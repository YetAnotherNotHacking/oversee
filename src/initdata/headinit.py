import os

from initdata.getiplist import scrape_insecam_camera_urls
from initdata.ip2locdownload import download_database
from initdata.formatscrapeddata import format_file

raw_scraped_data_file = "stream_links.txt" # From scraper
processed_urls_file = "rawips.txt" # For program to read
base_url = "http://www.insecam.org/en/byrating/"
total_pages = 448
database_url = "https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.CSV.ZIP"
database_compressed_name = "IP2LOCATION-LITE-DB1.CSV.ZIP"
database_uncompressed_name = "IP2LOCATION-LITE-DB1.CSV"

def check_file_existance(file1, file2):
    return os.path.isfile(file1), os.path.isfile(file2)

def safe_remove(path):
    if os.path.isfile(path):
        os.remove(path)

def initall():
    raw_exists, processed_exists = check_file_existance(raw_scraped_data_file, processed_urls_file)
    if not raw_exists or not processed_exists:
        safe_remove(raw_scraped_data_file)
        safe_remove(processed_urls_file)
        print(f"Starting to scrape {base_url} for {total_pages} pages")
        scrape_insecam_camera_urls(output_file=raw_scraped_data_file, base_url=base_url, total_pages=total_pages)
        print("Done scraping for the ip list")
        print("Starting to format the files")
        format_file(raw_scraped_data_file, processed_urls_file)
    print("Checking if the database is needed, downloading if it's missing")
    download_database(database_url, database_compressed_name, database_uncompressed_name)
    print("Done downloading the ip2loc database")