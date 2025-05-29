import requests
import json
from datetime import datetime
import settings

class RemoteDatabase:
    def __init__(self):
        self.api_url = settings.remote_db_url
        self.api_key = settings.remote_db_api_key
        
    def get_devices(self):
        """Fetch all devices from the remote database"""
        try:
            response = requests.get(
                f"{self.api_url}?action=get_devices&api_key={self.api_key}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching devices from remote database: {e}")
            return []
            
    def sync_devices(self, local_db_path):
        """Sync devices from remote database to local SQLite database"""
        try:
            import sqlite3
            
            # Get devices from remote database
            devices = self.get_devices()
            
            # Connect to local database
            conn = sqlite3.connect(local_db_path)
            cursor = conn.cursor()
            
            # Clear existing devices
            cursor.execute("DELETE FROM devices")
            
            # Insert devices from remote database
            for device in devices:
                cursor.execute('''
                    INSERT INTO devices (
                        ip, port, device_type, device_name, location,
                        status, last_seen, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    device['ip'],
                    device['port'],
                    device['device_type'],
                    device.get('device_name', ''),
                    device.get('location', ''),
                    device.get('status', 'Unknown'),
                    device.get('last_seen', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    device.get('notes', '')
                ))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"Error syncing devices: {e}")
            return False 