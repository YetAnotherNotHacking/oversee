import os
import sys
import sqlite3
import requests
from pathlib import Path

# Add parent directory to path to import settings
sys.path.append(str(Path(__file__).parent.parent))
import settings

def download_database():
    """Download the pre-generated database from silverflag.net"""
    print("Downloading pre-generated IP database from silverflag.net...")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(settings.ip_info_db), exist_ok=True)
    
    try:
        # Download the database
        response = requests.get('https://silverflag.net/oversee/ip2loc.raw', stream=True)
        if response.status_code == 200:
            # Save with .raw extension first
            temp_path = settings.ip_info_db + '.raw'
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify the database is valid
            try:
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM ip_info')
                count = cursor.fetchone()[0]
                conn.close()
                
                if count > 0:
                    # Rename to .db
                    if os.path.exists(settings.ip_info_db):
                        os.remove(settings.ip_info_db)
                    os.rename(temp_path, settings.ip_info_db)
                    print(f"Successfully downloaded and verified database with {count} records")
                    return True
                else:
                    print("Downloaded database appears to be empty")
                    os.remove(temp_path)
                    return False
                    
            except sqlite3.Error as e:
                print(f"Error verifying downloaded database: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
        else:
            print(f"Failed to download database: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error downloading database: {e}")
        return False

def verify_database():
    """Verify the existing database"""
    try:
        if not os.path.exists(settings.ip_info_db):
            return False
            
        conn = sqlite3.connect(settings.ip_info_db)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ip_info'")
        if not cursor.fetchone():
            print("Database exists but ip_info table is missing")
            conn.close()
            return False
            
        # Check if table has data
        cursor.execute('SELECT COUNT(*) FROM ip_info')
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            print(f"Found existing database with {count} records")
            return True
        else:
            print("Database exists but is empty")
            return False
            
    except Exception as e:
        print(f"Error verifying database: {e}")
        return False

def main():
    """Main function to handle database setup"""
    print("Checking IP database...")
    
    # First check if we have a valid database
    if verify_database():
        print("Using existing database")
        return True
        
    # If no valid database, try to download
    if download_database():
        print("Successfully set up database")
        return True
        
    print("Failed to set up database")
    return False

if __name__ == "__main__":
    main() 