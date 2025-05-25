# All of the configurations from the program

import os

# Get the base directory (src folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data directory
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# File paths
ip_list_file = os.path.join(DATA_DIR, 'rawips.txt')
stream_links_file = os.path.join(DATA_DIR, 'stream_links.txt')
streamables_file = os.path.join(DATA_DIR, 'streamables.txt')

# Version
overseeversion = "0.2.13"

# Database paths
ip_info_db = os.path.join(DATA_DIR, 'ip_info.db')
cameras_db = os.path.join(DATA_DIR, 'cameras.db')

# IP2LOC database
DB_URL = "https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_ZIP = "IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_CSV = "IP2LOCATION-LITE-DB1.CSV"

# Insecam configs
insecam_output_file="stream_links.txt" # Raw output (needs processing to be streamed)
base_url = "http://www.insecam.org/en/byrating/" # Endpoint to scrape by
total_pages = 448 # Total number of pages on insecam, may require manual updating (I might implement autoupdating for this later)