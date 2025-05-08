import requests
from bs4 import BeautifulSoup
import time
import random
import os

output_file = "stream_links.txt"
base_url = "http://www.insecam.org/en/byrating/"
total_pages = 448 # May require a manual update

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://www.insecam.org/"
}

with open(output_file, 'w') as f:
    pass

def extract_stream_links(page_url):
    stream_links = []
    try:
        
        time.sleep(random.uniform(1, 3))
      
        response = requests.get(page_url, headers=headers)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            thumbnail_items = soup.select('a.thumbnail-item__wrap')
            for item in thumbnail_items:
                img_tag = item.select_one('img.thumbnail-item__img')
                if img_tag and 'src' in img_tag.attrs:
                    stream_url = img_tag['src']
                    stream_links.append(stream_url)
        else:
            print(f"Failed to retrieve page {page_url}: Status code {response.status_code}")
    except Exception as e:
        print(f"Error processing {page_url}: {str(e)}")
    
    return stream_links
def crawl_all_pages():
    total_links = 0
    
    for page_num in range(1, total_pages + 1):
        page_url = f"{base_url}?page={page_num}"
        print(f"Crawling page {page_num}/{total_pages}: {page_url}")

        links = extract_stream_links(page_url)
        total_links += len(links)

        with open(output_file, 'a') as f:
            for link in links:
                f.write(f"{link}\n")
        
        print(f"Found {len(links)} links on page {page_num}. Total links so far: {total_links}")

        progress = (page_num / total_pages) * 100
        print(f"Progress: {progress:.2f}%")

if __name__ == "__main__":
    print(f"Starting to crawl {total_pages} pages from {base_url}")
    start_time = time.time()
    
    crawl_all_pages()
    
    end_time = time.time()
    elapsed_time = end_time - start_time

    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        with open(output_file, 'r') as f:
            line_count = sum(1 for _ in f)
        
        print(f"\nCrawling completed!")
        print(f"Total time elapsed: {elapsed_time:.2f} seconds")
        print(f"Total links saved: {line_count}")
        print(f"Output file: {output_file} ({file_size} bytes)")
    else:
        print("Crawling completed but no output file was created.")
