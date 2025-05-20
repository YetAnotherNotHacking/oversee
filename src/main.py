# SilverFlag Camera Viewer
# View many cameras @ once and switch between them
# https://github.com/yetanothernothacking/oversee
try:
    from tminus.headinit import initall
    from tzero.cleanolddatabases import remove_ip2loc, remove_iplist
    import argparse
    import cv2
    import threading
    import numpy as np
    import random
    import time
    import requests
    import urllib.parse
    import logging
    import os
    import psutil
    import pyautogui
    from pynput import mouse
    import platform
    import subprocess
    import ctypes
    from collections import deque
    import time
    import re
    import zipfile
    import csv
    import ipaddress
    from bisect import bisect_right
    import traceback
except ImportError as e:
    print("Did you run 'pip3 install -r requirements.txt? You are missing something.'")
    print(f"Missing package {e}")

logging.basicConfig(level=logging.DEBUG)
geolocation_data = {}

# Global layout variables for panel display
right_panel_left = 0
right_panel_right = 0
right_panel_top = 0
right_panel_bottom = 0
camera_view_height = 0
camera_view_top = 0
camera_view_bottom = 0
info_section_top = 0
info_section_bottom = 0
info_section_height = 0
right_activity_left = 0
right_activity_right = 0

# Application color palette (BGR format for OpenCV)
# Using a more professional blue-based theme
COLOR_PALETTE = {
    # Main colors
    'background_dark': (30, 30, 30),       # Monotone gray background
    'background_medium': (70, 70, 70),     # Medium blue-gray for panels
    'background_light': (90, 90, 90),      # Lighter blue-gray for highlights
    
    # Accent colors
    'accent_primary': (130, 90, 50),       # Orange accent
    'accent_secondary': (50, 150, 180),    # Yellow accent
    'accent_tertiary': (120, 60, 40),      # Reddish accent
    
    # Text colors
    'text_bright': (240, 240, 240),        # Bright white for primary text
    'text_medium': (180, 180, 180),        # Medium gray for secondary text
    'text_dim': (120, 120, 120),           # Dimmed text for less important elements
    
    # Status colors
    'status_good': (20, 180, 20),          # Green for good status
    'status_warning': (20, 180, 240),      # Yellow for warning
    'status_error': (20, 20, 180),         # Red for errors
    
    # UI elements
    'button_normal': (80, 120, 150),       # Blue-gray buttons
    'button_hover': (100, 140, 170),       # Lighter when hovered
    'button_active': (120, 160, 190),      # Even lighter when active
    'border': (100, 100, 120),             # Border color
    'divider': (60, 80, 100),              # Divider lines
    
    # Graph colors
    'graph_bg': (40, 40, 60),              # Graph background
    'graph_grid': (70, 70, 90),            # Graph grid lines
    'graph_line1': (0, 180, 255),          # Graph line 1 (orange)
    'graph_line2': (0, 210, 210),          # Graph line 2 (yellow)
    'graph_line3': (50, 200, 50),          # Graph line 3 (green)
    'graph_fill1': (0, 50, 80),            # Graph fill 1 (translucent orange)
    'graph_fill2': (50, 80, 50),           # Graph fill 2 (translucent yellow)
    'graph_fill3': (30, 80, 30),           # Graph fill 3 (translucent green)
}

def get_raw_screen_resolution():
    system = platform.system()

    if system == "Windows":
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        return width, height

    elif system == "Darwin":
        import Quartz
        main_display = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        width = int(main_display.size.width)
        height = int(main_display.size.height)
        return width, height

    elif system == "Linux":
        output = subprocess.check_output("xrandr | grep '*' | awk '{print $1}'", shell=True)
        width, height = map(int, output.decode().strip().split('x'))
        return width, height

    else:
        raise NotImplementedError("Unsupported OS")

# IP Databases
DB_URL = "https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_ZIP = "IP2LOCATION-LITE-DB1.CSV.ZIP"
DB_CSV = "IP2LOCATION-LITE-DB1.CSV"

# Main files for operation
IP_LIST_FILE = "rawips.txt"

# MainActivity (the area that the actual important part of the applicatoin is, this is sourrounded by the padding with the graphs and the status and stuff)
# Since padding is 40 px we will just get it from the screen size, accounting for that. I make too many variables.
windowactivity_topleft_x = 40
windowactivity_topleft_y = 40
windowactivity_bottomright_x = get_raw_screen_resolution()[0] - 40
windowactivity_bottomright_y = get_raw_screen_resolution()[1] - 40

windowactivity_activity_seperator_space = 40
windowactivity_activity_offset = windowactivity_activity_seperator_space / 2

windowactivity_leftactivity_topleft_x = windowactivity_topleft_x
windowactivity_leftactivity_topleft_y = windowactivity_topleft_y

windowactivity_leftactivity_bottomright_x = int((windowactivity_bottomright_x / 2) - windowactivity_activity_offset)
windowactivity_leftactivity_bottomright_y = windowactivity_bottomright_y

windowactivity_rightactivity_topleft_x = int((windowactivity_bottomright_x / 2) + windowactivity_activity_offset)
windowactivity_rightactivity_topleft_y = windowactivity_topleft_y

windowactivity_rightactivity_bottomright_x = windowactivity_bottomright_x
windowactivity_rightactivity_bottomright_y = windowactivity_bottomright_y

default_stream_params = {
    "nphMotionJpeg": "?Resolution=640x480&Quality=Standard",
    "faststream.jpg": "?stream=half&fps=16",
    "SnapshotJPEG": "?Resolution=640x480&amp;Quality=Clarity&amp;1746245729",
    "cgi-bin/camera": "?resolution=640&amp;quality=1&amp;Language=0",
    "GetLiveImage": "?connection_id=e0e2-4978d822",
    "GetOneShot": "?image_size=640x480&frame_count=1000000000",
    "webcapture.jpg": "?command=snap&channel=1",
    "snap.jpg": "?JpegSize=M&JpegCam=1"
}

_selected_python_joke = None

start_time = time.time()

cpu_usage_history = deque(maxlen=60)
mem_usage_history = deque(maxlen=60)
last_update_time = 0
selected_page = 1

# Buttons
# Matrix view button
button_page_1_topleft_x = 960
button_page_1_topleft_y = 0
button_page_1_bottomright_x = button_page_1_topleft_x + 230
button_page_1_bottomright_y = 40

# Grid view button
button_page_2_topleft_x = 1200
button_page_2_topleft_y = 0
button_page_2_bottomright_x = button_page_2_topleft_x + 220
button_page_2_bottomright_y = 40

# Map view button (new)
button_page_3_topleft_x = 1430
button_page_3_topleft_y = 0
button_page_3_bottomright_x = button_page_3_topleft_x + 220
button_page_3_bottomright_y = 40

# Scroll Up Button
button_list_scrollup_topleft_x = windowactivity_leftactivity_bottomright_x - 60
button_list_scrollup_topleft_y = get_raw_screen_resolution()[1] - 140
button_list_scrollup_bottomright_x = windowactivity_leftactivity_bottomright_x - 20
button_list_scrollup_bottomright_y = get_raw_screen_resolution()[1] - 100

# Scroll Down Button
button_list_scrolldn_topleft_x = windowactivity_leftactivity_bottomright_x - 60
button_list_scrolldn_topleft_y = get_raw_screen_resolution()[1] - 80
button_list_scrolldn_bottomright_x = windowactivity_leftactivity_bottomright_x - 20
button_list_scrolldn_bottomright_y = get_raw_screen_resolution()[1] - 40

# List viewing settings
view_list_visible_address_count = 10
view_list_scroll_step_size = 1

# Dynamic variables for the list
current_list_position = 0

# Add a popup mutex lock
popup_lock = threading.Lock()
popup_active = False
popup_queue = deque(maxlen=5)

# Add selected camera variable
selected_camera = None

# Add global variable to keep track of working cameras
working_cameras = []

# Add tracking for camera metadata
camera_metadata = {}

# Add bandwidth tracking
bandwidth_history = deque(maxlen=60)  # Store 60 seconds of bandwidth data
last_bandwidth_check = 0
prev_bytes_sent = 0
prev_bytes_recv = 0

# Add mouse position tracking for tooltips
mouse_position = (0, 0)
hover_tooltip_active = False
hover_tooltip_data = None
hover_tooltip_last_update = 0

# Add global variables for location clustering
location_clusters = {}
last_cluster_update_time = 0
selected_location_cluster = None

def update_bandwidth_usage():
    """Updates the bandwidth usage history"""
    global bandwidth_history, last_bandwidth_check, prev_bytes_sent, prev_bytes_recv
    
    now = time.time()
    if now - last_bandwidth_check >= 1:  # Update every second
        # Get network stats
        net_stats = psutil.net_io_counters()
        bytes_sent, bytes_recv = net_stats.bytes_sent, net_stats.bytes_recv
        
        # Calculate deltas
        if prev_bytes_sent > 0 and prev_bytes_recv > 0:
            sent_delta = bytes_sent - prev_bytes_sent
            recv_delta = bytes_recv - prev_bytes_recv
            
            # Store sent/received separately
            total_delta = (sent_delta + recv_delta) / 1024  # KB/s
            sent_delta_kb = sent_delta / 1024  # KB/s
            recv_delta_kb = recv_delta / 1024  # KB/s
            
            bandwidth_history.append((total_delta, sent_delta_kb, recv_delta_kb))
        else:
            # Initialize with zeros if first run
            bandwidth_history.append((0, 0, 0))
        
        # Update previous values
        prev_bytes_sent = bytes_sent
        prev_bytes_recv = bytes_recv
        last_bandwidth_check = now

def format_bandwidth(bytes_per_sec):
    """Formats bandwidth in human-readable format"""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.1f} KB/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} MB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024):.1f} GB/s"

def draw_bandwidth_graph(frame, origin, size, max_value=None):
    """Draws the bandwidth usage graph with upload and download separated"""
    graph_w, graph_h = size
    if not bandwidth_history:
        return
    
    # Get colors from palette
    bg_color = COLOR_PALETTE['graph_bg']
    grid_color = COLOR_PALETTE['graph_grid']
    
    # Draw graph background
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), bg_color, -1)
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), COLOR_PALETTE['border'], 1)
    
    # Calculate max value for scaling if not provided
    if max_value is None:
        if not bandwidth_history:
            max_value = 100
        else:
            # Get max of total network usage
            max_value = max([total for total, _, _ in bandwidth_history]) * 1.2 or 100
    
    # Draw horizontal guidelines
    for i in range(1, 4):
        y = origin[1] + graph_h - int((i / 4) * graph_h)
        cv2.line(frame, (origin[0], y), (origin[0] + graph_w, y), grid_color, 1)
    
    # Plot download (recv) line
    download_points = []
    for i, (_, _, recv) in enumerate(bandwidth_history):
        x = origin[0] + int(i * (graph_w / max(60, len(bandwidth_history))))
        # Scale value to graph height
        y = origin[1] + graph_h - int((recv / max_value) * graph_h)
        # Ensure y is within the graph bounds
        y = max(origin[1], min(y, origin[1] + graph_h))
        download_points.append((x, y))
    
    # Plot upload (sent) line
    upload_points = []
    for i, (_, sent, _) in enumerate(bandwidth_history):
        x = origin[0] + int(i * (graph_w / max(60, len(bandwidth_history))))
        # Scale value to graph height
        y = origin[1] + graph_h - int((sent / max_value) * graph_h)
        # Ensure y is within the graph bounds
        y = max(origin[1], min(y, origin[1] + graph_h))
        upload_points.append((x, y))
    
    # Draw filled areas and lines for both upload and download
    if len(download_points) >= 2:
        # Download fill (green)
        download_fill = download_points.copy()
        download_fill.append((download_points[-1][0], origin[1] + graph_h))
        download_fill.append((download_points[0][0], origin[1] + graph_h))
        cv2.fillPoly(frame, [np.array(download_fill, dtype=np.int32)], COLOR_PALETTE['graph_fill3'])
        
        # Download line (green)
        cv2.polylines(frame, [np.array(download_points, dtype=np.int32)], False, COLOR_PALETTE['graph_line3'], 1)
    
    if len(upload_points) >= 2:
        # Upload fill (orange)
        upload_fill = upload_points.copy()
        upload_fill.append((upload_points[-1][0], origin[1] + graph_h))
        upload_fill.append((upload_points[0][0], origin[1] + graph_h))
        cv2.fillPoly(frame, [np.array(upload_fill, dtype=np.int32)], COLOR_PALETTE['graph_fill1'])
        
        # Upload line (orange)
        cv2.polylines(frame, [np.array(upload_points, dtype=np.int32)], False, COLOR_PALETTE['graph_line1'], 1)
    
    # Draw current values and labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    
    if bandwidth_history:
        # Get latest values
        total, upload, download = bandwidth_history[-1]
        
        # Display labels and values
        cv2.putText(frame, "Bandwidth", (origin[0], origin[1] - 5), font, font_scale, COLOR_PALETTE['text_medium'], 1)
        
        # Total bandwidth
        total_text = format_bandwidth(total)
        cv2.putText(frame, f"Total: {total_text}", (origin[0] + 5, origin[1] + 15), font, font_scale, COLOR_PALETTE['text_bright'], 1)
        
        # Upload
        upload_text = format_bandwidth(upload)
        cv2.putText(frame, f"UP: {upload_text}", (origin[0] + 5, origin[1] + 35), font, font_scale, COLOR_PALETTE['graph_line1'], 1)
        
        # Download
        download_text = format_bandwidth(download)
        cv2.putText(frame, f"DOWN: {download_text}", (origin[0] + 100, origin[1] + 35), font, font_scale, COLOR_PALETTE['graph_line3'], 1)

