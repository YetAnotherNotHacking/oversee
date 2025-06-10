import requests
from bs4 import BeautifulSoup
import time
import random
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import sys
import settings

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://www.insecam.org/"
}

def extract_stream_links(page_url):
    stream_links = []
    try:
        response = requests.get(page_url, headers=headers, timeout=10)
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

def crawl_page_worker(page_info):
    page_num, base_url = page_info
    page_url = f"{base_url}?page={page_num}"
    links = extract_stream_links(page_url)
    return page_num, links

def scrape_insecam_camera_urls(output_file=settings.insecam_output_file, base_url=settings.base_url, total_pages=settings.total_pages, max_workers=5, progress_callback=None, force_redownload=False):
    """Download IP list from silverflag.net"""
    print(f"Starting download from https://silverflag.net/oversee/rawips.txt")
    print(f"Output will be saved to: {output_file}")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Check if file already exists and has content
    if os.path.exists(output_file) and not force_redownload:
        file_size = os.path.getsize(output_file)
        if file_size > 0:
            with open(output_file, 'r') as f:
                line_count = sum(1 for _ in f)
            print(f"Output file '{output_file}' already exists with {line_count} links ({file_size} bytes)")
            print("Skipping download. Use force_redownload=True to re-download.")
            return line_count
        else:
            print(f"Output file '{output_file}' exists but is empty. Proceeding with download...")
    elif force_redownload and os.path.exists(output_file):
        print(f"Force redownload enabled. Overwriting existing file '{output_file}'...")
    
    start_time = time.time()
    total_links = 0
    
    try:
        # Download the file
        response = requests.get("https://silverflag.net/oversee/rawips.txt", timeout=30)
        response.raise_for_status()
        
        # Save the content to file
        with open(output_file, 'w') as f:
            f.write(response.text)
        
        # Count the number of lines
        total_links = response.text.count('\n') + 1
        file_size = os.path.getsize(output_file)
        
        if progress_callback:
            progress_callback(1, 1, total_links)
            
        print(f"\nDownload completed!")
        print(f"Total time elapsed: {time.time() - start_time:.2f} seconds")
        print(f"Total links saved: {total_links}")
        print(f"Output file: {output_file} ({file_size} bytes)")
        print(f"Average speed: {total_links/(time.time() - start_time):.2f} links/second")
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {str(e)}")
        return 0
    
    return total_links