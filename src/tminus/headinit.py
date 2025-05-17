from src.tminus.getiplist import scrape_insecam_camera_urls

raw_scraped_data_file = "stream_links.txt" # From scraper
processed_urls_file = "rawips.txt" # For program to read

def initall():
    scrape_insecam_camera_urls()

if __name__ == "__main__":
    main()