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
except:
    print("You appear to be in a minimal python environment, please come back in a full environment to ensure this script will function correctly.")
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
    startupmenu.update_status("Finished loading local libs", 20.0)
    download_complete = threading.Event()
    scraping_complete = threading.Event()
    def download_and_extract():
        try:
            startupmenu.update_status("Downloading IP2LOC database", 25.0)
            download_database(settings.DB_URL, settings.DB_ZIP, settings.DB_CSV)
            startupmenu.update_status("Downloaded IP2LOC database", 35.0)
            startupmenu.update_status("Unzipping IP2LOC database", 40.0)
            extract_database(settings.DB_CSV, settings.DB_ZIP)
            startupmenu.update_status("Unzipped IP2LOC database", 50.0)
        except Exception as e:
            print(f"Database download/extract error: {e}")
        finally:
            download_complete.set()
    def scrape_urls():
        try:
            startupmenu.update_status("Starting web scraping (multi-threaded)", 30.0)
            startupmenu.update_scraping_status("Initializing scrapers...", 0.0)
            def scraping_progress_callback(completed_pages, total_pages, total_links):
                progress_pct = (completed_pages / total_pages) * 100
                status_text = f"Scraped {completed_pages}/{total_pages} pages ({total_links} links found)"
                startupmenu.update_scraping_status(status_text, progress_pct)
            total_links = scrape_insecam_camera_urls(
                output_file=settings.insecam_output_file, 
                base_url=settings.base_url, 
                total_pages=settings.total_pages,
                max_workers=16, # Dangerous?
                progress_callback=scraping_progress_callback
            )
            
            startupmenu.update_scraping_status(f"Scraping complete! Found {total_links} total links", 100.0)
            startupmenu.update_status("Web scraping completed", 70.0)
            
        except Exception as e:
            print(f"Scraping error: {e}")
            startupmenu.update_scraping_status(f"Scraping failed: {str(e)}", 0.0)
        finally:
            scraping_complete.set()
    download_thread = threading.Thread(target=download_and_extract, daemon=True)
    scraping_thread = threading.Thread(target=scrape_urls, daemon=True)
    download_thread.start()
    scraping_thread.start()
    while not (download_complete.is_set() and scraping_complete.is_set()):
        time.sleep(0.1)
        if download_complete.is_set() and not scraping_complete.is_set():
            startupmenu.update_status("Database ready, still scraping links...", 60.0)
        elif scraping_complete.is_set() and not download_complete.is_set():
            startupmenu.update_status("Links ready, still processing database...", 60.0)
    startupmenu.update_status("Both tasks complete! Formatting URLs...", 80.0)
    try:
        format_file(input_file=settings.insecam_output_file, output_file=settings.ip_list_file)
        startupmenu.update_status("Formatting completed", 90.0)
    except Exception as e:
        print(f"Formatting error: {e}")
        startupmenu.update_status(f"Formatting failed: {str(e)}", 90.0)
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
