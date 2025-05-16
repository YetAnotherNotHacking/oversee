# SilverFlag Camera Viewer
# View many cameras @ once and switch between them
# https://github.com/yetanothernothacking/oversee
try:
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
button_page_1_bottomright_x = button_page_1_topleft_x + 250
button_page_1_bottomright_y = 40

# Grid view button
button_page_2_topleft_x = 1220
button_page_2_topleft_y = 0
button_page_2_bottomright_x = button_page_2_topleft_x + 250
button_page_2_bottomright_y = 40

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
            total_delta = (sent_delta + recv_delta) / 1024  # KB/s
            bandwidth_history.append(total_delta)
        
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
    """Draws the bandwidth usage graph"""
    graph_w, graph_h = size
    if not bandwidth_history:
        return
    
    points = []
    if max_value is None:
        max_value = max(bandwidth_history) * 1.2 or 100  # Ensure non-zero
    
    for i, val in enumerate(bandwidth_history):
        x = origin[0] + int(i * (graph_w / 60))
        # Scale value to graph height
        y = origin[1] + graph_h - int((val / max_value) * graph_h)
        points.append((x, y))
    
    if len(points) >= 2:
        cv2.polylines(frame, [np.array(points, dtype=np.int32)], isClosed=False, color=(0, 180, 255), thickness=2)
        baseline_points = points.copy()
        baseline_points.append((points[-1][0], origin[1] + graph_h))
        baseline_points.append((points[0][0], origin[1] + graph_h))
        cv2.fillPoly(frame, [np.array(baseline_points, dtype=np.int32)], color=(0, 50, 80))
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), (180, 180, 180), 1)
    
    # Draw horizontal guidelines
    for i in range(1, 4):
        y = origin[1] + graph_h - int((i / 4) * graph_h)
        cv2.line(frame, (origin[0], y), (origin[0] + graph_w, y), (100, 100, 100), 1)
    
    # Draw labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    
    # Current value
    current_val = bandwidth_history[-1] if bandwidth_history else 0
    current_text = format_bandwidth(current_val)
    cv2.putText(frame, current_text, (origin[0] + 5, origin[1] + 15), font, font_scale, (220, 220, 220), 1)
    
    # Title
    cv2.putText(frame, "Bandwidth", (origin[0], origin[1] - 5), font, font_scale, (180, 180, 180), 1)

def count_lines(filepath):
    with open(filepath, 'r') as f:
        return sum(1 for _ in f)

def download_ip2loc_db_if_not_exists():
    if os.path.exists(DB_CSV):
        return
    if not os.path.exists(DB_ZIP):
        r = requests.get(DB_URL)
        with open(DB_ZIP, "wb") as f:
            f.write(r.content)
    with zipfile.ZipFile(DB_ZIP, 'r') as zip_ref:
        zip_ref.extract(DB_CSV)

