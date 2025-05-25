# First, make sure that we are able to import Tkinter
try:
    import tkinter as tk
    from tkinter import ttk
except:
    print("""\
    [!] Failed to import tkinter.
    This program is not able to operate without tkinter. Please install it.
    To fix this, install the tkinter package for your Python installation:

    - On Debian/Ubuntu: sudo apt install python3-tk
    - On Arch Linux: sudo pacman -S tk
    - On Fedora: sudo dnf install python3-tkinter
    - On Windows: Make sure you installed Python from the official installer at python.org and enabled the "tcl/tk" option.
    - On macOS (Homebrew): brew install python-tk

    If you are on macOS and you need to install it, you are able to look here: https://brew.sh (copy the latest command and run it in your terminal)

    After installing, try running the program again.
    """)
    exit()

try:
    import threading
    import time
    import logging
except:
    print("You appear to be in a minimal python environment, please come back in a full environment to ensure this script will function correctly.")

logging.basicConfig(level=logging.DEBUG)

from gui.initgui import StartUpMenu
from gui.maingui import runmaingui
def initialization_tasks(startupmenu):
    startupmenu.update_status("Loading program settings", 5.0)
    import settings
    startupmenu.update_status("Loaded program settings", 10.0)
    startupmenu.update_status("Loading local libs", 15.0)
    from initdata.headinit import initall
    from initdata.ip2locdownload import download_database, extract_database
    from initdata.getiplist import scrape_insecam_camera_urls
    from initdata.formatscrapeddata import format_file
    from initdata.validateiplist import validate_file_address_reachable
    from initdata.getiplistcoordinates import process_ip_list
    startupmenu.update_status("Finished loading local libs", 20.0)

    
    download_complete = threading.Event()
    scraping_complete = threading.Event()
    
    def download_and_extract():
        try:
            def progress_callback(status, progress):
                startupmenu.update_status(status, 50.0 + (progress * 0.25))  # 50-75% range
            
            success = download_database(
                settings.DB_URL, 
                settings.DB_ZIP, 
                settings.DB_CSV,
                progress_callback=progress_callback
            )
            
            if not success:
                startupmenu.update_status("Failed to download IP2LOC database", 75.0)
                return
                
        except Exception as e:
            print(f"Database download/extract error: {e}")
            startupmenu.update_status(f"Database error: {str(e)}", 75.0)
        finally:
            download_complete.set()
    
    def scrape_urls():
        try:
            startupmenu.update_status("Starting web scraping (multi-threaded)", 75.0)
            startupmenu.update_scraping_status("Initializing scrapers...", 0.0)
            
            def scraping_progress_callback(completed_pages, total_pages, total_links):
                progress_pct = (completed_pages / total_pages) * 100
                status_text = f"Scraped {completed_pages}/{total_pages} pages ({total_links} links found)"
                startupmenu.update_scraping_status(status_text, progress_pct)
            
            total_links = scrape_insecam_camera_urls(
                output_file=settings.insecam_output_file, 
                base_url=settings.base_url, 
                total_pages=settings.total_pages,
                max_workers=8,
                progress_callback=scraping_progress_callback
            )
            
            startupmenu.update_scraping_status(f"Scraping complete! Found {total_links} total links", 100.0)
            startupmenu.update_status("Web scraping completed", 80.0)
            
        except Exception as e:
            print(f"Scraping error: {e}")
            startupmenu.update_scraping_status(f"Scraping failed: {str(e)}", 0.0)
        finally:
            scraping_complete.set()
    
    # Start both tasks
    download_thread = threading.Thread(target=download_and_extract, daemon=True)
    scraping_thread = threading.Thread(target=scrape_urls, daemon=True)
    download_thread.start()
    scraping_thread.start()
    
    # Wait for both tasks to complete
    while not (download_complete.is_set() and scraping_complete.is_set()):
        time.sleep(0.1)
        if download_complete.is_set() and not scraping_complete.is_set():
            startupmenu.update_status("Database ready, still scraping links...", 80.0)
        elif scraping_complete.is_set() and not download_complete.is_set():
            startupmenu.update_status("Links ready, still processing database...", 70.0)
    
    startupmenu.update_status("Both tasks complete! Formatting URLs and verifying connectivity...", 85.0)
    try:
        format_file(input_file=settings.insecam_output_file, output_file=settings.ip_list_file)
        validate_file_address_reachable(max_workers=256)
        startupmenu.update_status("Formatting completed", 90.0)
    except Exception as e:
        print(f"Formatting error: {e}")
        startupmenu.update_status(f"Formatting failed: {str(e)}", 90.0)
    
    # At this point IDK the status percentage is so bad i dont even pringles can
    startupmenu.update_status("Processing IP geolocation data...", 25.0)
    process_ip_list(progress_callback=lambda progress, processed, total: startupmenu.update_status(f"Processing IPs: {processed}/{total} ({progress:.1f}%)", 25.0 + (progress * 0.25)))
    startupmenu.update_status("IP geolocation data processed", 50.0)

    startupmenu.update_status("", 95.0)
    startupmenu.update_status("Finalizing application startup", 95.0)
    time.sleep(0.5)
    startupmenu.update_status("", 98.0)
    startupmenu.update_status("Complete!", 100.0)
    time.sleep(1.0)

def on_completion():
    print("Initialization complete! Starting main application...")
    
if __name__ == "__main__":
    # INIT
    startupmenu = StartUpMenu()
    startupmenu.start_with_tasks(initialization_tasks, on_completion)
    # MAIN
    runmaingui()
