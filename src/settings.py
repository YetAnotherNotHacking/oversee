# All of the configurations from the program

import os
import sys
from pathlib import Path
from utility.paths import (
    get_database_path,
    get_log_file_path,
    get_cache_file_path,
    get_config_file_path,
    ensure_data_directories,
    verify_data_access
)

# Get the appropriate data directory based on platform
if sys.platform == 'darwin':  # macOS
    # Use /Users/Shared/OVERSEE for system-wide shared data
    DATA_DIR = '/Users/Shared/OVERSEE'
else:
    # Get the base directory (src folder)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# File paths
ip_list_file = os.path.join(DATA_DIR, 'rawips.txt')
stream_links_file = os.path.join(DATA_DIR, 'stream_links.txt')
streamables_file = os.path.join(DATA_DIR, 'streamables.txt')

# Version
overseeversion = "1.0.0"

# Database paths
cameras_db = get_database_path('cameras.db')
ip_info_db = get_database_path('ip_info.db')

# Log file paths
app_log = get_log_file_path('app.log')
error_log = get_log_file_path('error.log')

# Cache paths
geolocation_cache = get_cache_file_path('geolocation.json')

# Config paths
app_config = get_config_file_path('config.json')
user_preferences = get_config_file_path('preferences.json')

# IP2LOC database
DB_URL = "https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_ZIP = "IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_CSV = "IP2LOCATION-LITE-DB1.CSV"

# Insecam configs
insecam_output_file = os.path.join(DATA_DIR, "stream_links.txt")  # Raw output (needs processing to be streamed)
base_url = "http://www.insecam.org/en/byrating/"  # Endpoint to scrape by
total_pages = 448  # Total number of pages on insecam, may require manual updating (I might implement autoupdating for this later)

# Remote Database Settings
remote_db_url = "http://silverflag.net/oversee/backend/db.php"  # Update with your actual domain
remote_db_api_key = "publicaccesstokenzareawesome"  # Update with your actual API key

# Ensure all required directories exist
ensure_data_directories()

# Verify write access
verify_data_access()

# Default settings
DEFAULT_SETTINGS = {
    'max_threads': 200,
    'refresh_interval': 300,  # 5 minutes
    'preview_size': (320, 240),
    'max_cameras': 1000,
    'auto_refresh': True,
    'dark_mode': True,
    'show_offline': True,
    'cache_duration': 86400,  # 24 hours
    'log_level': 'INFO',
    'max_log_size': 10485760,  # 10MB
    'backup_count': 5
}