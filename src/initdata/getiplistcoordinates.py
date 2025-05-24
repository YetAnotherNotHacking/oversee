import os
import sys
import sqlite3
import requests
import time
from pathlib import Path

# Add parent directory to path to import settings
sys.path.append(str(Path(__file__).parent.parent))
import settings

def init_ip_info_db():
    """Initialize the IP info database"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ip_info.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
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
    return db_path

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

def process_ip_list():
    """Process all IPs in the list file and store their coordinates"""
    print("Initializing IP coordinates database...")
    
    # Initialize database
    db_path = init_ip_info_db()
    
    # Read IP list
    try:
        with open(settings.ip_list_file, 'r') as f:
            ip_list = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    except Exception as e:
        print(f"Error reading IP list file: {e}")
        return
    
    total_ips = len(ip_list)
    print(f"Found {total_ips} IPs to process")
    
    # Process each IP
    processed = 0
    for ip in ip_list:
        try:
            # Extract base IP without endpoint or port
            base_ip = ip.split('/')[0] if '/' in ip else ip
            base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
            
            # Check cache first
            result = get_cached_ip_info(base_ip, db_path)
            
            if not result:
                # Get IP info from API
                response = requests.get(f"https://ipinfo.io/{base_ip}")
                if response.status_code == 200:
                    data = response.json()
                    if 'loc' in data:
                        lat, lon = map(float, data['loc'].split(','))
                        result = {
                            'ip': base_ip,
                            'lat': lat,
                            'lon': lon,
                            'city': data.get('city', ''),
                            'country': data.get('country', '')
                        }
                        # Save to database
                        save_ip_info(result, db_path)
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)
            
            processed += 1
            if processed % 10 == 0:  # Progress update every 10 IPs
                print(f"Processed {processed}/{total_ips} IPs ({(processed/total_ips)*100:.1f}%)")
                
        except Exception as e:
            print(f"Error processing IP {ip}: {e}")
            continue
    
    print(f"Completed processing {processed}/{total_ips} IPs")

if __name__ == "__main__":
    process_ip_list() 