def draw_usage_graph(frame, data, origin, size, title, color=None, max_value=100):
    """Draws usage graphs (CPU/Memory) using the same style as bandwidth graph"""
    graph_w, graph_h = size
    
    # Use default color if none provided
    if color is None:
        color = COLOR_PALETTE['graph_line2']
    
    fill_color = COLOR_PALETTE['graph_fill2']
    
    # Draw graph background
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), COLOR_PALETTE['graph_bg'], -1)
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), COLOR_PALETTE['border'], 1)
    
    # Draw horizontal guidelines
    for i in range(1, 4):
        y = origin[1] + graph_h - int((i / 4) * graph_h)
        cv2.line(frame, (origin[0], y), (origin[0] + graph_w, y), COLOR_PALETTE['graph_grid'], 1)
    
    # Convert data queue to list
    graph_data = list(data)
    if not graph_data:
        return
    
    # Plot points
    points = []
    for i, val in enumerate(graph_data):
        x = origin[0] + int(i * (graph_w / max(60, len(graph_data))))
        y = origin[1] + graph_h - int((val / max_value) * graph_h)
        # Ensure y is within graph bounds
        y = max(origin[1], min(y, origin[1] + graph_h))
        points.append((x, y))
    
    if len(points) >= 2:
        # Draw fill
        fill_points = points.copy()
        fill_points.append((points[-1][0], origin[1] + graph_h))
        fill_points.append((points[0][0], origin[1] + graph_h))
        cv2.fillPoly(frame, [np.array(fill_points, dtype=np.int32)], fill_color)
        
        # Draw line
        cv2.polylines(frame, [np.array(points, dtype=np.int32)], False, color, 1)
    
    # Draw current value and title
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    
    cv2.putText(frame, title, (origin[0], origin[1] - 5), font, font_scale, COLOR_PALETTE['text_medium'], 1)
    
    if graph_data:
        value = graph_data[-1]
        value_text = f"{value:.1f}%"
        cv2.putText(frame, value_text, (origin[0] + 5, origin[1] + 15), font, font_scale, COLOR_PALETTE['text_bright'], 1)

def count_lines(filepath):
    with open(filepath, 'r') as f:
        return sum(1 for _ in f)

def download_ip2loc_db_if_not_exists():
    pass
    # Moved to the headinit file in tminus

def ip_to_int(ip_address):
    """Convert an IP address string to integer format for database lookups."""
    try:
        if not ip_address or ":" in ip_address:  # Skip empty or IPv6 addresses
            return 0
        # Convert IP string to integer
        return int(ipaddress.IPv4Address(ip_address))
    except Exception as e:
        logging.debug(f"Error converting IP {ip_address} to int: {e}")
        return 0

