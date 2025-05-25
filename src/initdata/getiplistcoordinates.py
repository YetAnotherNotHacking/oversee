import os
import sys
import sqlite3
import requests
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path to import settings
sys.path.append(str(Path(__file__).parent.parent))
import settings

def init_ip_info_db():
    """Initialize the IP info database"""
    db_path = settings.ip_info_db
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Check if database already exists and has data
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ip_info')
            count = cursor.fetchone()[0]
            conn.close()
            print(f"Existing database found with {count} IP records")
            if count > 0:
                print("Using existing database")
                return db_path
        except Exception as e:
            print(f"Error checking existing database: {e}")
    
    # Try to download the database from silverflag.net
    try:
        print("Attempting to download IP database from silverflag.net...")
        response = requests.get('https://silverflag.net/oversee/ip_info.raw', stream=True)
        if response.status_code == 200:
            # Save the downloaded database with .raw extension first
            temp_path = db_path + '.raw'
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            # Rename to .db
            os.rename(temp_path, db_path)
            
            # Verify the database after download
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ip_info')
            count = cursor.fetchone()[0]
            conn.close()
            print(f"Successfully downloaded IP database from silverflag.net with {count} records")
        else:
            print("Database not available on silverflag.net, will create locally")
            create_empty_db(db_path)
    except Exception as e:
        print(f"Error downloading database: {e}")
        print("Creating local database...")
        create_empty_db(db_path)
    
    return db_path

def create_empty_db(db_path):
    """Create an empty database with the correct schema"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ip_info (
            ip TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            city TEXT,
            country TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_cached_ip_info(ip, db_path):
    """Get IP info from database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT lat, lon, city, country FROM ip_info WHERE ip = ?', (ip,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'ip': ip,
                'lat': result[0],
                'lon': result[1],
                'city': result[2],
                'country': result[3]
            }
    except Exception as e:
        print(f"Error getting cached IP info: {e}")
    return None

def save_ip_info(data, db_path):
    """Save IP info to database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ip_info (ip, lat, lon, city, country, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (data['ip'], data['lat'], data['lon'], data['city'], data['country']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving IP info: {e}")

def normalize_ip(ip):
    """Normalize IP address by removing any endpoint or port"""
    base_ip = ip.split('/')[0] if '/' in ip else ip
    base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
    return base_ip

def process_single_ip(ip, db_path, progress_callback=None):
    """Process a single IP address and get its coordinates."""
    try:
        # Extract base IP without endpoint or port
        base_ip = normalize_ip(ip)
        
        # Add a delay to avoid rate limiting
        time.sleep(0.5)  # 500ms delay between requests
        
        # First try to get from cache
        cached_info = get_cached_ip_info(base_ip, db_path)
        if cached_info:
            return cached_info
            
        # Try ipinfo.io first
        try:
            response = requests.get(f'https://ipinfo.io/{base_ip}/json', 
                                  headers={'User-Agent': 'Mozilla/5.0'})
            
            if response.status_code == 429:
                # If we hit rate limit, try ip.guide as fallback
                print(f"Rate limit hit with ipinfo.io, trying ip.guide for {base_ip}")
                response = requests.get(f'https://ip.guide/{base_ip}',
                                     headers={'User-Agent': 'Mozilla/5.0'})
                
                if response.status_code == 200:
                    data = response.json()
                    info = {
                        'ip': base_ip,
                        'lat': float(data.get('latitude', 0)),
                        'lon': float(data.get('longitude', 0)),
                        'city': data.get('city', ''),
                        'country': data.get('country', '')
                    }
                    save_ip_info(info, db_path)
                    return info
            elif response.status_code == 200:
                data = response.json()
                if 'loc' in data:
                    lat, lon = map(float, data['loc'].split(','))
                    info = {
                        'ip': base_ip,
                        'lat': lat,
                        'lon': lon,
                        'city': data.get('city', ''),
                        'country': data.get('country', '')
                    }
                    save_ip_info(info, db_path)
                    return info
        except Exception as e:
            print(f"Error with ipinfo.io for {base_ip}: {e}")
            # If ipinfo.io fails, try ip.guide
            try:
                response = requests.get(f'https://ip.guide/{base_ip}',
                                     headers={'User-Agent': 'Mozilla/5.0'})
                
                if response.status_code == 200:
                    data = response.json()
                    info = {
                        'ip': base_ip,
                        'lat': float(data.get('latitude', 0)),
                        'lon': float(data.get('longitude', 0)),
                        'city': data.get('city', ''),
                        'country': data.get('country', '')
                    }
                    save_ip_info(info, db_path)
                    return info
            except Exception as e2:
                print(f"Error with ip.guide for {base_ip}: {e2}")
                
    except Exception as e:
        print(f"Error processing IP {ip}: {e}")
    return None

def process_ip_list(progress_callback=None):
    """Process all IPs in the list file and store their coordinates"""
    print("Initializing IP coordinates database...")
    
    # Initialize database once at the start
    db_path = init_ip_info_db()
    
    # Read IP list from rawips.txt
    ip_list = set()  # Use a set to avoid duplicates
    
    try:
        # Read from rawips.txt
        with open(settings.ip_list_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Normalize IP before adding to set
                    ip_list.add(normalize_ip(line))
    except Exception as e:
        print(f"Error reading IP list file: {e}")
        return
    
    # Get list of IPs already in database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT ip FROM ip_info')
    existing_ips = {normalize_ip(row[0]) for row in cursor.fetchall()}
    conn.close()
    
    # Filter out IPs that are already in database
    new_ips = ip_list - existing_ips
    
    total_ips = len(ip_list)
    existing_count = len(existing_ips)
    new_count = len(new_ips)
    
    print(f"Found {total_ips} total unique IPs")
    print(f"Database already contains {existing_count} IP records")
    print(f"Need to process {new_count} new IPs")
    
    if new_count == 0:
        print("All IPs already in database, skipping processing")
        return existing_count
    
    # Process only new IPs in parallel using ThreadPoolExecutor
    processed = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit only new IPs for processing
        future_to_ip = {executor.submit(process_single_ip, ip, db_path): ip for ip in new_ips}
        
        # Process results as they complete
        for future in future_to_ip:
            try:
                result = future.result()
                processed += 1
                
                # Update progress
                if progress_callback:
                    progress = (processed / new_count) * 100
                    progress_callback(progress, processed, new_count)
                elif processed % 10 == 0:  # Console progress update every 10 IPs
                    print(f"Processed {processed}/{new_count} new IPs ({(processed/new_count)*100:.1f}%)")
                    
            except Exception as e:
                print(f"Error processing IP {future_to_ip[future]}: {e}")
                continue
    
    # Final database count
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM ip_info')
    final_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"Completed processing {processed}/{new_count} new IPs")
    print(f"Final database contains {final_count} IP records")
    return final_count

if __name__ == "__main__":
    process_ip_list() 