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
    import os
    import sys
    import tempfile
    import platform
    import signal
    import atexit
except:
    print("You appear to be in a minimal python environment, please come back in a full environment to ensure this script will function correctly.")

logging.basicConfig(level=logging.DEBUG)

# Application singleton check
_lock_file = None

def acquire_app_lock():
    """Acquire application-level lock to prevent multiple instances"""
    global _lock_file
    try:
        lock_file_path = os.path.join(tempfile.gettempdir(), 'oversee_app.lock')
        
        # Check if lock file exists and contains a running PID
        if os.path.exists(lock_file_path):
            try:
                with open(lock_file_path, 'r') as f:
                    pid = int(f.read().strip())
                    # Check if process is still running
                    if platform.system() == "Windows":
                        import subprocess
                        result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                              capture_output=True, text=True)
                        if str(pid) in result.stdout:
                            return False  # Process still running
                    else:
                        try:
                            os.kill(pid, 0)  # Signal 0 just checks if process exists
                            return False  # Process still running
                        except OSError:
                            pass  # Process not running, can proceed
            except (ValueError, IOError):
                pass  # Invalid lock file, proceed
        
        # Create/update lock file
        _lock_file = open(lock_file_path, 'w')
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
        
        # Register cleanup handlers
        atexit.register(release_app_lock)
        if platform.system() != "Windows":
            signal.signal(signal.SIGTERM, lambda sig, frame: release_app_lock())
            signal.signal(signal.SIGINT, lambda sig, frame: release_app_lock())
        
        return True
    except (IOError, OSError):
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        return False

def release_app_lock():
    """Release application-level lock"""
    global _lock_file
    if _lock_file:
        try:
            _lock_file.close()
            lock_file_path = os.path.join(tempfile.gettempdir(), 'oversee_app.lock')
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)
        except:
            pass
        _lock_file = None

from gui.initgui import StartUpMenu
from gui.maingui import runmaingui

# Ensure we can import settings properly
try:
    import settings
    print(f"Settings imported successfully from: {settings.__file__}")
except ImportError as e:
    print(f"Failed to import settings: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    
    # Try to add the correct directories to path if we're in a packaged app
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        print("Detected PyInstaller bundle execution")
        bundle_dir = sys._MEIPASS
        print(f"Bundle directory: {bundle_dir}")
        
        # Add multiple possible source directories
        possible_src_dirs = [
            os.path.join(bundle_dir, 'src'),
            os.path.join(bundle_dir),
            bundle_dir,
        ]
        
        for src_dir in possible_src_dirs:
            if os.path.exists(src_dir) and src_dir not in sys.path:
                sys.path.insert(0, src_dir)
                print(f"Added to path: {src_dir}")
    else:
        # Running as a script - ensure src directory is in path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = script_dir  # We're already in src/
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
            print(f"Added script src dir to path: {src_dir}")
    
    # Try importing again
    try:
        import settings
        print("Settings imported successfully after path adjustment")
    except ImportError as e2:
        print(f"Still failed to import settings after path adjustment: {e2}")
        print("Available files in bundle:")
        if getattr(sys, 'frozen', False):
            try:
                for root, dirs, files in os.walk(sys._MEIPASS):
                    level = root.replace(sys._MEIPASS, '').count(os.sep)
                    indent = ' ' * 2 * level
                    print(f"{indent}{os.path.basename(root)}/")
                    subindent = ' ' * 2 * (level + 1)
                    for file in files[:10]:  # Limit to first 10 files per directory
                        print(f"{subindent}{file}")
                    if len(files) > 10:
                        print(f"{subindent}... and {len(files) - 10} more files")
            except Exception as walk_e:
                print(f"Could not walk bundle directory: {walk_e}")
        
        # Try a different approach - look for settings.py specifically
        try:
            import importlib.util
            if getattr(sys, 'frozen', False):
                settings_path = os.path.join(sys._MEIPASS, 'settings.py')
                if not os.path.exists(settings_path):
                    settings_path = os.path.join(sys._MEIPASS, 'src', 'settings.py')
            else:
                settings_path = os.path.join(os.path.dirname(__file__), 'settings.py')
            
            if os.path.exists(settings_path):
                print(f"Found settings.py at: {settings_path}")
                spec = importlib.util.spec_from_file_location("settings", settings_path)
                settings = importlib.util.module_from_spec(spec)
                sys.modules["settings"] = settings
                spec.loader.exec_module(settings)
                print("Settings imported via direct file loading")
            else:
                print(f"Could not find settings.py at expected location: {settings_path}")
                sys.exit(1)
        except Exception as e3:
            print(f"Direct file loading also failed: {e3}")
            sys.exit(1)

def initialization_tasks(startupmenu):
    startupmenu.update_status("Loading program settings", 5.0)
    # Settings is now imported at module level
    startupmenu.update_status("Loaded program settings", 10.0)
    
    # Install Playwright browsers if needed
    startupmenu.update_status("Installing Playwright browsers...", 12.0)
    try:
        import subprocess
        import sys
        
        # Check if Playwright browsers are installed
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                if not os.path.exists(p.chromium.executable_path):
                    print("Installing Playwright browsers...")
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                    print("Playwright browsers installed successfully")
        except Exception as e:
            print(f"Warning: Failed to install Playwright browsers: {e}")
            
    except Exception as e:
        print(f"Warning: Failed to install Playwright browsers: {e}")
    startupmenu.update_status("Playwright installation complete", 15.0)
    
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
    # Launch the main GUI after initialization is complete
    from gui.maingui import runmaingui
    runmaingui()

def init():
    """Initialize the application"""
    # Check for already running instance
    if not acquire_app_lock():
        print("Another instance of Oversee is already running. Exiting.")
        return
    
    try:
        # Create data directory
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        
        # Initialize database
        from gui.initgui import init_database
        init_database()
        
        # Install Playwright browsers if needed
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                if not os.path.exists(p.chromium.executable_path):
                    print("Installing Playwright browsers...")
                    import subprocess
                    subprocess.run(["playwright", "install", "chromium"], check=True)
                    print("Playwright browsers installed successfully")
        except Exception as e:
            print(f"Warning: Failed to install Playwright browsers: {e}")
        
        # Start GUI with initialization tasks
        startupmenu = StartUpMenu()
        startupmenu.start_with_tasks(initialization_tasks, on_completion)
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)
    finally:
        # Always release the lock when done
        release_app_lock()

if __name__ == "__main__":
    # Use the centralized init function instead of calling runmaingui directly
    init()
