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
    """Scrape camera URLs from insecam.org"""
    print(f"Starting scrape of {total_pages} pages from {base_url}")
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
    
    # Create/clear the output file
    with open(output_file, 'w') as f:
        pass
    
    print(f"Starting to crawl {total_pages} pages from {base_url} using {max_workers} threads")
    start_time = time.time()
    page_infos = [(page_num, base_url) for page_num in range(1, total_pages + 1)]
    total_links = 0
    completed_pages = 0
    file_lock = threading.Lock()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page = {executor.submit(crawl_page_worker, page_info): page_info[0] 
                         for page_info in page_infos}
        
        for future in as_completed(future_to_page):
            page_num = future_to_page[future]
            try:
                page_num_result, links = future.result()
                with file_lock:
                    with open(output_file, 'a') as f:
                        for link in links:
                            f.write(f"{link}\n")
                    total_links += len(links)
                    completed_pages += 1
                    print(f"Completed page {page_num_result}: {len(links)} links found. "
                          f"Total: {total_links} links from {completed_pages}/{total_pages} pages")
                    if progress_callback:
                        progress_callback(completed_pages, total_pages, total_links)
            except Exception as e:
                print(f"Error processing page {page_num}: {str(e)}")
                completed_pages += 1
                if progress_callback:
                    progress_callback(completed_pages, total_pages, total_links)
    
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
        print(f"Average speed: {line_count/elapsed_time:.2f} links/second")
    else:
        print("Crawling completed but no output file was created.")
    
    return total_links