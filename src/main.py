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

# Load the loadup menu functions
from gui.initgui import StartUpMenu

# Set up the loading menu
startupmenu = StartUpMenu()
startupmenu.show_loading_window()

# Load the program settings
startupmenu.loadup_status = "Loading program settings"
startupmenu.loadup_status = 5.0
from settings import *
startupmenu.loadup_status = "Loaded program settings"
startupmenu.loadup_status = 6.0

# Load the rest of the codebase
startupmenu.loadup_status = "Loading local libs"
startupmenu.loadup_percentage = 10.0
from initdata.headinit import initall
from initdata.ip2locdownload import download_database, extract_database
startupmenu.loadup_status = "Finished loading local libs"
startupmenu.loadup_percentage = 11.0

# Download IP2LOC
startupmenu.loadup_status = "Downloading IP2LOC database"
startupmenu.loadup_percentage = 20.0
download_database(settings.DB_URL, settings.DB_ZIP, settings.DB_CSV)
startupmenu.loadup_status = "Downloaded IP2LOC database"
startupmenu.loadup_percentage = 21.0

# Unzip IP2LOC
startupmenu.loadup_status = "Unzipping IP2LOC database"
startupmenu.loadup_percentage = 30.0
extract_database(settings.DB_CSV, settings.DB_ZIP)
startupmenu.loadup_status = "Unzipped IP2LOC database"
startupmenu.loadup_percentage = 31.0

# Scrape for the Insecam URLS
startupmenu.loadup_status = "Scraping for fresh links (this might take a while...)"
startupmenu.loadup_percentage = 50.0
from initdata.getiplist import scrape_insecam_camera_urls
scrape_insecam_camera_urls(output_file=settings.insecam_output_file, base_url=settings.base_url, total_pages=settings.total_pages)
startupmenu.loadup_status = "Scraped raw data from Insecam"
startupmenu.loadup_percentage = 55.0

# Process the craped insecam URLS
startupmenu.loadup_status = "Formatting the URLs for their raw endpoints..."
startupmenu.loadup_percentage = 80.0
from initdata.formatscrapeddata import format_file
format_file(input_file=settings.insecam_output_file, output_file=settings.ip_list_file)
startupmenu.loadup_status = "Formatting completed"
startupmenu.loadup_percentage = 85.0

# Final stuff
startupmenu.loadup_status = "Finalizing"
startupmenu.loadup_percentage = 95.0
startupmenu.loadup_status = "Showing window"
startupmenu.loadup_percentage = 99.9

# Shut down the load up window
startupmenu.overandout()