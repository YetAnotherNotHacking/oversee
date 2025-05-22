# All of the configurations from the program

# IP2LOC database
DB_URL = "https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_ZIP = "IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_CSV = "IP2LOCATION-LITE-DB1.CSV"

# Insecam configs
insecam_output_file="stream_links.txt" # Raw output (needs processing to be streamed)
base_url = "http://www.insecam.org/en/byrating/" # Endpoint to scrape by
total_pages = 448 # Total number of pages on insecam, may require manual updating (I might implement autoupdating for this later)

# IP list settings
ip_list_file = "streamables.txt"