def load_ip2loc_db():
    ranges = []
    countries = []
    with open(DB_CSV, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            ip_from = int(row[0])
            ip_to = int(row[1])
            country = row[3]
            ranges.append(ip_to)
            countries.append((ip_from, country))
    return ranges, countries

try:
    ip_database = load_ip2loc_db()
except Exception as e:
    download_ip2loc_db_if_not_exists()
    ip_database = load_ip2loc_db()

def get_geolocation(ip_address):
    if ip_address in geolocation_data:
        return geolocation_data[ip_address]

    try:
        ip_int = ip_to_int(ip_address)
        for ip_from, ip_to, country in ip_database:
            if ip_from <= ip_int <= ip_to:
                geolocation_data[ip_address] = country
                return country
    except Exception:
        pass

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

    # 1 - page 1 button
    # 2 - page 2 button
    # 3 - list view scroll up button
    # 4 - list view scroll down button

    if check_in_bounding_box(point, [button_page_1_topleft_x, button_page_1_topleft_y], [button_page_1_bottomright_x, button_page_1_bottomright_y]):
        return 1
    if check_in_bounding_box(point, [button_page_2_topleft_x, button_page_2_topleft_y], [button_page_2_bottomright_x, button_page_2_bottomright_y]):
        return 2
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
    global selected_page, current_list_position, selected_camera, working_cameras

    try:
        current_mouse_location = get_current_cursor_position()
        button_reaction = check_if_in_button_area(current_mouse_location)

        # Only show popup for button clicks, not random clicks
        if button_reaction > 0:
            show_popup(text=f"Button {button_reaction} clicked")

        if button_reaction == 1:
            selected_page = 1
        elif button_reaction == 2:
            selected_page = 2
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
                
                # Check if a camera control button was clicked
                if selected_camera:
                    camera_button = check_if_camera_control_clicked(current_mouse_location)
                    if camera_button != "none":
                        ip_address = extract_ip_from_url(selected_camera)
                        handle_camera_control(camera_button, ip_address)
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

def draw_usage_graph(frame, data, origin, size, color):
    graph_w, graph_h = size
    graph_data = list(data)
    points = []
    for i, val in enumerate(graph_data):
        x = origin[0] + int(i * (graph_w / 60))
        y = origin[1] + graph_h - int(val * (graph_h / 100))
        points.append((x, y))
    if len(points) >= 2:
        cv2.polylines(frame, [np.array(points, dtype=np.int32)], isClosed=False, color=color, thickness=1)
    cv2.rectangle(frame, origin, (origin[0] + graph_w, origin[1] + graph_h), (255, 255, 255), 2)

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
    
    # Update working cameras list - all camera IPs that have valid frames
    working_cameras = [cam_id for cam_id, frame in frames_dict.items() 
                      if frame is not None and frame.size > 0 and len(frame.shape) == 3]
    
    # ensure that the frame exists just incase it's somehow editted before it's ready
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    
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
            object[:] = [215, 120, 0]

            message_no_cameras = "No cameras here (yet)"
            message_no_cameras_hint = "Wait for some streams to load first"

            cv2.putText(object, message_no_cameras, (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(object, message_no_cameras_hint, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.putText(object, ":(", (60, 230), cv2.FONT_HERSHEY_SIMPLEX, 4.9, (255,255,255), 8)

            return object

        cols = int(np.ceil(np.sqrt(count)))
        rows = int(np.ceil(count / cols))

        screen_w = get_raw_screen_resolution()[0]
        screen_h = get_raw_screen_resolution()[1]

        cell_w = screen_w // cols
        cell_h = screen_h // rows

        grid_rows = []

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
        full_grid = cv2.copyMakeBorder(full_grid, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(100, 100, 100))

    elif selected_page == 2:
        # Build the initial frame (again??)
        screen_w, screen_h = get_screen_x(), get_screen_y()
        full_grid = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        full_grid[:] = [100, 50, 100]  # Darker background

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

        
        cv2.rectangle(
            full_grid,
            (activity_area_left, activity_area_top),
            (activity_area_right, activity_area_bottom),
            (70, 70, 70),
            -1
        )


        
        cv2.rectangle(
            full_grid,
            (windowactivity_leftactivity_topleft_x, windowactivity_leftactivity_topleft_y),
            (left_activity_right, left_activity_bottom),
            (70, 60, 50),  # Dark blue-gray
            -1
        )
        

        
        cv2.rectangle(
            full_grid,
            (right_activity_left, windowactivity_rightactivity_topleft_y),
            (right_activity_right, right_activity_bottom),
            (80, 50, 30),  # Dark reddish
            -1
        )
        


        # Info section
        info_section_top = camera_view_bottom + 10
        info_section_bottom = info_section_top + info_section_height - 10

        # Controls section
        controls_section_top = info_section_bottom + 10
        controls_section_bottom = right_panel_bottom

        # Get the heights
        info_section_height = int(right_panel_height * 0.2)
        controls_section_height = right_panel_height - camera_view_height - info_section_height



        # Add section dividers
        cv2.line(full_grid, 
                (right_activity_left, camera_view_bottom), 
                (right_activity_right, camera_view_bottom), 
                (100, 70, 50), 2)
        
        cv2.line(full_grid, 
                (right_activity_left, info_section_bottom), 
                (right_activity_right, info_section_bottom), 
                (100, 70, 50), 2)
        
        cv2.putText(full_grid, "Camera View", 
                   (right_activity_left + 20, camera_view_top + 25), 
                   section_label_font, section_label_scale, (180, 180, 180), 1)
        
        cv2.putText(full_grid, "Camera Details", 
                   (right_activity_left + 20, info_section_top + 25), 
                   section_label_font, section_label_scale, (180, 180, 180), 1)
        
        cv2.putText(full_grid, "Camera Controls (Not Implemented)", 
                   (right_activity_left + 20, controls_section_top + 25), 
                   section_label_font, section_label_scale, (180, 180, 180), 1)

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
                         (40, 40, 60), -1)
            cv2.addWeighted(overlay, 0.7, full_grid, 0.3, 0, full_grid)
        
        # Define column positions with improved spacing
        col1_x = list_left + preview_size + spacing
        col2_x = col1_x + 200  # Shortened to avoid overlap
        col3_x = col2_x + 140  # Shortened to avoid overlap
        col4_x = col3_x + 110  # Shortened to avoid overlap
        col5_x = col4_x + 110  # Position for uptime
        
        # Column headers
        if header_y > 0:
            cv2.putText(full_grid, "Preview", (list_left, header_y), font, small_font_scale, (180, 180, 180), font_thickness)
            cv2.putText(full_grid, "Camera Address", (col1_x, header_y), font, small_font_scale, (180, 180, 180), font_thickness)
            cv2.putText(full_grid, "Location", (col2_x, header_y), font, small_font_scale, (180, 180, 180), font_thickness)
            cv2.putText(full_grid, "Type", (col3_x, header_y), font, small_font_scale, (180, 180, 180), font_thickness)
            cv2.putText(full_grid, "Resolution", (col4_x, header_y), font, small_font_scale, (180, 180, 180), font_thickness)
            cv2.putText(full_grid, "Uptime", (col5_x, header_y), font, small_font_scale, (180, 180, 180), font_thickness)
        
        # Stats bar
        stats_y = min(list_top - 65, resized_height - 120)
        if stats_y > 0:
            # Working camera stats with background
            overlay = full_grid.copy()
            cv2.rectangle(overlay, 
                         (windowactivity_leftactivity_topleft_x, stats_y - 25), 
                         (left_activity_right, stats_y + 5), 
                         (40, 60, 40), -1)
            cv2.addWeighted(overlay, 0.7, full_grid, 0.3, 0, full_grid)
            
            # Show how many cameras are working vs total
            working_count_text = f"Working: {len(working_cameras)}/{len(inputs) if inputs else 0} ({current_list_position + 1}-{min(current_list_position + view_list_visible_address_count, len(working_cameras))})"
            cv2.putText(full_grid, working_count_text, (list_left, stats_y), font, font_scale, (180, 180, 180), font_thickness)

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
                bg_color = (50, 50, 60) if idx % 2 == 0 else (60, 60, 70)  # Alternate dark colors
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
                    cv2.rectangle(overlay, (sel_x1, sel_y1), (sel_x2, sel_y2), (140, 120, 20), -1)  # Goldish highlight
                    cv2.addWeighted(overlay, 0.4, full_grid, 0.6, 0, full_grid)

            # Display preview frame with safety checks
            preview_frame = frames_dict.get(input_id)
            if preview_frame is not None:
                try:
                    # Make sure we have a valid frame
                    if preview_frame.size > 0 and preview_frame.shape[0] > 0 and preview_frame.shape[1] > 0:
                        # Create a copy to avoid modifying the original
                        preview_frame_copy = preview_frame.copy()
                        
                        # Make sure we have a valid destination area
                        if (y + preview_size <= resized_height and 
                            x + preview_size <= resized_width and 
                            y >= 0 and x >= 0):
                            
                            # Resize the frame safely
                            thumb = cv2.resize(preview_frame_copy, (preview_size, preview_size))
                            full_grid[y:y+preview_size, x:x+preview_size] = thumb
                        else:
                            # Draw a placeholder if we can't place the thumbnail
                            if (y + 10 < resized_height and x + 10 < resized_width and 
                                y + preview_size - 10 < resized_height and x + preview_size - 10 < resized_width):
                                cv2.rectangle(full_grid, (x, y), (x + preview_size, y + preview_size), (80, 80, 80), -1)
                            
                except Exception as e:
                    print(f"Error handling preview frame for {input_id}: {e}")
                    # Try to draw a placeholder if possible
                    if (y < resized_height and x < resized_width and 
                        y + preview_size < resized_height and x + preview_size < resized_width):
                        cv2.rectangle(full_grid, (x, y), (x + preview_size, y + preview_size), (80, 80, 80), -1)
            else:
                # Draw placeholder with safety checks
                if (y < resized_height and x < resized_width and 
                    y + preview_size < resized_height and x + preview_size < resized_width):
                    cv2.rectangle(full_grid, (x, y), (x + preview_size, y + preview_size), (80, 80, 80), -1)

            # Extract IP address for geolocation lookup
            ip_address = extract_ip_from_url(input_id)
            
            # Get metadata for this camera
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
                    cv2.putText(full_grid, ip_display, (col1_x, text_y_1), font, small_font_scale, (255, 255, 255), 1)
                
                # Location
                if col2_x < resized_width:
                    loc_display = location[:15] + "..." if len(location) > 18 else location
                    cv2.putText(full_grid, loc_display, (col2_x, text_y_1), font, small_font_scale, (255, 255, 255), 1)
                
                # Stream type
                if col3_x < resized_width:
                    type_text = f"{stream_type}"[:12]
                    cv2.putText(full_grid, type_text, (col3_x, text_y_1), font, small_font_scale, (255, 255, 255), 1)
                
                # Resolution
                if col4_x < resized_width:
                    res_text = resolution[:10]
                    cv2.putText(full_grid, res_text, (col4_x, text_y_1), font, small_font_scale, (255, 255, 255), 1)
                
                # Uptime
                if col5_x < resized_width:
                    cv2.putText(full_grid, uptime_str, (col5_x, text_y_1), font, small_font_scale, (255, 255, 255), 1)
            
            # Row 2 - additional details with smaller font
            text_y_2 = y + 50
            if text_y_2 < resized_height:
                # Camera ID/shorter version
                if col1_x < resized_width:
                    cv2.putText(full_grid, f"ID: {input_id.split('/')[-1]}", (col1_x, text_y_2), font, 0.5, (180, 180, 180), 1)
                
                # Frames info
                if col2_x < resized_width:
                    cv2.putText(full_grid, f"Frames: {frames_received}", (col2_x, text_y_2), font, 0.5, (180, 180, 180), 1)
                
                # Endpoint
                if col3_x < resized_width:
                    end_text = endpoint[:10]
                    cv2.putText(full_grid, end_text, (col3_x, text_y_2), font, 0.5, (180, 180, 180), 1)
                
                # FPS
                if col4_x < resized_width:
                    fps_text = f"FPS: {fps}"
                    cv2.putText(full_grid, fps_text, (col4_x, text_y_2), font, 0.5, (180, 180, 180), 1)
                
                # First seen (shortened)
                if col5_x < resized_width:
                    time_str = time.strftime("%H:%M", time.localtime(first_seen))
                    cv2.putText(full_grid, f"@{time_str}", (col5_x, text_y_2), font, 0.5, (180, 180, 180), 1)

        # Add in the scroll button rectangles with proper arrows
        # Scroll Up button with improved styling
        button_color = (60, 100, 120)
        cv2.rectangle(full_grid, 
                     (button_list_scrollup_topleft_x, button_list_scrollup_topleft_y),
                     (button_list_scrollup_bottomright_x, button_list_scrollup_bottomright_y), 
                     button_color, -1)
        # Add a button border
        cv2.rectangle(full_grid, 
                     (button_list_scrollup_topleft_x, button_list_scrollup_topleft_y),
                     (button_list_scrollup_bottomright_x, button_list_scrollup_bottomright_y), 
                     (120, 160, 180), 1)
        # Up arrow symbol
        cv2.putText(full_grid, UP_ARROW, 
                    (button_list_scrollup_topleft_x + 17, button_list_scrollup_topleft_y + 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Scroll Down button with improved styling
        cv2.rectangle(full_grid, 
                     (button_list_scrolldn_topleft_x, button_list_scrolldn_topleft_y),
                     (button_list_scrolldn_bottomright_x, button_list_scrolldn_bottomright_y), 
                     button_color, -1)
        # Add a button border
        cv2.rectangle(full_grid, 
                     (button_list_scrolldn_topleft_x, button_list_scrolldn_topleft_y),
                     (button_list_scrolldn_bottomright_x, button_list_scrolldn_bottomright_y), 
                     (120, 160, 180), 1)
        # Down arrow symbol
        cv2.putText(full_grid, DOWN_ARROW, 
                    (button_list_scrolldn_topleft_x + 17, button_list_scrolldn_topleft_y + 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        
        # Display local time at bottom right
        current_time = time.strftime("%H:%M:%S", time.localtime())
        time_text = f"Local Time: {current_time}"
        time_size = cv2.getTextSize(time_text, font, 0.7, 2)[0]
        time_x = resized_width - time_size[0] - 20
        time_y = resized_height - 20
        
        # Background for time display
        time_bg_width = time_size[0] + 20
        time_bg_height = time_size[1] + 10
        cv2.rectangle(full_grid, 
                     (time_x - 10, time_y - time_bg_height + 5), 
                     (time_x + time_bg_width - 10, time_y + 5), 
                     (40, 40, 60), -1)
    
    # Add the graphical part of the buttons - with bounds checking
    screen_width = full_grid.shape[1]
    button1_x1 = min(button_page_1_topleft_x, screen_width - 300)
    button1_x2 = min(button_page_1_bottomright_x, screen_width - 50)
    button2_x1 = min(button_page_2_topleft_x, screen_width - 300)
    button2_x2 = min(button_page_2_bottomright_x, screen_width - 50)
    
    cv2.rectangle(full_grid, (button1_x1, button_page_1_topleft_y), 
                 (button1_x2, button_page_1_bottomright_y), (0, 150, 100), -1)
    cv2.rectangle(full_grid, (button2_x1, button_page_2_topleft_y), 
                 (button2_x2, button_page_2_bottomright_y), (200, 150, 100), -1)

    text_font = cv2.FONT_HERSHEY_SIMPLEX
    text_scale = 0.7
    text_thickness = 2
    text_color = (255, 255, 255)

    text1 = "Matrix View"
    text2 = "List View"

    text1_size = cv2.getTextSize(text1, text_font, text_scale, text_thickness)[0]
    text2_size = cv2.getTextSize(text2, text_font, text_scale, text_thickness)[0]

    text1_x = button1_x1 + (min(250, button1_x2 - button1_x1) - text1_size[0]) // 2
    text1_y = button_page_1_topleft_y + (40 + text1_size[1]) // 2

    text2_x = button2_x1 + (min(250, button2_x2 - button2_x1) - text2_size[0]) // 2
    text2_y = button_page_2_topleft_y + (40 + text2_size[1]) // 2

    cv2.putText(full_grid, text1, (text1_x, text1_y), text_font, text_scale, text_color, text_thickness)
    cv2.putText(full_grid, text2, (text2_x, text2_y), text_font, text_scale, text_color, text_thickness)

    height, width = full_grid.shape[:2]

    # Global styling layout variables
    graph_padding_offset = 40

    # Top left information center
    information_center_width = 400

    # Draw the background
    cv2.rectangle(full_grid, (graph_padding_offset, 0), 
                 (min(information_center_width + graph_padding_offset, width), graph_padding_offset), 
                 (150, 150, 100), -1)

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

    # Write the text
    # Ensure we use a consistent font scale here
    camera_count = get_camera_text(len(frames_dict))
    camera_font_scale = 0.7
    cv2.putText(full_grid, camera_count, (graph_padding_offset, 30), cv2.FONT_HERSHEY_SIMPLEX, camera_font_scale, (255, 255, 255), 1, cv2.LINE_AA)

    # Graph settings (usage graphs, bottom left of the full screen view tucked into the )
    graph_width, graph_height = 180, 40
    graphs_background_box_width = min(730, width - graph_padding_offset - 50)
    
    # Draw the background for the bottom left section
    cv2.rectangle(full_grid, (graph_padding_offset, height - 40), 
                 (min(graph_padding_offset + graphs_background_box_width, width), height), 
                 (150, 150, 100), -1)

    # Only draw graphs if we have enough space
    if graph_padding_offset + graph_width + 250 < width:
        # Graph 1
        graph1_x = 160
        graph1_y = height - graph_height
        
        cpu_graph_label = "SYS CPU:"
        
        cv2.putText(full_grid, cpu_graph_label, (graph1_x - 120, graph1_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        draw_usage_graph(full_grid, cpu_usage_history, (graph1_x, graph1_y), (graph_width, graph_height), (0, 255, 0))

        # Graph 2 - only if we have space
        if graph1_x + graph_width + 250 + graph_width < width:
            graph2_x = graph1_x + graph_width + 250
            graph2_y = graph1_y
            cpu_graph_label = "PROGRAM MEMORY:"

            cv2.putText(full_grid, cpu_graph_label, (graph2_x - 240, graph2_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            draw_usage_graph(full_grid, mem_usage_history, (graph2_x, graph2_y), (graph_width, graph_height), (0, 128, 255))
    
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
        
        # Use fixed dimensions and aspect ratio for stability
        panel_width = right_panel_right - right_panel_left
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
        
        # Calculate centering position
        x_offset = right_panel_left + (panel_width - display_width) // 2
        y_offset = camera_view_top + (panel_height - display_height) // 2
        
        # Create a region of interest in the full grid
        if (y_offset >= 0 and x_offset >= 0 and 
            y_offset + display_height <= full_grid.shape[0] and 
            x_offset + display_width <= full_grid.shape[1]):
            
            full_grid[y_offset:y_offset+display_height, x_offset:x_offset+display_width] = display_frame
        
        # Add camera details and controls to the respective sections
        full_grid = display_camera_details_and_controls(
            frames_dict, full_grid, selected_camera,
            right_panel_left, right_panel_right,
            info_section_top, info_section_bottom,
            controls_section_top, controls_section_bottom
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
def display_camera_details_and_controls(frames_dict, full_grid, selected_camera, 
                                      right_activity_left, right_activity_right,
                                      info_section_top, info_section_bottom,
                                      controls_section_top, controls_section_bottom):
    """Displays simplified camera information and control interface in the right panel"""
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
    
    # TODO: Make this cleaner in a table on the left and ensure data e.g. location is present and not always unknown

    # Extract IP address for controls
    ip_address = extract_ip_from_url(selected_camera)
    
    # Get minimal camera info
    meta = camera_metadata.get(selected_camera, {})
    resolution = meta.get("resolution", "Unknown")
    fps = meta.get("fps", 0)
    
    # Info section - simplified
    # Draw a simple header with minimal information
    info_bg = full_grid.copy()
    cv2.rectangle(info_bg, 
                 (right_activity_left, info_section_top), 
                 (right_activity_right, info_section_bottom), 
                 (40, 40, 50), -1)
    cv2.addWeighted(info_bg, 0.6, full_grid, 0.4, 0, full_grid)
    
    # Camera title
    title_y = info_section_top + 30
    camera_title = f"Camera: {selected_camera.split('/')[-1]}"
    cv2.putText(full_grid, camera_title, 
               (right_activity_left + 20, title_y), 
               font, font_scale, (200, 200, 220), 2)
    
    # Resolution and FPS
    info_y = title_y + 35
    stats_text = f"Resolution: {resolution} | FPS: {fps}"
    cv2.putText(full_grid, stats_text, 
               (right_activity_left + 20, info_y), 
               font, font_scale * 0.9, font_color, font_thickness)
    
    # IP address
    ip_y = info_y + 30
    ip_text = f"IP: {ip_address}"
    cv2.putText(full_grid, ip_text, 
               (right_activity_left + 20, ip_y), 
               font, font_scale * 0.9, font_color, font_thickness)
    

    # TODO: Make this more clear on the right side and add a divisor line between it and the camera inforamation table

    # Controls section - simplified and more prominent
    controls_bg = full_grid.copy()
    cv2.rectangle(controls_bg, 
                 (right_activity_left, controls_section_top), 
                 (right_activity_right, controls_section_bottom), 
                 (50, 50, 60), -1)
    cv2.addWeighted(controls_bg, 0.7, full_grid, 0.3, 0, full_grid)
    
    # Header
    controls_title_y = controls_section_top + 30
    cv2.putText(full_grid, "Camera Controls", 
               (right_activity_left + 20, controls_title_y), 
               font, font_scale, (200, 200, 220), 2)
    
    # Calculate center for control buttons
    panel_width = right_activity_right - right_activity_left
    panel_center_x = right_activity_left + panel_width // 2
    button_size = 60  # Larger buttons for better visibility and usability
    button_spacing = 70
    
    # Calculate vertical position for controls
    controls_y = controls_title_y + 70
    
    # Button colors
    button_color = (70, 100, 130)  # More visible blue color
    button_border = (120, 160, 200)  # Lighter border
    text_color = (255, 255, 255)  # White text
    
    # Draw the control buttons in a D-pad layout
    
    # Up button
    up_btn_x = panel_center_x - button_size // 2
    up_btn_y = controls_y - button_spacing
    cv2.rectangle(full_grid, 
                 (up_btn_x, up_btn_y), 
                 (up_btn_x + button_size, up_btn_y + button_size), 
                 button_color, -1)
    cv2.rectangle(full_grid, 
                 (up_btn_x, up_btn_y), 
                 (up_btn_x + button_size, up_btn_y + button_size), 
                 button_border, 2)
    cv2.putText(full_grid, UP_ARROW, 
               (up_btn_x + button_size//2 - 5, up_btn_y + button_size//2 + 5), 
               font, 1.2, text_color, 2)
    
    # Left button
    left_btn_x = panel_center_x - button_spacing - button_size // 2
    left_btn_y = controls_y
    cv2.rectangle(full_grid, 
                 (left_btn_x, left_btn_y), 
                 (left_btn_x + button_size, left_btn_y + button_size), 
                 button_color, -1)
    cv2.rectangle(full_grid, 
                 (left_btn_x, left_btn_y), 
                 (left_btn_x + button_size, left_btn_y + button_size), 
                 button_border, 2)
    cv2.putText(full_grid, LEFT_ARROW, 
               (left_btn_x + button_size//2 - 5, left_btn_y + button_size//2 + 5), 
               font, 1.2, text_color, 2)
    
    # Right button
    right_btn_x = panel_center_x + button_spacing - button_size // 2
    right_btn_y = controls_y
    cv2.rectangle(full_grid, 
                 (right_btn_x, right_btn_y), 
                 (right_btn_x + button_size, right_btn_y + button_size), 
                 button_color, -1)
    cv2.rectangle(full_grid, 
                 (right_btn_x, right_btn_y), 
                 (right_btn_x + button_size, right_btn_y + button_size), 
                 button_border, 2)
    cv2.putText(full_grid, RIGHT_ARROW, 
               (right_btn_x + button_size//2 - 5, right_btn_y + button_size//2 + 5), 
               font, 1.2, text_color, 2)
    
    # Down button
    down_btn_x = panel_center_x - button_size // 2
    down_btn_y = controls_y + button_spacing
    cv2.rectangle(full_grid, 
                 (down_btn_x, down_btn_y), 
                 (down_btn_x + button_size, down_btn_y + button_size), 
                 button_color, -1)
    cv2.rectangle(full_grid, 
                 (down_btn_x, down_btn_y), 
                 (down_btn_x + button_size, down_btn_y + button_size), 
                 button_border, 2)
    cv2.putText(full_grid, DOWN_ARROW, 
               (down_btn_x + button_size//2 - 5, down_btn_y + button_size//2 + 5), 
               font, 1.2, text_color, 2)
    
    # Zoom controls - bottom row
    zoom_y = down_btn_y + button_spacing + 20
    
    # Zoom in button
    zoom_in_x = panel_center_x - button_spacing
    zoom_in_y = zoom_y
    cv2.rectangle(full_grid, 
                 (zoom_in_x, zoom_in_y), 
                 (zoom_in_x + button_size, zoom_in_y + button_size), 
                 button_color, -1)
    cv2.rectangle(full_grid, 
                 (zoom_in_x, zoom_in_y), 
                 (zoom_in_x + button_size, zoom_in_y + button_size), 
                 button_border, 2)
    cv2.putText(full_grid, PLUS_SYMBOL, 
               (zoom_in_x + button_size//2 - 5, zoom_in_y + button_size//2 + 5), 
               font, 1.2, text_color, 2)
    
    # Zoom out button
    zoom_out_x = panel_center_x + button_spacing - button_size
    zoom_out_y = zoom_y
    cv2.rectangle(full_grid, 
                 (zoom_out_x, zoom_out_y), 
                 (zoom_out_x + button_size, zoom_out_y + button_size), 
                 button_color, -1)
    cv2.rectangle(full_grid, 
                 (zoom_out_x, zoom_out_y), 
                 (zoom_out_x + button_size, zoom_out_y + button_size), 
                 button_border, 2)
    cv2.putText(full_grid, MINUS_SYMBOL, 
               (zoom_out_x + button_size//2 - 5, zoom_out_y + button_size//2 + 5), 
               font, 1.2, text_color, 2)
    
    # Add "Controls Active" status
    status_y = zoom_y + button_size + 30
    cv2.putText(full_grid, "Camera controls ready", 
               (panel_center_x - 100, status_y), 
               font, 0.7, (100, 200, 100), 1)
    
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

# Function to check if a camera control button was clicked
def check_if_camera_control_clicked(point):
    """Check if a camera control button was clicked"""
    # If we're not in list view or no camera is selected, return none
    if selected_page != 2 or not selected_camera:
        return "none"
    
    # Make sure we're in the controls section
    if point[1] < controls_section_top or point[1] > controls_section_bottom:
        return "none"
    
    if point[0] < right_panel_left or point[0] > right_panel_right:
        return "none"
    
    # Calculate button positions similar to how they're drawn
    # Header
    controls_title_y = controls_section_top + 30
    
    # Calculate center for control buttons
    panel_width = right_panel_right - right_panel_left
    panel_center_x = right_panel_left + panel_width // 2
    button_size = 60
    button_spacing = 70
    
    # Calculate vertical position for controls
    controls_y = controls_title_y + 70
    
    # Check each button
    
    # Up button
    up_btn_x = panel_center_x - button_size // 2
    up_btn_y = controls_y - button_spacing
    if up_btn_x <= point[0] <= up_btn_x + button_size and up_btn_y <= point[1] <= up_btn_y + button_size:
        return "up"
    
    # Left button
    left_btn_x = panel_center_x - button_spacing - button_size // 2
    left_btn_y = controls_y
    if left_btn_x <= point[0] <= left_btn_x + button_size and left_btn_y <= point[1] <= left_btn_y + button_size:
        return "left"
    
    # Right button
    right_btn_x = panel_center_x + button_spacing - button_size // 2
    right_btn_y = controls_y
    if right_btn_x <= point[0] <= right_btn_x + button_size and right_btn_y <= point[1] <= right_btn_y + button_size:
        return "right"
    
    # Down button
    down_btn_x = panel_center_x - button_size // 2
    down_btn_y = controls_y + button_spacing
    if down_btn_x <= point[0] <= down_btn_x + button_size and down_btn_y <= point[1] <= down_btn_y + button_size:
        return "down"
    
    # Zoom controls - bottom row
    zoom_y = down_btn_y + button_spacing + 20
    
    # Zoom in button
    zoom_in_x = panel_center_x - button_spacing
    zoom_in_y = zoom_y
    if zoom_in_x <= point[0] <= zoom_in_x + button_size and zoom_in_y <= point[1] <= zoom_in_y + button_size:
        return "zoom_in"
    
    # Zoom out button
    zoom_out_x = panel_center_x + button_spacing - button_size
    zoom_out_y = zoom_y
    if zoom_out_x <= point[0] <= zoom_out_x + button_size and zoom_out_y <= point[1] <= zoom_out_y + button_size:
        return "zoom_out"
    
    return "none"

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

def main():
    try:
        download_ip2loc_db_if_not_exists()
        ranges, countries = load_ip2loc_db()
    except Exception as e:
        logging.error(f"Error loading IP database: {e}")
        ranges, countries = [], []

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
        
        # Define font settings
        font = cv2.FONT_HERSHEY_DUPLEX  # Changed to DUPLEX for a more normal font
        font_scale = 1.0
        font_thickness = 2
        font_color = (255, 255, 255)
        
        # Draw error icon in top right
        icon_size = 80
        margin = 30
        icon_x = screen_w - icon_size - margin
        icon_y = margin
        
        # Draw a warning triangle
        triangle_pts = np.array([
            [icon_x + icon_size//2, icon_y],
            [icon_x, icon_y + icon_size],
            [icon_x + icon_size, icon_y + icon_size]
        ], np.int32)
        
        cv2.fillPoly(error_frame, [triangle_pts], (0, 0, 255))
        cv2.polylines(error_frame, [triangle_pts], True, (255, 255, 255), 2)
        
        # Draw exclamation mark inside triangle
        cv2.putText(error_frame, "!", 
                    (icon_x + icon_size//2 - 5, icon_y + icon_size - 20), 
                    font, 1.2, (255, 255, 255), 3)
        
        # Draw title - Changed to FATAL EXCEPTION
        title_text = "FATAL EXCEPTION"
        title_scale = 1.5
        title_thickness = 3
        title_size = cv2.getTextSize(title_text, font, title_scale, title_thickness)[0]
        title_x = (screen_w - title_size[0]) // 2
        title_y = margin + 80
        
        # Draw title text (without gradient)
        cv2.putText(error_frame, title_text, (title_x, title_y), 
                    font, title_scale, (0, 0, 255), title_thickness)
        cv2.putText(error_frame, title_text, (title_x, title_y), 
                    font, title_scale, (255, 255, 255), 1)
        
        # Process error info
        if isinstance(error_text, Exception):
            error_name = type(error_text).__name__
            error_description = str(error_text)
            
            # Extract stack trace
            stack_trace = traceback.format_exc().split("\n")
            
            # Draw error type and message
            cv2.putText(error_frame, f"Type: {error_name}", 
                        (50, title_y + 70), font, font_scale, (255, 50, 50), font_thickness)
            
            # Wrap error description
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
            
            # Draw stack trace with line numbers and box
            trace_y = title_y + 120 + len(desc_lines)*40 + 50
            cv2.putText(error_frame, "Stack Trace:", 
                        (50, trace_y), font, font_scale, (100, 200, 255), font_thickness)
            
            # Calculate stack trace box dimensions
            trace_line_count = min(8, len(stack_trace)) + 1  # +1 for the header
            box_height = trace_line_count * 30 + 20  # height based on number of lines + padding
            box_width = screen_w - 100  # width with margins
            box_x = 40
            box_y = trace_y + 10
            
            # Draw stack trace box
            cv2.rectangle(error_frame, (box_x, box_y), (box_x + box_width, box_y + box_height), 
                        (40, 40, 80), -1)  # Fill
            cv2.rectangle(error_frame, (box_x, box_y), (box_x + box_width, box_y + box_height), 
                        (100, 100, 180), 2)  # Border
            
            # Draw stack trace lines
            trace_y += 40
            for i, line in enumerate(stack_trace):
                if i >= 8:  # Limit number of stack trace lines
                    cv2.putText(error_frame, "...", 
                                (60, trace_y + i*30), font, 0.8, (150, 150, 150), 1)
                    break
                    
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Extract line numbers when available
                if "line" in line and "File" in line:
                    # Split the line to highlight parts
                    parts = line.split(", line ")
                    if len(parts) > 1:
                        file_part = parts[0]
                        line_part = "line " + parts[1]
                        
                        # Draw file part in one color
                        cv2.putText(error_frame, file_part, 
                                    (60, trace_y + i*30), font, 0.7, (180, 180, 255), 1)
                        
                        # Calculate where to start the line number part
                        file_width = cv2.getTextSize(file_part, font, 0.7, 1)[0][0]
                        
                        # Draw line number part in a different color
                        cv2.putText(error_frame, ", " + line_part, 
                                    (60 + file_width, trace_y + i*30), font, 0.7, (255, 180, 180), 1)
                    else:
                        cv2.putText(error_frame, line, 
                                    (60, trace_y + i*30), font, 0.7, (180, 180, 255), 1)
                else:
                    cv2.putText(error_frame, line, 
                                (60, trace_y + i*30), font, 0.7, (200, 200, 200), 1)
        else:
            # For non-exception errors
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
        
        # Python jokes
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
        
        # Initialize joke if it hasn't been selected yet
        if _selected_python_joke is None:
            _selected_python_joke = random.choice(python_jokes)
        
        # Use consistent joke across multiple calls
        joke = _selected_python_joke
        joke_size = cv2.getTextSize(joke, font, 0.7, 1)[0]
        joke_x = (screen_w - joke_size[0]) // 2
        joke_y = screen_h - 80
        
        # Draw joke with slight transparency effect
        cv2.putText(error_frame, joke, (joke_x, joke_y), font, 0.7, (100, 100, 100), 1)
        
        # Draw timestamp
        timestamp = f"Time: {time.strftime('%H:%M:%S - %Y-%m-%d')}"
        cv2.putText(error_frame, timestamp, (20, screen_h - 20), font, 0.7, (150, 150, 150), 1)
        
        return error_frame

    while True:
        try:
            with lock:
                global current_list_position
                
                # Ensure the position is valid based on actual working camera count
                max_position = get_safe_max_position()
                current_list_position = max(0, min(current_list_position, max_position))
                
                try:
                    listinput = get_ip_range(IP_LIST_FILE, current_list_position + 1, current_list_position + view_list_visible_address_count + 1)
                    grid = layout_frames(frames, borders, labels, selected_page=selected_page, inputs=listinput)
                    
                    # Apply popups directly to the frame
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
    main()