def load_ip2loc_db():
    ranges = []
    countries = []
    try:
        with open(DB_CSV, newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 4:  # Ensure row has the expected format
                    ip_from = int(row[0])
                    ip_to = int(row[1])
                    country = row[3]
                    ranges.append((ip_from, ip_to, country))
    except Exception as e:
        logging.error(f"Error loading IP database: {e}")
    return ranges

try:
    ip_database = load_ip2loc_db()
except Exception as e:
    download_ip2loc_db_if_not_exists()
    ip_database = load_ip2loc_db()

def get_geolocation(ip_address):
    """Get geolocation information for an IP address."""
    if not ip_address or ip_address == "Unknown":
        return "Unknown Location"
        
    # Check cache first
    if ip_address in geolocation_data:
        return geolocation_data[ip_address]

    try:
        # Extract just the IP if it contains a port
        if ":" in ip_address:
            ip_address = ip_address.split(":")[0]
            
        # Convert to integer for lookup
        ip_int = ip_to_int(ip_address)
        if ip_int == 0:
            return "Unknown Location"
            
        # Search through the database
        for ip_from, ip_to, country in ip_database:
            if ip_from <= ip_int <= ip_to:
                geolocation_data[ip_address] = country
                return country
    except Exception as e:
        logging.error(f"Geolocation lookup error for {ip_address}: {e}")

    geolocation_data[ip_address] = "Unknown Location"
    return "Unknown Location"

# Read from the files
def get_ip_range(filename, start, end):
    """Get a range of IP addresses from the file, with bounds checking."""
    try:
        with open(filename) as f:
            lines = [line.strip() for line in f if line.strip()]
        
        # Ensure start and end are valid
        start = max(1, start)  # Ensure start is at least 1
        end = min(len(lines) + 1, end)  # Ensure end doesn't exceed file length
        
        # Check for potential bounds errors
        if start > len(lines) or start > end:
            return []
        
        # Adjust for 1-based indexing to 0-based
        return lines[start - 1:end - 1]
    except Exception as e:
        logging.error(f"Error in get_ip_range: {e}")
        return []

def count_ips_in_file(filename):
    with open(filename) as f:
        return sum(1 for line in f if line.strip())

# Make the buttons work in the gui
def get_current_cursor_position():
    return pyautogui.position()

def check_in_bounding_box(point, top_left, bottom_right):
    return top_left[0] <= point[0] <= bottom_right[0] and top_left[1] <= point[1] <= bottom_right[1]

def check_if_in_button_area(point):
    def check_in_bounding_box(point, top_left, bottom_right):
        return top_left[0] <= point[0] <= bottom_right[0] and top_left[1] <= point[1] <= bottom_right[1]

    # 1 - page 1 button (Matrix View)
    # 2 - page 2 button (List View)
    # 3 - list view scroll up button
    # 4 - list view scroll down button
    # 5 - page 3 button (Map View) - new

    if check_in_bounding_box(point, [button_page_1_topleft_x, button_page_1_topleft_y], [button_page_1_bottomright_x, button_page_1_bottomright_y]):
        return 1
    if check_in_bounding_box(point, [button_page_2_topleft_x, button_page_2_topleft_y], [button_page_2_bottomright_x, button_page_2_bottomright_y]):
        return 2
    if check_in_bounding_box(point, [button_page_3_topleft_x, button_page_3_topleft_y], [button_page_3_bottomright_x, button_page_3_bottomright_y]):
        return 5  # Using 5 for Map View to avoid confusion with the scroll buttons (3 and 4)
    if check_in_bounding_box(point, [button_list_scrollup_topleft_x, button_list_scrollup_topleft_y], [button_list_scrollup_bottomright_x, button_list_scrollup_bottomright_y]):
        return 3
    if check_in_bounding_box(point, [button_list_scrolldn_topleft_x, button_list_scrolldn_topleft_y], [button_list_scrolldn_bottomright_x, button_list_scrolldn_bottomright_y]):
        return 4
    return 0

def show_popup(color="yellow", text="notext", duration=500):
    global popup_active, popup_queue
    
    if not isinstance(text, str):
        text = str(text)
    
    with popup_lock:
        # Instead of launching Tkinter windows, just add message to queue
        # that will be displayed directly in OpenCV
        popup_queue.append((text, color, time.time() + duration/1000.0))

def draw_popups_on_frame(frame):
    global popup_queue
    current_time = time.time()
    
    with popup_lock:
        # Only keep active popups
        active_popups = [(msg, color, end_time) for msg, color, end_time in popup_queue if end_time > current_time]
        popup_queue = deque(active_popups, maxlen=5)
        
        if not popup_queue:
            return frame
        
        # Create a copy of the frame to avoid modifying the original
        result = frame.copy()
        height, width = result.shape[:2]
        
        y_offset = height - 60
        for msg, color_name, _ in popup_queue:
            # Convert color name to BGR
            if color_name == "yellow":
                color = (0, 255, 255)
            elif color_name == "red":
                color = (0, 0, 255)
            else:
                color = (255, 255, 255)
            
            # Create popup box
            msg_size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            box_width = min(msg_size[0] + 20, width - 40)
            box_height = 40
            
            box_x = width - box_width - 20
            box_y = y_offset - box_height
            
            # Draw box with semi-transparency
            overlay = result.copy()
            cv2.rectangle(overlay, (box_x, box_y), (box_x + box_width, box_y + box_height), (40, 40, 40), -1)
            cv2.addWeighted(overlay, 0.7, result, 0.3, 0, result)
            
            # Draw text
            text_x = box_x + 10
            text_y = box_y + 30
            cv2.putText(result, msg, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            y_offset -= 50
        
        return result

def click_handler():
    global selected_page, current_list_position, selected_camera, working_cameras, selected_location_cluster

    try:
        current_mouse_location = get_current_cursor_position()
        button_reaction = check_if_in_button_area(current_mouse_location)

        # Only show popup for button clicks, not random clicks
        if button_reaction > 0:
            show_popup(text=f"Button {button_reaction} clicked")

        if button_reaction == 1:
            selected_page = 1  # Matrix View
        elif button_reaction == 2:
            selected_page = 2  # List View
        elif button_reaction == 5:
            selected_page = 3  # Map View
        elif button_reaction == 3:
            # Scroll up
            if current_list_position <= 0:
                show_popup(text="Top of list")
                current_list_position = 0
            else:
                current_list_position = current_list_position - view_list_scroll_step_size
        elif button_reaction == 4:
            # Scroll down
            max_position = max(0, len(working_cameras) - view_list_visible_address_count)
            if current_list_position >= max_position:
                show_popup(text="End of list")
                current_list_position = max_position
            else:
                current_list_position = current_list_position + view_list_scroll_step_size
        else:
            # Check if click was on an item in the list view
            if selected_page == 2:
                # Calculate list item areas and check for click
                list_top = min(windowactivity_leftactivity_topleft_y + 80, get_raw_screen_resolution()[1] - 200)
                row_height = min(90, (get_raw_screen_resolution()[1] - list_top - 100) // 10)
                list_item_click = check_if_list_item_clicked(current_mouse_location, list_top, row_height)
                if list_item_click >= 0:
                    # Get the actual camera from the working cameras list
                    idx = current_list_position + list_item_click
                    if idx < len(working_cameras):
                        selected_camera = working_cameras[idx]
                        show_popup(text=f"Selected camera: {selected_camera}")
            # Check if click was on a location cluster in Map View
            elif selected_page == 3:
                # Calculate cluster box parameters
                screen_w = get_screen_x()
                grid_left = 50
                grid_top = 150
                grid_width = screen_w - 100
                box_height = 120
                box_margin = 20
                box_width = (grid_width - box_margin*3) // 3  # 3 boxes per row
                
                # Check which cluster was clicked
                clicked_cluster = None
                row = 0
                col = 0
                max_cols = 3
                
                for location in location_clusters.keys():
                    # Calculate box position
                    box_x = grid_left + col * (box_width + box_margin)
                    box_y = grid_top + row * (box_height + box_margin)
                    
                    # Check if click was within this box
                    if (box_x <= current_mouse_location[0] <= box_x + box_width and
                        box_y <= current_mouse_location[1] <= box_y + box_height):
                        clicked_cluster = location
                        break
                    
                    # Move to next position in grid
                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1
                
                # Handle cluster selection
                if clicked_cluster:
                    if clicked_cluster == selected_location_cluster:
                        # Deselect if already selected
                        selected_location_cluster = None
                        show_popup(text=f"Deselected cluster: {clicked_cluster}")
                    else:
                        # Select the new cluster
                        selected_location_cluster = clicked_cluster
                        show_popup(text=f"Selected cluster: {clicked_cluster}")
                        
                        # Count cameras in this cluster
                        camera_count = len(location_clusters[clicked_cluster]['cameras'])
                        active_count = location_clusters[clicked_cluster]['active_count']
                        show_popup(text=f"Showing {camera_count} cameras ({active_count} active)")
    except Exception as e:
        logging.error(f"Error in click_handler: {e}")
        show_popup(text=f"Click error: {str(e)[:30]}", color="red")

def check_if_list_item_clicked(point, list_top, row_height):
    # Check if the click is within the list view area
    list_left = min(windowactivity_leftactivity_topleft_x + 20, get_raw_screen_resolution()[0] - 300)
    list_right = min(windowactivity_leftactivity_bottomright_x - 20, get_raw_screen_resolution()[0] - 100)
    list_bottom = list_top + (view_list_visible_address_count * row_height)
    
    # First check if we're in the bounds of the entire list area
    if point[0] < list_left or point[0] > list_right or point[1] < list_top or point[1] > list_bottom:
        return -1
    
    # Calculate row index based on Y position relative to list_top
    # This is more precise than checking each row individually
    relative_y = point[1] - list_top
    row_index = int(relative_y / row_height)
    
    # Ensure we're within the visible row count
    if 0 <= row_index < view_list_visible_address_count:
        return row_index
    
    return -1

def start_on_click(target_func):
    triggered = [False]

    def on_click(x, y, button, pressed):
        if pressed:
            if not triggered[0]:
                triggered[0] = True
                threading.Thread(target=target_func, daemon=True).start()
        else:
            triggered[0] = False

    listener = mouse.Listener(on_click=on_click)
    listener.start()
    return listener

def track_mouse_position():
    """Track the mouse position for use with tooltips."""
    global mouse_position

    def on_move(x, y):
        global mouse_position
        mouse_position = (x, y)

    listener = mouse.Listener(on_move=on_move)
    listener.start()
    return listener

def format_uptime(timestamp):
    """Format time difference in a human-readable way"""
    now = time.time()
    diff = now - timestamp
    
    if diff < 60:
        return f"{int(diff)}s"
    elif diff < 3600:
        return f"{int(diff // 60)}m {int(diff % 60)}s"
    elif diff < 86400:
        hours = int(diff // 3600)
        minutes = int((diff % 3600) // 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(diff // 86400)
        hours = int((diff % 86400) // 3600)
        return f"{days}d {hours}h"

def get_screen_x():
    return get_raw_screen_resolution()[0]

def get_screen_y():
    return get_raw_screen_resolution()[1]

def get_cpu_usage():
    return psutil.cpu_percent(interval=1)

def is_jpg_poll_stream(url):
    return url.endswith('.jpg') or '.jpg?' in url or '.cgi' in url

def add_custom_params(url):
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path.lower()
    for key, param in default_stream_params.items():
        if key in path:
            if "?" in url:
                if not any(param.startswith(f"{x}=") for x in param.split("&")):
                    url += f"&{param.strip('?')}"
            else:
                url += f"?{param.strip('?')}"
            break
    return url

def extract_ip_from_url(url):
    """Extract just the IP or hostname from a URL."""
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc:
        return parsed.netloc

    # If no scheme, the hostname might be in the path
    parts = url.split('/')
    if parts:
        return parts[0].split(':')[0]  # Remove port if present

    return url

def read_stream(input_id, frames, borders, lock):
    try:
        def should_poll_jpeg(url):
            lower = url.lower()

            return any(p in lower for p in [
                "/cgi-bin/camera",
                "/snapshotjpeg",
                "/oneshotimage1",
                "/oneshotimage2",
                "/oneshotimage3",
                "/getoneshot",
                "/nphmotionjpeg",
                "/cam1ir",
                "/cam1color",
                "/image",
                ".jpg",
                ".jpeg"
            ])

        # Store metadata about the camera
        with lock:
            if input_id not in camera_metadata:
                camera_metadata[input_id] = {
                    "first_seen": time.time(),
                    "frames_received": 0,
                    "last_frame_time": 0,
                    "fps": 0,
                    "resolution": "Unknown",
                    "stream_type": "Unknown",
                    "endpoint": "Unknown",
                    "connection_attempts": 0,
                    "connection_failures": 0,
                    "last_success": 0
                }
            
            # Determine stream type
            if input_id.startswith("rtsp://"):
                camera_metadata[input_id]["stream_type"] = "RTSP"
            elif should_poll_jpeg(input_id):
                camera_metadata[input_id]["stream_type"] = "JPEG Poll"
            else:
                camera_metadata[input_id]["stream_type"] = "HTTP"
            
            # Extract endpoint
            endpoint = input_id.split("/")[-1] if "/" in input_id else "root"
            camera_metadata[input_id]["endpoint"] = endpoint

        if input_id.startswith("rtsp://") or input_id.startswith("http://"):
            full_url = input_id

        elif any(x in input_id.lower() for x in [
            "/cam", "/cgi-bin", "/snapshotjpeg", "/oneshotimage", "/getoneshot", "/nphmotionjpeg",
            "/cam1ir", "/cam1color", ".jpg", ".jpeg", ".mjpg", ".mjpeg"
        ]):

            full_url = f"http://{input_id}" if not input_id.startswith("http") else input_id
        else:
            print(f"[{input_id}] Rejected: Invalid stream identifier")
            return

        full_url = add_custom_params(full_url)
        color = tuple(random.randint(64, 255) for _ in range(3))

        with lock:
            borders[input_id] = color

        if should_poll_jpeg(full_url):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Connection": "close"
            }
            print(f"[{input_id}] Starting JPEG poll stream: {full_url}")
            last_fps_time = time.time()
            frames_count = 0
            
            max_consecutive_failures = 5
            consecutive_failures = 0            
            min_timeout = 1.0
            max_timeout = 3.0
            current_timeout = min_timeout
            
            while True:
                try:
                    # Mark connection attempt
                    with lock:
                        camera_metadata[input_id]["connection_attempts"] += 1
                        
                    camera_metadata[input_id]["connection_attempts"] += 1
                    
                    req = urllib.request.Request(full_url, headers=headers)
                    
                    # Use a shorter timeout for faster failure detection
                    with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                        # Read with a size limit to prevent extremely large images
                        img_data = resp.read(5 * 1024 * 1024)  # 5MB limit (reduced from 10MB)
                        
                        # Validate we actually got data
                        if not img_data:
                            consecutive_failures += 1
                            raise ValueError("Empty image data received")
                            
                        img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                        
                        # Use IMREAD_COLOR to ensure consistent 3-channel output
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                        if frame is not None and frame.size > 0:
                            # Verify frame dimensions are reasonable
                            if frame.shape[0] > 0 and frame.shape[1] > 0 and frame.shape[2] == 3:
                                # Reset failure counter on success
                                consecutive_failures = 0
                                
                                # After success, slightly decrease timeout for future requests
                                current_timeout = max(min_timeout, current_timeout * 0.9)
                                
                                # Mark success
                                with lock:
                                    camera_metadata[input_id]["last_success"] = time.time()
                                
                                # Resize larger frames to reduce memory usage
                                if frame.shape[0] > 1080 or frame.shape[1] > 1920:
                                    # Maintain aspect ratio while reducing size
                                    if frame.shape[1] > frame.shape[0]:  # Landscape
                                        scale = min(1.0, 1920 / frame.shape[1])
                                    else:  # Portrait
                                        scale = min(1.0, 1080 / frame.shape[0])
                                        
                                    new_width = int(frame.shape[1] * scale)
                                    new_height = int(frame.shape[0] * scale)
                                    frame = cv2.resize(frame, (new_width, new_height), 
                                                      interpolation=cv2.INTER_AREA)
                                
                                # Safely copy the frame to prevent memory issues
                                safe_frame = frame.copy()
                                with lock:
                                    frames[input_id] = safe_frame
                                    
                                    # Update metadata
                                    camera_metadata[input_id]["frames_received"] += 1
                                    camera_metadata[input_id]["last_frame_time"] = time.time()
                                    camera_metadata[input_id]["resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
                                    
                                    # Calculate FPS
                                    frames_count += 1
                                    now = time.time()
                                    time_diff = now - last_fps_time
                                    if time_diff >= 5:  # Update FPS every 5 seconds
                                        camera_metadata[input_id]["fps"] = round(frames_count / time_diff, 1)
                                        frames_count = 0
                                        last_fps_time = now
                                
                                # Add adaptive sleep based on FPS - slower cameras get more sleep
                                fps = camera_metadata[input_id]["fps"]
                                if fps > 0:
                                    # Aim for around target_fps but never sleep more than max_sleep_time
                                    target_fps = 5  # Reasonable target for most cameras
                                    max_sleep_time = 0.5  # Maximum sleep time in seconds
                                    
                                    if fps > target_fps:
                                        sleep_time = min(max_sleep_time, 1.0 / target_fps - 1.0 / fps)
                                        if sleep_time > 0.01:  # Only sleep if it's significant
                                            time.sleep(sleep_time)
                            else:
                                consecutive_failures += 1
                                print(f"[{input_id}] Invalid frame dimensions: {frame.shape}")
                        else:
                            consecutive_failures += 1
                            print(f"[{input_id}] Failed to decode image")
                            
                except Exception as e:
                    consecutive_failures += 1
                    with lock:
                        camera_metadata[input_id]["connection_failures"] += 1
                    
                    # Increase timeout on failure to avoid hammering non-responsive cameras
                    current_timeout = min(max_timeout, current_timeout * 1.2)
                    
                    print(f"[{input_id}] JPEG poll error: {e}")
                    
                    # Progressive backoff sleep based on consecutive failures
                    # This prevents flooding non-responsive cameras with requests
                    backoff_time = min(5.0, 0.1 * (2 ** min(consecutive_failures, 5)))
                    time.sleep(backoff_time)
                    
                # If we've reached max consecutive failures, take a longer pause
                # and then try again with reset counter
                if consecutive_failures >= max_consecutive_failures:
                    print(f"[{input_id}] Too many consecutive failures, taking a break...")
                    time.sleep(5.0)  # Take a longer break
                    consecutive_failures = 0  # Reset the counter and try again
                    
    except Exception as e:
        print(f"[{input_id}] Stream error: {e}")
        time.sleep(1.0)

def add_logo(full_grid):
    logo_path = "sf-logo-long-plain.webp"
    if not os.path.exists(logo_path):
        logo_url = "https://raw.githubusercontent.com/Silverflag/sf-clearnet-v2/refs/heads/main/assets/logos/sf-logo-long-plain.webp"
        logo = requests.get(logo_url).content
        with open(logo_path, 'wb') as f:
            f.write(logo)

    logo_img = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
    logo_height = 30
    logo_width = int(logo_img.shape[1] * (logo_height / logo_img.shape[0]))
    logo_resized = cv2.resize(logo_img, (logo_width, logo_height), interpolation=cv2.INTER_AREA)

    if logo_resized.shape[2] == 4:
        alpha = logo_resized[:, :, 3] / 255.0
        logo_rgb = logo_resized[:, :, :3]
        y1 = 5
        y2 = y1 + logo_resized.shape[0]
        x2 = full_grid.shape[1] - 50
        x1 = x2 - logo_resized.shape[1]

        roi = full_grid[y1:y2, x1:x2]
        for c in range(3):
            roi[:, :, c] = (alpha * logo_rgb[:, :, c] + (1 - alpha) * roi[:, :, c]).astype(full_grid.dtype)
        full_grid[y1:y2, x1:x2] = roi
    else:
        full_grid[5:5 + logo_resized.shape[0], -logo_resized.shape[1] - 50:-50] = logo_resized
    return full_grid

def draw_usage_graph(frame, data, origin, size, title, color=None, max_value=100):
    """Draws usage graphs (CPU/Memory) using the same style as bandwidth graph"""
    graph_w, graph_h = size
    
    # Use default color if none provided
    if color is None:
        color = COLOR_PALETTE['graph_line2']
    
    fill_color = COLOR_PALETTE['graph_fill2']
    
    # Draw graph background
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), COLOR_PALETTE['graph_bg'], -1)
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), COLOR_PALETTE['border'], 1)
    
    # Draw horizontal guidelines
    for i in range(1, 4):
        y = origin[1] + graph_h - int((i / 4) * graph_h)
        cv2.line(frame, (origin[0], y), (origin[0] + graph_w, y), COLOR_PALETTE['graph_grid'], 1)
    
    # Convert data queue to list
    graph_data = list(data)
    if not graph_data:
        return
    
    # Plot points
    points = []
    for i, val in enumerate(graph_data):
        x = origin[0] + int(i * (graph_w / max(60, len(graph_data))))
        y = origin[1] + graph_h - int((val / max_value) * graph_h)
        # Ensure y is within graph bounds
        y = max(origin[1], min(y, origin[1] + graph_h))
        points.append((x, y))
    
    if len(points) >= 2:
        # Draw fill
        fill_points = points.copy()
        fill_points.append((points[-1][0], origin[1] + graph_h))
        fill_points.append((points[0][0], origin[1] + graph_h))
        cv2.fillPoly(frame, [np.array(fill_points, dtype=np.int32)], fill_color)
        
        # Draw line
        cv2.polylines(frame, [np.array(points, dtype=np.int32)], False, color, 1)
    
    # Draw current value and title
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    
    cv2.putText(frame, title, (origin[0], origin[1] - 5), font, font_scale, COLOR_PALETTE['text_medium'], 1)
    
    if graph_data:
        value = graph_data[-1]
        value_text = f"{value:.1f}%"
        cv2.putText(frame, value_text, (origin[0] + 5, origin[1] + 15), font, font_scale, COLOR_PALETTE['text_bright'], 1)

# Improved arrow symbols for buttons
UP_ARROW = "▲"
DOWN_ARROW = "▼"
LEFT_ARROW = "◄"
RIGHT_ARROW = "►"
PLUS_SYMBOL = "+"
MINUS_SYMBOL = "-"

# Layout parameters for better organization
def layout_frames(frames_dict, borders_dict, labels_dict, selected_page, inputs):
    global working_cameras
    global right_panel_left, right_panel_right, right_panel_top, right_panel_bottom
    global camera_view_height, camera_view_top, camera_view_bottom
    global info_section_top, info_section_bottom, info_section_height
    global right_activity_left, right_activity_right
    global mouse_position, hover_tooltip_active, hover_tooltip_data
    global selected_location_cluster
    
    # Update working cameras list - all camera IPs that have valid frames
    working_cameras = [cam_id for cam_id, frame in frames_dict.items() 
                      if frame is not None and frame.size > 0 and len(frame.shape) == 3]
    
    # ensure that the frame exists just incase it's somehow editted before it's ready
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    
    # Get frame dimensions
    height, width = frame.shape[:2]
    resized_height, resized_width = height, width
    
    if selected_page == 1:
        global last_update_time
        if time.time() - last_update_time >= 1:
            cpu_usage_history.append(psutil.cpu_percent())
            mem_usage_history.append(min(psutil.Process().memory_info().rss / psutil.virtual_memory().total * 100, 100))
            last_update_time = time.time()
        
        # Safe access to frames dictionary
        try:
            frames = list(frames_dict.items())
            count = len(frames)
        except Exception as e:
            logging.error(f"Error accessing frames: {e}")
            count = 0
            frames = []
            
        if count == 0:
            object = np.zeros((1080, 1920, 3), dtype=np.uint8)
            object[:] = COLOR_PALETTE['background_dark']

            message_no_cameras = "No cameras here (yet)"
            message_no_cameras_hint = "Wait for some streams to load first"

            cv2.putText(object, message_no_cameras, (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_PALETTE['text_bright'], 2)
            cv2.putText(object, message_no_cameras_hint, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_PALETTE['text_medium'], 2)
            cv2.putText(object, ":(", (60, 230), cv2.FONT_HERSHEY_SIMPLEX, 4.9, COLOR_PALETTE['text_bright'], 8)

            return object

        cols = int(np.ceil(np.sqrt(count)))
        rows = int(np.ceil(count / cols))

        screen_w = get_raw_screen_resolution()[0]
        screen_h = get_raw_screen_resolution()[1]

        cell_w = screen_w // cols
        cell_h = screen_h // rows

        grid_rows = []

        # Track which camera the mouse is hovering over for tooltip display
        hover_tooltip_active = False
        current_mouse_pos = mouse_position
        hovered_camera = None
        hovered_cell_coords = None

        for r in range(rows):
            row_imgs = []
            for c in range(cols):
                i = r * cols + c
                if i >= count:
                    blank = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
                    row_imgs.append(blank)
                    continue

                url, frame = frames[i]
                
                # Skip any empty or invalid frames
                if frame is None or frame.size == 0 or len(frame.shape) < 2:
                    blank = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
                    row_imgs.append(blank)
                    continue

                # Safe resize to avoid buffer overflow
                try:
                    # Create a copy to avoid modifying the original frame
                    frame_copy = frame.copy()
                    
                    # Calculate cell position in global coordinates for mouse hover detection
                    cell_x1 = c * cell_w + 40  # Add border offset
                    cell_y1 = r * cell_h + 40  # Add border offset
                    cell_x2 = cell_x1 + cell_w
                    cell_y2 = cell_y1 + cell_h
                    
                    # Check if mouse is hovering over this cell
                    mouse_x, mouse_y = current_mouse_pos
                    if cell_x1 <= mouse_x <= cell_x2 and cell_y1 <= mouse_y <= cell_y2:
                        hovered_camera = url
                        hovered_cell_coords = (cell_x1, cell_y1, cell_w, cell_h)
                    
                    # Check for valid dimensions before resizing
                    if cell_w <= 6 or cell_h <= 6:
                        frame = np.zeros((max(1, cell_h), max(1, cell_w), 3), dtype=np.uint8)
                    else:
                        try:
                            # Create a safe copy with known good dimensions
                            safe_frame = np.ascontiguousarray(frame_copy)
                            frame = cv2.resize(safe_frame, (max(1, cell_w), max(1, cell_h)))
                        except Exception as e:
                            print(f"Resize error: {e}")
                            frame = np.zeros((max(1, cell_h), max(1, cell_w), 3), dtype=np.uint8)
                except Exception as e:
                    print(f"Error resizing frame for {url}: {e}")
                    frame = np.zeros((max(1, cell_h), max(1, cell_w), 3), dtype=np.uint8)
                
                # No borders or labels in matrix view, just pure camera feeds
                row_imgs.append(frame)
                
            row = np.hstack(row_imgs)
            grid_rows.append(row)

        full_grid = np.vstack(grid_rows)
        full_grid = cv2.copyMakeBorder(full_grid, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=COLOR_PALETTE['background_medium'])
        
        # If a camera is being hovered over, prepare tooltip data
        if hovered_camera:
            ip_address = extract_ip_from_url(hovered_camera)
            location = get_geolocation(ip_address)
            
            hover_tooltip_active = True
            hover_tooltip_data = {
                'camera': hovered_camera,
                'ip': ip_address,
                'location': location,
                'position': current_mouse_pos
            }
            
            # Get additional metadata about the camera if available
            meta = camera_metadata.get(hovered_camera, {})
            resolution = meta.get("resolution", "Unknown")
            fps = meta.get("fps", 0)
            stream_type = meta.get("stream_type", "Unknown")
            
            # Create an enhanced tooltip with more information
            tooltip_lines = [
                f"IP: {ip_address}",
                f"Location: {location}",
            ]
            
            # Add resolution and stream type if available
            if resolution != "Unknown":
                tooltip_lines.append(f"Resolution: {resolution}")
            if stream_type != "Unknown":
                tooltip_lines.append(f"Type: {stream_type}")
            if fps > 0:
                tooltip_lines.append(f"FPS: {fps}")
                
            # Join the lines with newlines for multi-line tooltip
            tooltip_text = "\n".join(tooltip_lines)
            
            # Draw the tooltip
            full_grid = draw_tooltip(full_grid, tooltip_text, current_mouse_pos)

    elif selected_page == 2:
        # Build the initial frame (again??)
        screen_w, screen_h = get_screen_x(), get_screen_y()
        full_grid = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        full_grid[:] = COLOR_PALETTE['background_dark']  # Darker background

        # IDFK put them at the top
        resized_height, resized_width = full_grid.shape[:2]

        # Get the right panel dimensions
        right_panel_top = windowactivity_rightactivity_topleft_y
        right_panel_left = min(windowactivity_rightactivity_topleft_x, get_raw_screen_resolution()[0] - 200)
        right_panel_right = min(windowactivity_rightactivity_bottomright_x, get_raw_screen_resolution()[0] - 50)
        right_panel_bottom = min(windowactivity_rightactivity_bottomright_y, get_raw_screen_resolution()[1] - 50)

        # Left panel - camera list - dark blue-gray
        left_activity_right = min(windowactivity_leftactivity_bottomright_x, resized_width - 100)
        left_activity_bottom = min(windowactivity_leftactivity_bottomright_y, resized_height - 50)
        left_panel_width = int(resized_width * 0.4)

        # Right panel - camera view - dark reddish
        right_activity_left = left_activity_right + 20  # Small gap between panels
        right_activity_right = min(windowactivity_rightactivity_bottomright_x, resized_width - 50)
        right_activity_bottom = min(windowactivity_rightactivity_bottomright_y, resized_height - 50)

        # Section labels
        section_label_font = cv2.FONT_HERSHEY_SIMPLEX
        section_label_scale = 0.6

        
        # Make sure we use dimensions that won't cause buffer overflows
        scale_factor = min(1.0, resized_height / 480)
        font_scale = max(0.3, min(0.55 * scale_factor, 0.7))
        font_thickness = 1
        font = cv2.FONT_HERSHEY_SIMPLEX
        small_font_scale = font_scale * 0.8

        # Draw the main activity area - Dark gray
        activity_area_top = min(windowactivity_topleft_y, resized_height - 100)
        activity_area_bottom = min(windowactivity_bottomright_y, resized_height - 50)
        activity_area_left = min(windowactivity_topleft_x, resized_width - 100)
        activity_area_right = min(windowactivity_bottomright_x, resized_width - 50)

        
        right_panel_height = right_panel_bottom - right_panel_top
        camera_view_height = int(right_panel_height * 0.6)
        camera_view_top = right_panel_top
        camera_view_bottom = camera_view_top + camera_view_height

        # Info section
        info_section_height = int(right_panel_height * 0.2)
        info_section_top = camera_view_bottom + 10
        info_section_bottom = info_section_top + info_section_height - 10

        cv2.rectangle(
            full_grid,
            (activity_area_left, activity_area_top),
            (activity_area_right, activity_area_bottom),
            COLOR_PALETTE['background_medium'],
            -1
        )


        
        cv2.rectangle(
            full_grid,
            (windowactivity_leftactivity_topleft_x, windowactivity_leftactivity_topleft_y),
            (left_activity_right, left_activity_bottom),
            COLOR_PALETTE['background_medium'],  # Dark blue-gray
            -1
        )
        

        
        cv2.rectangle(
            full_grid,
            (right_activity_left, windowactivity_rightactivity_topleft_y),
            (right_activity_right, right_activity_bottom),
            COLOR_PALETTE['accent_tertiary'],  # Dark reddish
            -1
        )
        
        # Add section dividers
        cv2.line(full_grid, 
                (right_activity_left, camera_view_bottom), 
                (right_activity_right, camera_view_bottom), 
                COLOR_PALETTE['divider'], 2)
        
        cv2.line(full_grid, 
                (right_activity_left, info_section_bottom), 
                (right_activity_right, info_section_bottom), 
                COLOR_PALETTE['divider'], 2)
        
        cv2.putText(full_grid, "Camera View", 
                   (right_activity_left + 20, camera_view_top + 25), 
                   section_label_font, section_label_scale, COLOR_PALETTE['text_medium'], 1)
        
        cv2.putText(full_grid, "Camera Details", 
                   (right_activity_left + 20, info_section_top + 25), 
                   section_label_font, section_label_scale, COLOR_PALETTE['text_medium'], 1)

        # Set up list view parameters with bounds checking
        list_left = min(windowactivity_leftactivity_topleft_x + 20, left_activity_right - 300)
        list_top = min(windowactivity_leftactivity_topleft_y + 80, resized_height - 200)
        row_height = min(120, (resized_height - list_top - 100) // 8)  # Increased height for more info
        preview_size = min(80, row_height - 10)
        spacing = 10

        # Header with improved spacing to avoid text overlap
        header_y = min(list_top - 30, resized_height - 100)
        header_bg_y1 = header_y - 25
        header_bg_y2 = header_y + 5
        if header_bg_y1 > 0 and header_bg_y2 < resized_height:
            # Header background
            overlay = full_grid.copy()
            cv2.rectangle(overlay, 
                         (windowactivity_leftactivity_topleft_x, header_bg_y1), 
                         (left_activity_right, header_bg_y2), 
                         COLOR_PALETTE['background_light'], -1)
            cv2.addWeighted(overlay, 0.7, full_grid, 0.3, 0, full_grid)
        
        # Define column positions with improved spacing
        col1_x = list_left + preview_size + spacing
        col2_x = col1_x + 200  # Shortened to avoid overlap
        col3_x = col2_x + 140  # Shortened to avoid overlap
        col4_x = col3_x + 110  # Shortened to avoid overlap
        col5_x = col4_x + 110  # Position for uptime
        
        # Column headers
        if header_y > 0:
            cv2.putText(full_grid, "Preview", (list_left, header_y), font, small_font_scale, COLOR_PALETTE['text_bright'], font_thickness)
            cv2.putText(full_grid, "Camera Address", (col1_x, header_y), font, small_font_scale, COLOR_PALETTE['text_bright'], font_thickness)
            cv2.putText(full_grid, "Location", (col2_x, header_y), font, small_font_scale, COLOR_PALETTE['text_bright'], font_thickness)
            cv2.putText(full_grid, "Type", (col3_x, header_y), font, small_font_scale, COLOR_PALETTE['text_bright'], font_thickness)
            cv2.putText(full_grid, "Resolution", (col4_x, header_y), font, small_font_scale, COLOR_PALETTE['text_bright'], font_thickness)
            cv2.putText(full_grid, "Uptime", (col5_x, header_y), font, small_font_scale, COLOR_PALETTE['text_bright'], font_thickness)
        
        # Use working_cameras list - slice for current page
        start_idx = current_list_position
        end_idx = start_idx + view_list_visible_address_count
        
        # Calculate how many rows we can safely display
        max_rows = min(view_list_visible_address_count, (resized_height - list_top - 50) // row_height)
        visible_ips = working_cameras[start_idx:start_idx + max_rows] if working_cameras else []

        # Highlight the selected camera
        global selected_camera

        for idx, input_id in enumerate(visible_ips):
            y = list_top + idx * row_height
            
            # Skip if we're out of bounds
            if y + preview_size > resized_height:
                break
                
            x = list_left
            
            # Alternate row backgrounds for better readability 
            row_bg_y1 = y - 5
            row_bg_y2 = y + row_height - 5
            
            if row_bg_y1 >= 0 and row_bg_y2 < resized_height:
                overlay = full_grid.copy()
                bg_color = COLOR_PALETTE['background_dark'] if idx % 2 == 0 else COLOR_PALETTE['background_medium']  # Alternate dark colors
                cv2.rectangle(overlay, 
                             (windowactivity_leftactivity_topleft_x, row_bg_y1), 
                             (left_activity_right, row_bg_y2), 
                             bg_color, -1)
                cv2.addWeighted(overlay, 0.5, full_grid, 0.5, 0, full_grid)

            # Highlight selected camera's row
            if input_id == selected_camera:
                sel_y1 = y - 5
                sel_y2 = y + row_height - 5
                sel_x1 = windowactivity_leftactivity_topleft_x
                sel_x2 = left_activity_right
                
                if sel_y1 >= 0 and sel_x1 >= 0 and sel_y2 < resized_height and sel_x2 < resized_width:
                    overlay = full_grid.copy()
                    cv2.rectangle(overlay, (sel_x1, sel_y1), (sel_x2, sel_y2), COLOR_PALETTE['accent_primary'], -1)  # Highlight
                    cv2.addWeighted(overlay, 0.4, full_grid, 0.6, 0, full_grid)

            # Display preview frame with safety checks
            preview_frame = frames_dict.get(input_id)
            if preview_frame is not None:
                try:
                    if preview_frame.size > 0 and preview_frame.shape[0] > 0 and preview_frame.shape[1] > 0:
                        preview_frame_copy = preview_frame.copy()
                        if (y + preview_size <= resized_height and 
                            x + preview_size <= resized_width and 
                            y >= 0 and x >= 0):
                            thumb = cv2.resize(preview_frame_copy, (preview_size, preview_size))
                            full_grid[y:y+preview_size, x:x+preview_size] = thumb
                        else:
                            if (y + 10 < resized_height and x + 10 < resized_width and 
                                y + preview_size - 10 < resized_height and x + preview_size - 10 < resized_width):
                                cv2.rectangle(full_grid, (x, y), (x + preview_size, y + preview_size), COLOR_PALETTE['background_light'], -1)
                            
                except Exception as e:
                    print(f"Error handling preview frame for {input_id}: {e}")
                    if (y < resized_height and x < resized_width and 
                        y + preview_size < resized_height and x + preview_size < resized_width):
                        cv2.rectangle(full_grid, (x, y), (x + preview_size, y + preview_size), COLOR_PALETTE['background_light'], -1)
            else:
                if (y < resized_height and x < resized_width and 
                    y + preview_size < resized_height and x + preview_size < resized_width):
                    cv2.rectangle(full_grid, (x, y), (x + preview_size, y + preview_size), COLOR_PALETTE['background_light'], -1)

            ip_address = extract_ip_from_url(input_id)
            
            meta = camera_metadata.get(input_id, {})
            stream_type = meta.get("stream_type", "Unknown")
            endpoint = meta.get("endpoint", "Unknown")
            resolution = meta.get("resolution", "Unknown")
            fps = meta.get("fps", 0)
            first_seen = meta.get("first_seen", time.time())
            frames_received = meta.get("frames_received", 0)
            
            # Calculate uptime
            uptime_str = format_uptime(first_seen)
            
            # Get geolocation data
            location = get_geolocation(ip_address)
            
            # Row 1 - main info with smaller font to prevent overlap
            text_y_1 = y + 20
            if text_y_1 < resized_height:
                # IP address
                if col1_x < resized_width:
                    ip_display = ip_address
                    if len(ip_display) > 20:  # Truncate more aggressively
                        ip_display = ip_display[:17] + "..."
                    cv2.putText(full_grid, ip_display, (col1_x, text_y_1), font, small_font_scale, COLOR_PALETTE['text_bright'], 1)
                
                # Location
                if col2_x < resized_width:
                    loc_display = location[:15] + "..." if len(location) > 18 else location
                    cv2.putText(full_grid, loc_display, (col2_x, text_y_1), font, small_font_scale, COLOR_PALETTE['text_bright'], 1)
                
                # Stream type
                if col3_x < resized_width:
                    type_text = f"{stream_type}"[:12]
                    cv2.putText(full_grid, type_text, (col3_x, text_y_1), font, small_font_scale, COLOR_PALETTE['text_bright'], 1)
                
                # Resolution
                if col4_x < resized_width:
                    res_text = resolution[:10]
                    cv2.putText(full_grid, res_text, (col4_x, text_y_1), font, small_font_scale, COLOR_PALETTE['text_bright'], 1)
                
                # Uptime
                if col5_x < resized_width:
                    cv2.putText(full_grid, uptime_str, (col5_x, text_y_1), font, small_font_scale, COLOR_PALETTE['text_bright'], 1)
            
            # Row 2 - additional details with smaller font
            text_y_2 = y + 50
            if text_y_2 < resized_height:
                # Camera ID/shorter version
                if col1_x < resized_width:
                    cv2.putText(full_grid, f"ID: {input_id.split('/')[-1]}", (col1_x, text_y_2), font, 0.5, COLOR_PALETTE['text_medium'], 1)
                
                # Frames info
                if col2_x < resized_width:
                    cv2.putText(full_grid, f"Frames: {frames_received}", (col2_x, text_y_2), font, 0.5, COLOR_PALETTE['text_medium'], 1)
                
                # Endpoint
                if col3_x < resized_width:
                    end_text = endpoint[:10]
                    cv2.putText(full_grid, end_text, (col3_x, text_y_2), font, 0.5, COLOR_PALETTE['text_medium'], 1)
                
                # FPS
                if col4_x < resized_width:
                    fps_text = f"FPS: {fps}"
                    cv2.putText(full_grid, fps_text, (col4_x, text_y_2), font, 0.5, COLOR_PALETTE['text_medium'], 1)
                
                # First seen (shortened)
                if col5_x < resized_width:
                    time_str = time.strftime("%H:%M", time.localtime(first_seen))
                    cv2.putText(full_grid, f"@{time_str}", (col5_x, text_y_2), font, 0.5, COLOR_PALETTE['text_medium'], 1)

        # Add in the scroll button rectangles with proper arrows
        # Scroll Up button with improved styling
        button_color = COLOR_PALETTE['button_normal']
        cv2.rectangle(full_grid, 
                     (button_list_scrollup_topleft_x, button_list_scrollup_topleft_y),
                     (button_list_scrollup_bottomright_x, button_list_scrollup_bottomright_y), 
                     button_color, -1)
        # Add a button border
        cv2.rectangle(full_grid, 
                     (button_list_scrollup_topleft_x, button_list_scrollup_topleft_y),
                     (button_list_scrollup_bottomright_x, button_list_scrollup_bottomright_y), 
                     COLOR_PALETTE['border'], 1)
        # Up arrow symbol
        cv2.putText(full_grid, UP_ARROW, 
                    (button_list_scrollup_topleft_x + 17, button_list_scrollup_topleft_y + 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, COLOR_PALETTE['text_bright'], 2)

        # Scroll Down button with improved styling
        cv2.rectangle(full_grid, 
                     (button_list_scrolldn_topleft_x, button_list_scrolldn_topleft_y),
                     (button_list_scrolldn_bottomright_x, button_list_scrolldn_bottomright_y), 
                     button_color, -1)
        # Add a button border
        cv2.rectangle(full_grid, 
                     (button_list_scrolldn_topleft_x, button_list_scrolldn_topleft_y),
                     (button_list_scrolldn_bottomright_x, button_list_scrolldn_bottomright_y), 
                     COLOR_PALETTE['border'], 1)
        # Down arrow symbol
        cv2.putText(full_grid, DOWN_ARROW, 
                    (button_list_scrolldn_topleft_x + 17, button_list_scrolldn_topleft_y + 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, COLOR_PALETTE['text_bright'], 2)
        
        # Display local time at bottom right
        current_time = time.strftime("%H:%M:%S", time.localtime())
        time_text = f"Local Time: {current_time}"
        time_font = cv2.FONT_HERSHEY_SIMPLEX
        time_font_scale = 0.7
        time_size = cv2.getTextSize(time_text, time_font, time_font_scale, 2)[0]
        # Ensure we use the available dimensions to place the time display
        height, width = full_grid.shape[:2]
        time_x = width - time_size[0] - 20
        time_y = height - 20
        
        # Background for time display
        time_bg_width = time_size[0] + 20
        time_bg_height = time_size[1] + 10
        cv2.rectangle(full_grid, 
                     (time_x - 10, time_y - time_bg_height + 5), 
                     (time_x + time_bg_width - 10, time_y + 5), 
                     COLOR_PALETTE['background_light'], -1)
        
        # Draw time text
        cv2.putText(full_grid, time_text, (time_x, time_y), 
                    time_font, time_font_scale, COLOR_PALETTE['text_bright'], 1)
    
    elif selected_page == 3:  # Map View
        # Update location clusters
        update_location_clusters(frames_dict)
        
        # Create basic frame
        screen_w, screen_h = get_screen_x(), get_screen_y()
        full_grid = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        full_grid[:] = COLOR_PALETTE['background_dark']
        
        # Draw title
        cv2.putText(full_grid, "Camera Clusters by Location", 
                   (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 
                   COLOR_PALETTE['text_bright'], 2)
                   
        # Draw cluster count
        cluster_count = len(location_clusters)
        cv2.putText(full_grid, f"Found {cluster_count} location clusters", 
                   (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                   COLOR_PALETTE['text_medium'], 1)
        
        # Layout grid for location clusters
        grid_left = 50
        grid_top = 150
        grid_width = screen_w - 100
        grid_right = grid_left + grid_width
        
        # Calculate grid parameters
        box_height = 120
        box_margin = 20
        box_width = (grid_width - box_margin*3) // 3  # 3 boxes per row
        
        # Draw the boxes of clusters
        row = 0
        col = 0
        max_cols = 3
        current_mouse_pos = mouse_position
        hovered_cluster = None
        
        for location, cluster in location_clusters.items():
            # Calculate box position
            box_x = grid_left + col * (box_width + box_margin)
            box_y = grid_top + row * (box_height + box_margin)
            
            # Check if mouse is hovering over this box
            if (box_x <= current_mouse_pos[0] <= box_x + box_width and 
                box_y <= current_mouse_pos[1] <= box_y + box_height):
                hovered_cluster = location
                
            # Determine box color based on active percentage
            active_percent = 0
            if cluster['count'] > 0:
                active_percent = cluster['active_count'] / cluster['count'] * 100
                
            if active_percent > 75:
                box_color = COLOR_PALETTE['status_good']  # Green for mostly active
            elif active_percent > 25:
                box_color = COLOR_PALETTE['status_warning']  # Yellow for partially active
            else:
                box_color = COLOR_PALETTE['status_error']  # Red for mostly inactive
                
            # Draw box with proper styling
            # Highlight if selected or hovered
            is_selected = (location == selected_location_cluster)
            is_hovered = (location == hovered_cluster)
            
            # Draw box background
            alpha = 0.8
            if is_selected:
                alpha = 1.0
                # Draw a thicker border for selected cluster
                cv2.rectangle(full_grid, (box_x-2, box_y-2), 
                             (box_x+box_width+2, box_y+box_height+2), 
                             COLOR_PALETTE['accent_primary'], 2)
            
            overlay = full_grid.copy()
            cv2.rectangle(overlay, (box_x, box_y), 
                         (box_x+box_width, box_y+box_height), 
                         COLOR_PALETTE['background_medium'], -1)
            
            # Add a color indicator on the left side of the box
            indicator_width = 10
            cv2.rectangle(overlay, (box_x, box_y), 
                         (box_x+indicator_width, box_y+box_height), 
                         box_color, -1)
            
            # Apply transparency
            cv2.addWeighted(overlay, alpha, full_grid, 1-alpha, 0, full_grid)
            
            # Draw the text content
            title_y = box_y + 25
            count_y = title_y + 25
            active_y = count_y + 25
            fps_y = active_y + 25
            
            # Location name (truncate if too long)
            location_name = location
            if len(location_name) > 15:
                location_name = location_name[:12] + "..."
                
            cv2.putText(full_grid, location_name, 
                       (box_x + 20, title_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.65, 
                       COLOR_PALETTE['text_bright'], 1)
            
            # Camera count
            count_text = f"Cameras: {cluster['count']}"
            cv2.putText(full_grid, count_text, 
                       (box_x + 20, count_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.55, 
                       COLOR_PALETTE['text_medium'], 1)
            
            # Active count
            active_text = f"Active: {cluster['active_count']} ({int(active_percent)}%)"
            cv2.putText(full_grid, active_text, 
                       (box_x + 20, active_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.55, 
                       COLOR_PALETTE['text_medium'], 1)
            
            # Average FPS
            avg_fps = cluster['metadata'].get('avg_fps', 0)
            fps_text = f"Avg FPS: {avg_fps:.1f}"
            cv2.putText(full_grid, fps_text, 
                       (box_x + 20, fps_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.55, 
                       COLOR_PALETTE['text_medium'], 1)
            
            # Move to next position in grid
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Handle cluster selection and hovering
        if hovered_cluster:
            cluster = location_clusters[hovered_cluster]
            
            # Draw a detailed tooltip for the hovered cluster
            tooltip_lines = [
                f"Location: {hovered_cluster}",
                f"Total Cameras: {cluster['count']}",
                f"Active Cameras: {cluster['active_count']} ({int(active_percent)}%)",
                f"Average FPS: {cluster['metadata'].get('avg_fps', 0):.1f}"
            ]
            
            # Add text about clicking to select
            if hovered_cluster != selected_location_cluster:
                tooltip_lines.append("Click to view cameras from this location")
            else:
                tooltip_lines.append("Currently selected")
                
            tooltip_text = "\n".join(tooltip_lines)
            full_grid = draw_tooltip(full_grid, tooltip_text, current_mouse_pos)
            
        # If a cluster is selected, show preview of cameras from that location
        if selected_location_cluster and selected_location_cluster in location_clusters:
            selected_cluster = location_clusters[selected_location_cluster]
            preview_area_top = grid_top + (row + 1) * (box_height + box_margin) + 20
            
            # Draw section title
            cv2.putText(full_grid, f"Camera Previews: {selected_location_cluster}", 
                       (grid_left, preview_area_top - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, 
                       COLOR_PALETTE['text_bright'], 1)
            
            # Draw horizontal line
            cv2.line(full_grid, 
                    (grid_left, preview_area_top + 10), 
                    (grid_right, preview_area_top + 10), 
                    COLOR_PALETTE['divider'], 1)
            
            # Display first 8 cameras of the selected location
            preview_top = preview_area_top + 30
            preview_size = 160
            preview_padding = 20
            preview_per_row = 4
            
            for i, camera_id in enumerate(selected_cluster['cameras'][:8]):
                if i >= 8:  # Limit to 8 previews
                    break
                    
                row = i // preview_per_row
                col = i % preview_per_row
                
                x = grid_left + col * (preview_size + preview_padding)
                y = preview_top + row * (preview_size + preview_padding + 30)
                
                # Draw camera preview
                frame = frames_dict.get(camera_id)
                if frame is not None and frame.size > 0:
                    try:
                        preview_frame = cv2.resize(frame, (preview_size, preview_size))
                        full_grid[y:y+preview_size, x:x+preview_size] = preview_frame
                    except Exception as e:
                        # Draw placeholder on error
                        cv2.rectangle(full_grid, (x, y), 
                                     (x+preview_size, y+preview_size), 
                                     COLOR_PALETTE['background_light'], -1)
                else:
                    # Draw placeholder for offline camera
                    cv2.rectangle(full_grid, (x, y), 
                                 (x+preview_size, y+preview_size), 
                                 COLOR_PALETTE['background_light'], -1)
                
                # Draw camera address below preview
                ip_text = extract_ip_from_url(camera_id)
                if len(ip_text) > 15:
                    ip_text = ip_text[:12] + "..."
                    
                cv2.putText(full_grid, ip_text, 
                           (x, y+preview_size+20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                           COLOR_PALETTE['text_medium'], 1)
        
    # Add the graphical part of the buttons - with bounds checking
    screen_width = full_grid.shape[1]
    button1_x1 = min(button_page_1_topleft_x, screen_width - 450)
    button1_x2 = min(button_page_1_bottomright_x, screen_width - 450 + 230)
    button2_x1 = min(button_page_2_topleft_x, screen_width - 450 + 240)
    button2_x2 = min(button_page_2_bottomright_x, screen_width - 450 + 460)
    button3_x1 = min(button_page_3_topleft_x, screen_width - 450 + 470)
    button3_x2 = min(button_page_3_bottomright_x, screen_width - 450 + 690)
    
    # Matrix View button - active/inactive state
    button1_color = COLOR_PALETTE['accent_secondary'] if selected_page == 1 else COLOR_PALETTE['button_normal']
    cv2.rectangle(full_grid, (button1_x1, button_page_1_topleft_y), 
                 (button1_x2, button_page_1_bottomright_y), button1_color, -1)
    
    # Grid View button - active/inactive state
    button2_color = COLOR_PALETTE['accent_secondary'] if selected_page == 2 else COLOR_PALETTE['button_normal']
    cv2.rectangle(full_grid, (button2_x1, button_page_2_topleft_y), 
                 (button2_x2, button_page_2_bottomright_y), button2_color, -1)
                 
    # Map View button - active/inactive state
    button3_color = COLOR_PALETTE['accent_secondary'] if selected_page == 3 else COLOR_PALETTE['button_normal']
    cv2.rectangle(full_grid, (button3_x1, button_page_3_topleft_y), 
                 (button3_x2, button_page_3_bottomright_y), button3_color, -1)

    # Add button borders
    cv2.rectangle(full_grid, (button1_x1, button_page_1_topleft_y), 
                 (button1_x2, button_page_1_bottomright_y), COLOR_PALETTE['border'], 1)
    cv2.rectangle(full_grid, (button2_x1, button_page_2_topleft_y), 
                 (button2_x2, button_page_2_bottomright_y), COLOR_PALETTE['border'], 1)
    cv2.rectangle(full_grid, (button3_x1, button_page_3_topleft_y), 
                 (button3_x2, button_page_3_bottomright_y), COLOR_PALETTE['border'], 1)

    text_font = cv2.FONT_HERSHEY_SIMPLEX
    text_scale = 0.7
    text_thickness = 2
    text_color = COLOR_PALETTE['text_bright']

    text1 = "Matrix View"
    text2 = "List View"
    text3 = "Map View"

    text1_size = cv2.getTextSize(text1, text_font, text_scale, text_thickness)[0]
    text2_size = cv2.getTextSize(text2, text_font, text_scale, text_thickness)[0]
    text3_size = cv2.getTextSize(text3, text_font, text_scale, text_thickness)[0]

    text1_x = button1_x1 + (min(230, button1_x2 - button1_x1) - text1_size[0]) // 2
    text1_y = button_page_1_topleft_y + (40 + text1_size[1]) // 2

    text2_x = button2_x1 + (min(220, button2_x2 - button2_x1) - text2_size[0]) // 2
    text2_y = button_page_2_topleft_y + (40 + text2_size[1]) // 2
    
    text3_x = button3_x1 + (min(220, button3_x2 - button3_x1) - text3_size[0]) // 2
    text3_y = button_page_3_topleft_y + (40 + text3_size[1]) // 2

    cv2.putText(full_grid, text1, (text1_x, text1_y), text_font, text_scale, text_color, text_thickness)
    cv2.putText(full_grid, text2, (text2_x, text2_y), text_font, text_scale, text_color, text_thickness)
    cv2.putText(full_grid, text3, (text3_x, text3_y), text_font, text_scale, text_color, text_thickness)

    height, width = full_grid.shape[:2]

    # Global styling layout variables
    graph_padding_offset = 40

    # Top left information center - camera count
    information_center_width = 400
    
    # Draw the camera count background
    info_bg_color = COLOR_PALETTE['accent_tertiary']
    cv2.rectangle(full_grid, (graph_padding_offset, 0), 
                 (min(information_center_width + graph_padding_offset, width), graph_padding_offset), 
                 info_bg_color, -1)

    # Make the text
    def get_camera_text(numcams):
        """Safely generate camera count text."""
        try:
            count = int(numcams)
            if count == 1:
                return "1 cam online"
            else:
                return f"{count} cams online"
        except:
            return "? cams online"

    # Write the camera count text
    camera_count = get_camera_text(len(frames_dict))
    camera_font_scale = 0.7
    cv2.putText(full_grid, camera_count, (graph_padding_offset, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, camera_font_scale, COLOR_PALETTE['text_bright'], 1, cv2.LINE_AA)

    # Graph settings - bottom area for graphs 
    graph_width, graph_height = 180, 40
    graphs_background_box_width = min(730, width - graph_padding_offset - 50)
    
    # Draw the background for the bottom left section (graphs area)
    cv2.rectangle(full_grid, (graph_padding_offset, height - 40), 
                 (min(graph_padding_offset + graphs_background_box_width, width), height), 
                 COLOR_PALETTE['accent_tertiary'], -1)

    # Display local time at bottom right
    current_time = time.strftime("%H:%M:%S", time.localtime())
    time_text = f"Local Time: {current_time}"
    time_font = cv2.FONT_HERSHEY_SIMPLEX
    time_font_scale = 0.7
    time_size = cv2.getTextSize(time_text, time_font, time_font_scale, 2)[0]
    time_x = resized_width - time_size[0] - 20
    time_y = resized_height - 20
    
    # Background for time display
    time_bg_width = time_size[0] + 20
    time_bg_height = time_size[1] + 10
    cv2.rectangle(full_grid, 
                 (time_x - 10, time_y - time_bg_height + 5), 
                 (time_x + time_bg_width - 10, time_y + 5), 
                 COLOR_PALETTE['background_light'], -1)
    
    # Draw time text
    cv2.putText(full_grid, time_text, (time_x, time_y), 
                time_font, time_font_scale, COLOR_PALETTE['text_bright'], 1)
                
    # Only draw graphs if we have enough space
    if graph_padding_offset + graph_width + 250 < width:
        # Graph 1 - CPU Usage
        graph1_x = 160
        graph1_y = height - graph_height
        
        cpu_graph_label = "SYS CPU:"
        
        cv2.putText(full_grid, cpu_graph_label, (graph1_x - 120, graph1_y + 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_PALETTE['text_bright'], 2)
        draw_usage_graph(full_grid, cpu_usage_history, (graph1_x, graph1_y), 
                        (graph_width, graph_height), "CPU Usage", COLOR_PALETTE['graph_line3'])

        # Graph 2 - Memory Usage - only if we have space
        if graph1_x + graph_width + 250 + graph_width < width:
            graph2_x = graph1_x + graph_width + 250
            graph2_y = graph1_y
            mem_graph_label = "MEMORY:"

            cv2.putText(full_grid, mem_graph_label, (graph2_x - 120, graph2_y + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_PALETTE['text_bright'], 2)
            draw_usage_graph(full_grid, mem_usage_history, (graph2_x, graph2_y), 
                            (graph_width, graph_height), "Memory Usage", COLOR_PALETTE['graph_line2'])
    
    # Add logo at the end
    final_full_grid = add_logo(full_grid)
    
    # Display selected camera if we're on the list page and there's a selection
    if selected_page == 2 and selected_camera is not None:
        final_full_grid = display_selected_camera(frames_dict, final_full_grid)
    
    # Add bandwidth graph display (after all other graphs have been drawn)
    height, width = final_full_grid.shape[:2]
    update_bandwidth_usage()
    graph3_x = graph1_x + graph_width + 500 if 'graph1_x' in locals() else 160 + 180 + 500
    graph3_y = height - graph_height
    
    if len(bandwidth_history) > 0 and graph3_x + graph_width < width:
        draw_bandwidth_graph(final_full_grid, (graph3_x, graph3_y), (graph_width, graph_height), None)

    return final_full_grid

def display_selected_camera(frames_dict, full_grid):
    """Display selected camera in the right panel with enhanced layout"""
    global selected_camera
    global right_panel_left, right_panel_right, right_panel_top, right_panel_bottom
    global camera_view_height, camera_view_top, camera_view_bottom
    global info_section_top, info_section_bottom
    global right_activity_left, right_activity_right
    
    # Debug: Log information about the selected camera
    logging.debug(f"Display selected camera called with: {selected_camera}")
    
    if not selected_camera:
        logging.debug("No camera selected")
        return full_grid
    
    # Get the frame for the selected camera
    frame = frames_dict.get(selected_camera)
    
    if frame is None:
        return full_grid
        
    try:
        # Create a copy to avoid modifying the original
        frame_copy = frame.copy()
        
        # Get panel dimensions - use right_activity values which are correctly set
        panel_width = right_activity_right - right_activity_left
        panel_height = camera_view_height
        
        # Use a fixed 16:9 aspect ratio
        fixed_aspect_ratio = 16/9
        
        # Calculate fixed dimensions that don't change based on source frame
        display_width = int(panel_width * 0.9)  # Use 90% of panel width
        display_height = int(display_width / fixed_aspect_ratio)
        
        # Make sure height fits
        if display_height > panel_height * 0.9:
            display_height = int(panel_height * 0.9)
            display_width = int(display_height * fixed_aspect_ratio)
        
        # Resize the frame to fit the panel
        display_frame = cv2.resize(frame_copy, (display_width, display_height))
        
        # Calculate centering position - use right_activity coordinates 
        x_offset = right_activity_left + (panel_width - display_width) // 2
        y_offset = camera_view_top + 30  # Add some padding from the top
        
        # Create a region of interest in the full grid
        if (y_offset >= 0 and x_offset >= 0 and 
            y_offset + display_height <= full_grid.shape[0] and 
            x_offset + display_width <= full_grid.shape[1]):
            
            # Draw a border around the frame
            cv2.rectangle(full_grid, 
                         (x_offset-2, y_offset-2), 
                         (x_offset+display_width+2, y_offset+display_height+2), 
                         (120, 120, 120), 2)
            
            # Place the camera image
            full_grid[y_offset:y_offset+display_height, x_offset:x_offset+display_width] = display_frame
        
        # Add camera details and controls to the respective sections
        full_grid = display_camera_details(
            frames_dict, full_grid, selected_camera,
            right_activity_left, right_activity_right,
            info_section_top, info_section_bottom
        )
    except Exception as e:
        logging.error(f"Error displaying selected camera: {e}")
    
    return full_grid

def get_safe_max_position():
    """Get maximum valid position for the camera list"""
    global working_cameras
    try:
        if not working_cameras:
            return 0
        return max(0, len(working_cameras) - view_list_visible_address_count)
    except:
        return 0

# Function to display camera details and controls in the right panel
def display_camera_details(frames_dict, full_grid, selected_camera, 
                                      right_activity_left, right_activity_right,
                                      info_section_top, info_section_bottom):
    """Displays detailed camera information and control interface in the right panel"""
    if not selected_camera:
        # If no camera selected, show a message
        font = cv2.FONT_HERSHEY_SIMPLEX
        message = "No camera selected"
        text_size = cv2.getTextSize(message, font, 1.0, 2)[0]
        text_x = right_activity_left + (right_activity_right - right_activity_left - text_size[0]) // 2
        text_y = info_section_top + (info_section_bottom - info_section_top) // 2
        cv2.putText(full_grid, message, (text_x, text_y), font, 1.0, (180, 180, 180), 2)
        return full_grid
    
    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    font_color = (220, 220, 220)
    font_thickness = 1
    small_font_scale = 0.6
    
    # Extract IP address and parsed URL components
    ip_address = extract_ip_from_url(selected_camera)
    parsed_url = urllib.parse.urlparse(selected_camera if selected_camera.startswith('http') else f'http://{selected_camera}')
    
    # Get detailed camera info
    meta = camera_metadata.get(selected_camera, {})
    resolution = meta.get("resolution", "Unknown")
    fps = meta.get("fps", 0)
    stream_type = meta.get("stream_type", "Unknown")
    endpoint = meta.get("endpoint", "Unknown")
    frames_received = meta.get("frames_received", 0)
    first_seen = meta.get("first_seen", time.time())
    last_frame_time = meta.get("last_frame_time", 0)
    connection_attempts = meta.get("connection_attempts", 0)
    connection_failures = meta.get("connection_failures", 0)
    last_success = meta.get("last_success", 0)
    
    # Calculate derived metrics
    uptime = format_uptime(first_seen)
    success_rate = "0%" if connection_attempts == 0 else f"{((connection_attempts - connection_failures) / connection_attempts) * 100:.1f}%"
    last_frame_ago = "Never" if last_frame_time == 0 else format_uptime(last_frame_time)
    location = get_geolocation(ip_address)
    
    # Info section - with enhanced styling and organization
    # Draw a gradient background for the info section
    info_bg = full_grid.copy()
    cv2.rectangle(info_bg, 
                 (right_activity_left, info_section_top), 
                 (right_activity_right, info_section_bottom), 
                 (25, 30, 40), -1)  # Darker background for better contrast
    cv2.addWeighted(info_bg, 0.85, full_grid, 0.15, 0, full_grid)
    
    # Draw a header bar
    header_height = 30
    cv2.rectangle(full_grid,
                 (right_activity_left, info_section_top),
                 (right_activity_right, info_section_top + header_height),
                 (40, 60, 80), -1)
    
    # Camera title in header
    title_y = info_section_top + 22
    camera_title = f"Camera Details: {selected_camera.split('/')[-1]}"
    cv2.putText(full_grid, camera_title, 
               (right_activity_left + 15, title_y), 
               font, font_scale, (240, 240, 250), 2)
    
    # Draw divider between columns
    divider_x = right_activity_left + (right_activity_right - right_activity_left) // 2
    cv2.line(full_grid,
             (divider_x, info_section_top + header_height + 5),
             (divider_x, info_section_bottom - 5),
             (60, 80, 100), 1)
    
    # Column 1 (Left Side)
    col1_x = right_activity_left + 15
    row1_y = info_section_top + header_height + 25
    row_space = 25
    
    # Connection information
    cv2.putText(full_grid, "Connection Info:", (col1_x, row1_y), font, small_font_scale, (150, 200, 230), 1)
    cv2.putText(full_grid, f"IP: {ip_address}", (col1_x, row1_y + row_space), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Port: {parsed_url.port or 'Default'}", (col1_x, row1_y + row_space*2), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Endpoint: {endpoint}", (col1_x, row1_y + row_space*3), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Location: {location}", (col1_x, row1_y + row_space*4), font, small_font_scale, font_color, font_thickness)
    
    # Stream statistics
    cv2.putText(full_grid, "Stream Stats:", (col1_x, row1_y + row_space*5.5), font, small_font_scale, (150, 200, 230), 1)
    cv2.putText(full_grid, f"Type: {stream_type}", (col1_x, row1_y + row_space*6.5), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Resolution: {resolution}", (col1_x, row1_y + row_space*7.5), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"FPS: {fps}", (col1_x, row1_y + row_space*8.5), font, small_font_scale, font_color, font_thickness)
    
    # Column 2 (Right Side)
    col2_x = divider_x + 15
    
    # Performance metrics
    cv2.putText(full_grid, "Performance:", (col2_x, row1_y), font, small_font_scale, (150, 200, 230), 1)
    cv2.putText(full_grid, f"Uptime: {uptime}", (col2_x, row1_y + row_space), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Frames: {frames_received}", (col2_x, row1_y + row_space*2), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Last frame: {last_frame_ago} ago", (col2_x, row1_y + row_space*3), font, small_font_scale, font_color, font_thickness)
    
    # Reliability information
    cv2.putText(full_grid, "Reliability:", (col2_x, row1_y + row_space*5.5), font, small_font_scale, (150, 200, 230), 1)
    cv2.putText(full_grid, f"Connections: {connection_attempts}", (col2_x, row1_y + row_space*6.5), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Failures: {connection_failures}", (col2_x, row1_y + row_space*7.5), font, small_font_scale, font_color, font_thickness)
    cv2.putText(full_grid, f"Success rate: {success_rate}", (col2_x, row1_y + row_space*8.5), font, small_font_scale, font_color, font_thickness)
    
    # Add timestamp at the bottom right
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    timestamp_text = f"Updated: {timestamp}"
    timestamp_size = cv2.getTextSize(timestamp_text, font, 0.5, 1)[0]
    cv2.putText(full_grid, timestamp_text, 
               (right_activity_right - timestamp_size[0] - 10, info_section_bottom - 10), 
               font, 0.5, (150, 150, 150), 1)
    
    # Draw a status indicator showing if camera is currently active
    status_color = (20, 180, 20) if time.time() - last_frame_time < 5 else (20, 20, 180)  # Green if recent frame, red if stale
    cv2.circle(full_grid, (right_activity_right - 15, title_y - 8), 5, status_color, -1)
    
    return full_grid



# Camera movement control class
class CameraMovement:
    """Class for camera movement controls with placeholder methods"""
    
    @staticmethod
    def move_up(camera_ip, amount=1):
        """Move camera up by specified amount"""
        print(f"Moving camera {camera_ip} up by {amount}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def move_down(camera_ip, amount=1):
        """Move camera down by specified amount"""
        print(f"Moving camera {camera_ip} down by {amount}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def move_left(camera_ip, amount=1):
        """Move camera left by specified amount"""
        print(f"Moving camera {camera_ip} left by {amount}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def move_right(camera_ip, amount=1):
        """Move camera right by specified amount"""
        print(f"Moving camera {camera_ip} right by {amount}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def zoom_in(camera_ip, amount=1):
        """Zoom camera in by specified amount"""
        print(f"Zooming camera {camera_ip} in by {amount}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def zoom_out(camera_ip, amount=1):
        """Zoom camera out by specified amount"""
        print(f"Zooming camera {camera_ip} out by {amount}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def move_to_preset(camera_ip, preset_number):
        """Move camera to a preset position"""
        print(f"Moving camera {camera_ip} to preset {preset_number}")
        # Placeholder - implement actual camera control protocol here
        return True
    
    @staticmethod
    def stop(camera_ip):
        """Stop camera movement"""
        print(f"Stopping camera {camera_ip} movement")
        # Placeholder - implement actual camera control protocol here
        return True


# Function to handle camera control button clicks
def handle_camera_control(control_action, camera_ip):
    """Call the appropriate camera movement method based on the control action"""
    try:
        if control_action == "up":
            CameraMovement.move_up(camera_ip)
            show_popup(text=f"Moving camera {camera_ip} up")
        elif control_action == "down":
            CameraMovement.move_down(camera_ip)
            show_popup(text=f"Moving camera {camera_ip} down")
        elif control_action == "left":
            CameraMovement.move_left(camera_ip)
            show_popup(text=f"Moving camera {camera_ip} left")
        elif control_action == "right":
            CameraMovement.move_right(camera_ip)
            show_popup(text=f"Moving camera {camera_ip} right")
        elif control_action == "zoom_in":
            CameraMovement.zoom_in(camera_ip)
            show_popup(text=f"Zooming camera {camera_ip} in")
        elif control_action == "zoom_out":
            CameraMovement.zoom_out(camera_ip)
            show_popup(text=f"Zooming camera {camera_ip} out")
    except Exception as e:
        logging.error(f"Error handling camera control: {e}")
        show_popup(text=f"Camera control error: {str(e)[:30]}", color="red")


def cleanall():
    print("Cleaning all dataset")
    if os.path.isfile(DB_ZIP) and os.path.isfile(DB_CSV) and os.path.isfile(IP_LIST_FILE):
        remove_ip2loc(DB_ZIP=DB_ZIP, DB_CSV=DB_CSV)
        remove_iplist(IP_LIST_FILE=IP_LIST_FILE)
    else:
        print("Invalid state detected, exiting. HINT: This happens when you clean the program before it has fully inited atleast one time.")
        exit()
    print("Datasets have been deleted, callinit the init function tDatabaseso cause them to autodownload again")
    initall()

def cleanip2loc():
    print("Cleaning ip2loc dataset")
    if os.path.isfile(DB_CSV) and os.path.isfile(DB_ZIP):
        remove_ip2loc(DB_ZIP=DB_ZIP, DB_CSV=DB_CSV)
    else:
        print("Invalid state detected, exiting. HINT: This happens when you clean the program before it has fully inited atleast one time.")
        exit()
    print("Datasets have been deleted, callinit the init function to cause them to autodownload again")
    initall()

def cleaniplist():
    print("Cleaning iplist dataset")
    if os.path.isfile(IP_LIST_FILE):
        remove_iplist(IP_LIST_FILE=IP_LIST_FILE)
    else:
        print("Invalid state detected, exiting. HINT: This happens when you clean the program before it has fully inited atleast one time.")
        exit()
    print("Datasets have been deleted, callinit the init function to cause them to autodownload again")
    initall()

def draw_tooltip(frame, text, position, padding=10, font_scale=0.7, bg_color=(40, 40, 40), text_color=(240, 240, 240)):
    """Draw a tooltip box with text at the specified position."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # Handle multi-line text
    lines = text.split('\n')
    line_heights = []
    line_widths = []
    
    # Calculate size needed for each line
    for line in lines:
        text_size, baseline = cv2.getTextSize(line, font, font_scale, 1)
        line_heights.append(text_size[1])
        line_widths.append(text_size[0])
    
    # Position the tooltip just below the mouse cursor
    x, y = position
    
    # Keep tooltip on screen
    height, width = frame.shape[:2]
    box_width = max(line_widths) + padding * 2
    line_spacing = 8  # Space between lines
    box_height = sum(line_heights) + padding * 2 + line_spacing * max(0, len(lines) - 1)
    
    # Adjust position to stay within screen bounds
    if x + box_width > width:
        x = width - box_width
    if y + box_height + 20 > height:
        y = y - box_height - 10  # Show above cursor if near bottom
    else:
        y = y + 20  # Show below cursor normally
    
    # Draw semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + box_width, y + box_height), bg_color, -1)
    cv2.rectangle(overlay, (x, y), (x + box_width, y + box_height), (80, 80, 80), 1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
    
    # Draw each line of text
    text_y = y + padding
    for i, line in enumerate(lines):
        text_y += line_heights[i]  # Add the height of this line
        text_x = x + padding
        cv2.putText(frame, line, (text_x, text_y), font, font_scale, text_color, 1, cv2.LINE_AA)
        text_y += line_spacing  # Add space between lines
    
    return frame

def update_location_clusters(frames_dict):
    """Analyze active cameras and group them by location/country"""
    global location_clusters, last_cluster_update_time
    
    # Only update every 5 seconds to avoid excessive processing
    current_time = time.time()
    if current_time - last_cluster_update_time < 5 and location_clusters:
        return
    
    last_cluster_update_time = current_time
    new_clusters = {}
    
    # Process all active cameras
    for camera_id, frame in frames_dict.items():
        if frame is None or frame.size == 0:
            continue
            
        ip_address = extract_ip_from_url(camera_id)
        location = get_geolocation(ip_address)
        
        if location == "Unknown Location":
            location = "Unidentified"
            
        # Add camera to the appropriate cluster
        if location not in new_clusters:
            new_clusters[location] = {
                'cameras': [],
                'count': 0,
                'active_count': 0,
                'metadata': {},
            }
            
        # Add camera to cluster
        new_clusters[location]['cameras'].append(camera_id)
        new_clusters[location]['count'] += 1
        
        # Check if camera is "active" (has recent frames)
        meta = camera_metadata.get(camera_id, {})
        last_frame_time = meta.get('last_frame_time', 0)
        if current_time - last_frame_time < 30:  # Active in last 30 seconds
            new_clusters[location]['active_count'] += 1
            
        # Add some metadata about the cluster
        if 'fps_total' not in new_clusters[location]['metadata']:
            new_clusters[location]['metadata']['fps_total'] = 0
            new_clusters[location]['metadata']['cameras_with_fps'] = 0
            
        fps = meta.get('fps', 0)
        if fps > 0:
            new_clusters[location]['metadata']['fps_total'] += fps
            new_clusters[location]['metadata']['cameras_with_fps'] += 1
    
    # Calculate averages and other stats
    for location, cluster in new_clusters.items():
        if cluster['metadata'].get('cameras_with_fps', 0) > 0:
            cluster['metadata']['avg_fps'] = cluster['metadata']['fps_total'] / cluster['metadata']['cameras_with_fps']
        else:
            cluster['metadata']['avg_fps'] = 0
    
    # Sort clusters by camera count (descending)
    location_clusters = {k: v for k, v in sorted(
        new_clusters.items(), 
        key=lambda item: item[1]['count'], 
        reverse=True
    )}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanall", help="Delete the old data sources and download new ones", action="store_true")
    parser.add_argument("--cleanip2loc", help="Delete the old data sources for ip2loc and download new ones", action="store_true")
    parser.add_argument("--cleanip2list", help="Delete the old iplist and scrape a new one", action="store_true")
    args = parser.parse_args()

    # Act based on the inputs now
    if args.cleanall:
        cleanall()
        time.sleep(1)
    elif args.cleanip2loc:
        cleanip2loc()
        time.sleep(1) 
    elif args.cleanip2loc:
        cleaniplist()
        time.sleep(1) 

    print("Doing init jobs...")
    initall()
    print("Init completed")

    with open("rawips.txt") as f:
        inputs = [line.strip() for line in f if line.strip()]
    logging.debug(f"Loaded {len(inputs)} streams from ip_list.txt.")
    frames = {}
    borders = {}
    labels = {}
    lock = threading.Lock()
    for input_id in inputs:
        threading.Thread(target=read_stream, args=(input_id, frames, borders, lock), daemon=True).start()
    cv2.namedWindow("SilverFlag Stream Viewer", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("SilverFlag Stream Viewer", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    def display_error(error_text):
        global _selected_python_joke
        screen_w, screen_h = get_raw_screen_resolution()
        error_frame = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        font = cv2.FONT_HERSHEY_DUPLEX  # Changed to DUPLEX for a more normal font
        font_scale = 1.0
        font_thickness = 2
        font_color = (255, 255, 255)
        icon_size = 80
        margin = 30
        icon_x = screen_w - icon_size - margin
        icon_y = margin
        triangle_pts = np.array([
            [icon_x + icon_size//2, icon_y],
            [icon_x, icon_y + icon_size],
            [icon_x + icon_size, icon_y + icon_size]
        ], np.int32)
        cv2.fillPoly(error_frame, [triangle_pts], (0, 0, 255))
        cv2.polylines(error_frame, [triangle_pts], True, (255, 255, 255), 2)
        cv2.putText(error_frame, "!", 
                    (icon_x + icon_size//2 - 5, icon_y + icon_size - 20), 
                    font, 1.2, (255, 255, 255), 3)
        title_text = "FATAL EXCEPTION"
        title_scale = 1.5
        title_thickness = 3
        title_size = cv2.getTextSize(title_text, font, title_scale, title_thickness)[0]
        title_x = (screen_w - title_size[0]) // 2
        title_y = margin + 80
        cv2.putText(error_frame, title_text, (title_x, title_y), 
                    font, title_scale, (0, 0, 255), title_thickness)
        cv2.putText(error_frame, title_text, (title_x, title_y), 
                    font, title_scale, (255, 255, 255), 1)
        if isinstance(error_text, Exception):
            error_name = type(error_text).__name__
            error_description = str(error_text)
            stack_trace = traceback.format_exc().split("\n")
            cv2.putText(error_frame, f"Type: {error_name}", 
                        (50, title_y + 70), font, font_scale, (255, 50, 50), font_thickness)
            max_width = screen_w - 100
            desc_lines = []
            words = error_description.split()
            current_line = "Message: " + (words[0] if words else "")
            for word in words[1:]:
                test_line = current_line + " " + word
                test_size = cv2.getTextSize(test_line, font, font_scale, font_thickness)[0][0]
                if test_size < max_width:
                    current_line = test_line
                else:
                    desc_lines.append(current_line)
                    current_line = "        " + word
            desc_lines.append(current_line)
            for i, line in enumerate(desc_lines):
                cv2.putText(error_frame, line, 
                            (50, title_y + 120 + i*40), font, font_scale, font_color, font_thickness)
            trace_y = title_y + 120 + len(desc_lines)*40 + 50
            cv2.putText(error_frame, "Stack Trace:", 
                        (50, trace_y), font, font_scale, (100, 200, 255), font_thickness)
            trace_line_count = min(8, len(stack_trace)) + 1
            box_height = trace_line_count * 30 + 20
            box_width = screen_w - 100
            box_x = 40
            box_y = trace_y + 10
            cv2.rectangle(error_frame, (box_x, box_y), (box_x + box_width, box_y + box_height), 
                        (40, 40, 80), -1)
            cv2.rectangle(error_frame, (box_x, box_y), (box_x + box_width, box_y + box_height), 
                        (100, 100, 180), 2)
            trace_y += 40
            for i, line in enumerate(stack_trace):
                if i >= 8:
                    cv2.putText(error_frame, "...", 
                                (60, trace_y + i*30), font, 0.8, (150, 150, 150), 1)
                    break
                if not line.strip():
                    continue
                if "line" in line and "File" in line:
                    parts = line.split(", line ")
                    if len(parts) > 1:
                        file_part = parts[0]
                        line_part = "line " + parts[1]
                        cv2.putText(error_frame, file_part, 
                                    (60, trace_y + i*30), font, 0.7, (180, 180, 255), 1)
                        file_width = cv2.getTextSize(file_part, font, 0.7, 1)[0][0]
                        cv2.putText(error_frame, ", " + line_part, 
                                    (60 + file_width, trace_y + i*30), font, 0.7, (255, 180, 180), 1)
                    else:
                        cv2.putText(error_frame, line, 
                                    (60, trace_y + i*30), font, 0.7, (180, 180, 255), 1)
                else:
                    cv2.putText(error_frame, line, 
                                (60, trace_y + i*30), font, 0.7, (200, 200, 200), 1)
        else:
            error_lines = []
            words = str(error_text).split()
            current_line = words[0] if words else ""
            max_width = screen_w - 100
            for word in words[1:]:
                test_line = current_line + " " + word
                test_size = cv2.getTextSize(test_line, font, font_scale, font_thickness)[0][0]
                if test_size < max_width:
                    current_line = test_line
                else:
                    error_lines.append(current_line)
                    current_line = word
            error_lines.append(current_line)
            for i, line in enumerate(error_lines):
                error_y = title_y + 80 + i*40
                cv2.putText(error_frame, line, 
                            (50, error_y), font, font_scale, font_color, font_thickness)
        python_jokes = [
            "Python: Where indentation errors are just as fatal as logic errors",
            "Python: Making whitespace important since 1991",
            "I'd tell you a Python joke but I'm afraid you'd indent it wrong",
            "Programmer: 'Why isn't this code working?' Python: 'tab vs space, line 42'",
            "Python: The language where invisible characters matter",
            "My code works fine locally but breaks in production... must be Python",
            "Python autocompletes to Python3, Python3.10, Python3.11... just pick one already",
            "In Python we don't say 'I love you', we say 'pip install love' and I think that's beautiful",
            "I asked Python for its opinion on JavaScript. It raised an IndentationError"
        ]
        if _selected_python_joke is None:
            _selected_python_joke = random.choice(python_jokes)
        joke = _selected_python_joke
        joke_size = cv2.getTextSize(joke, font, 0.7, 1)[0]
        joke_x = (screen_w - joke_size[0]) // 2
        joke_y = screen_h - 80
        cv2.putText(error_frame, joke, (joke_x, joke_y), font, 0.7, (100, 100, 100), 1)
        timestamp = f"Time: {time.strftime('%H:%M:%S - %Y-%m-%d')}"
        cv2.putText(error_frame, timestamp, (20, screen_h - 20), font, 0.7, (150, 150, 150), 1)
        return error_frame
    while True:
        try:
            with lock:
                global current_list_position
                max_position = get_safe_max_position()
                current_list_position = max(0, min(current_list_position, max_position))
                try:
                    listinput = get_ip_range(IP_LIST_FILE, current_list_position + 1, current_list_position + view_list_visible_address_count + 1)
                    grid = layout_frames(frames, borders, labels, selected_page=selected_page, inputs=listinput)
                    grid = draw_popups_on_frame(grid)
                except Exception as layout_error:
                    logging.error(f"Error in layout_frames: {layout_error}")
                    grid = display_error(layout_error)
            
            if grid is not None and grid.size > 0 and len(grid.shape) == 3 and grid.shape[2] == 3:
                cv2.imshow("SilverFlag Stream Viewer", grid)
            else:
                cv2.imshow("SilverFlag Stream Viewer", display_error("Invalid frame generated (NULL or wrong dimensions)"))
        
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            try:
                cv2.imshow("SilverFlag Stream Viewer", display_error(e))
            except:
                error_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(error_frame, "Critical Error", (500, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                cv2.imshow("SilverFlag Stream Viewer", error_frame)
            
        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_on_click(click_handler)
    track_mouse_position()
    main()
