from tminus.getiplist import scrape_insecam_camera_urls
from tminus.ip2locdownload import download_database

raw_scraped_data_file = "stream_links.txt" # From scraper
processed_urls_file = "rawips.txt" # For program to read
base_url = "http://www.insecam.org/en/byrating/"
total_pages = 448
database_url = "https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.CSV.ZIP"
database_compressed_name = "IP2LOCATION-LITE-DB1.CSV.ZIP"
database_uncompressed_name = "IP2LOCATION-LITE-DB1.CSV"

def initall():
    print(f"Starting to scrape {base_url} for {total_pages} pages")
    scrape_insecam_camera_urls(output_file=raw_scraped_data_file, base_url=base_url, total_pages=total_pages)
    print("Done scraping for the ip list")
    print("Checking if the database is needed, downloading if it's missing")
    download_database(database_url, database_compressed_name. database_uncompressed_name)
    print("Done downloading the ip2loc database")

if __name__ == "__main__":
    main()