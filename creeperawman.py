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
    import tkinter as tk
    import re
    import zipfile
    import csv
    import ipaddress
    from bisect import bisect_right
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
button_list_scrollup_topleft_x = 940
button_list_scrollup_topleft_y = get_raw_screen_resolution()[1] - 140
button_list_scrollup_bottomright_x = 980
button_list_scrollup_bottomright_y = get_raw_screen_resolution()[1] - 100

# Scroll Down Button
button_list_scrolldn_topleft_x = 940
button_list_scrolldn_topleft_y = get_raw_screen_resolution()[1] - 80
button_list_scrolldn_bottomright_x = 980
button_list_scrolldn_bottomright_y = get_raw_screen_resolution()[1] - 40

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
    with open(filename) as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines[start - 1:end]

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

    if check_in_bounding_box(point, [button_page_1_topleft_x, button_page_1_topleft_y], [button_page_1_bottomright_x, button_page_1_bottomright_y]):
        return 1
    if check_in_bounding_box(point, [button_page_2_topleft_x, button_page_2_topleft_y], [button_page_2_bottomright_x, button_page_2_bottomright_y]):
        return 2
    return 0

def show_popup(color="yellow", text="notext", duration=200):
    def popup():
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=color)
        width, height = 200, 50
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = screen_width - width - 20
        y = screen_height - height - 60
        root.geometry(f"{width}x{height}+{x}+{y}")
        label = tk.Label(root, text=text, bg=color, fg="black", font=("Arial", 12))
        label.pack(expand=True)
        root.after(duration, root.destroy)
        root.mainloop()
    threading.Thread(target=popup).start()

def click_handler():
    global selected_page
    current_mouse_location = get_current_cursor_position()
    button_reaction = check_if_in_button_area(current_mouse_location)

    show_popup(text=current_mouse_location)

    if button_reaction == 1:
        # show_popup(text="Button 1 clicked!\n")
        selected_page = 1
    elif button_reaction == 2:
        # show_popup(text="Button 2 clicked!")
        selected_page = 2


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

def format_uptime(seconds):
    units = [
        ('month', 30 * 24 * 3600),
        ('week', 7 * 24 * 3600),
        ('day', 24 * 3600),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1)
    ]
    parts = []
    for name, count in units:
        value = seconds // count
        if value:
            seconds %= count
            parts.append(f"{int(value)} {name}{'s' if value != 1 else ''}")
    return ', '.join(parts)

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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            print(f"[{input_id}] Starting JPEG poll stream: {full_url}")
            while True:
                try:
                    req = urllib.request.Request(full_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        # Read with a size limit to prevent extremely large images
                        img_data = resp.read(10 * 1024 * 1024)  # 10MB limit
                        
                        # Validate we actually got data
                        if not img_data:
                            raise ValueError("Empty image data received")
                            
                        img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                        
                        # Use IMREAD_COLOR to ensure consistent 3-channel output
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                        if frame is not None and frame.size > 0:
                            # Verify frame dimensions are reasonable
                            if frame.shape[0] > 0 and frame.shape[1] > 0 and frame.shape[2] == 3:
                                # Safely copy the frame to prevent memory issues
                                safe_frame = frame.copy()
                                with lock:
                                    frames[input_id] = safe_frame
                            else:
                                print(f"[{input_id}] Invalid frame dimensions: {frame.shape}")
                        else:
                            print(f"[{input_id}] Failed to decode image")
                            
                except Exception as e:
                    print(f"[{input_id}] JPEG poll error: {e}")
                    time.sleep(0.1)
    except Exception as e:
        print(f"[{input_id}] Stream error: {e}")
        time.sleep(0.1)


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

def layout_frames(frames_dict, borders_dict, labels_dict, selected_page, inputs):
    # ensure that the frame exists just incase it's somehow editted before it's ready
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    if selected_page == 1:
        global last_update_time
        if time.time() - last_update_time >= 1:
            cpu_usage_history.append(psutil.cpu_percent())
            mem_usage_history.append(min(psutil.Process().memory_info().rss / psutil.virtual_memory().total * 100, 100))
            last_update_time = time.time()
        frames = list(frames_dict.items())
        count = len(frames)
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
                original_height, original_width = frame.shape[:2]
                resolution_text = f"{original_width}x{original_height}"

                # Safe resize to avoid buffer overflow
                try:
                    # Create a copy to avoid modifying the original frame
                    frame_copy = frame.copy()
                    
                    # Check for valid dimensions before resizing
                    if cell_w <= 6 or cell_h <= 6:
                        frame = np.zeros((max(1, cell_h - 6), max(1, cell_w - 6), 3), dtype=np.uint8)
                    else:
                        # Safe resize with error handling
                        try:
                            frame = cv2.resize(frame_copy, (cell_w - 6, cell_h - 6))
                        except cv2.error:
                            # Fallback to a safer method if standard resize fails
                            frame = np.zeros((cell_h - 6, cell_w - 6, 3), dtype=np.uint8)
                            smaller_dim = min(frame_copy.shape[1], cell_w - 6), min(frame_copy.shape[0], cell_h - 6)
                            if smaller_dim[0] > 0 and smaller_dim[1] > 0:
                                small_frame = cv2.resize(frame_copy, smaller_dim)
                                frame[:smaller_dim[1], :smaller_dim[0]] = small_frame
                except Exception as e:
                    print(f"Error resizing frame for {url}: {e}")
                    # Fallback to a safe black frame if resize fails
                    frame = np.zeros((max(1, cell_h - 6), max(1, cell_w - 6), 3), dtype=np.uint8)
                
                resized_height, resized_width = frame.shape[:2]
                
                label = labels_dict.get(url, url)
                
                scale_factor = resized_height / 480
                
                font_scale = max(0.3, 0.55 * scale_factor)
                
                top_box_h = max(12, int(25 * scale_factor))
                bottom_box_h = max(12, int(25 * scale_factor))
                
                cv2.rectangle(frame, (0, 0), (resized_width, top_box_h), (0, 0, 0), -1)
                cv2.putText(frame, label, (5, top_box_h - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.rectangle(frame, (0, resized_height - bottom_box_h), (resized_width, resized_height), (0, 0, 0), -1)
                cv2.putText(frame, resolution_text, (5, resized_height - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)
                
                bordered = cv2.copyMakeBorder(frame, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=borders_dict.get(url, (0, 255, 0)))
                row_imgs.append(bordered)
            row = np.hstack(row_imgs)
            grid_rows.append(row)

        full_grid = np.vstack(grid_rows)
        full_grid = cv2.copyMakeBorder(full_grid, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(100, 100, 100))

    elif selected_page == 2:
        # Create grid with a fixed size to avoid resizing issues
        screen_w, screen_h = get_screen_x(), get_screen_y()
        full_grid = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        full_grid[:] = [120, 120, 120]
        
        # Make sure we use dimensions that won't cause buffer overflows
        resized_height, resized_width = full_grid.shape[:2]
        scale_factor = min(1.0, resized_height / 480)  # Limit the scale factor
        font_scale = max(0.3, min(0.55 * scale_factor, 0.7))  # Limit font scale
        font_thickness = 1
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Draw the main activity area
        activity_area_top = min(windowactivity_topleft_y, resized_height - 100)
        activity_area_bottom = min(windowactivity_bottomright_y, resized_height - 50)
        activity_area_left = min(windowactivity_topleft_x, resized_width - 100)
        activity_area_right = min(windowactivity_bottomright_x, resized_width - 50)
        
        cv2.rectangle(
            full_grid,
            (activity_area_left, activity_area_top),
            (activity_area_right, activity_area_bottom),
            (0, 0, 0),
            -1
        )

        # Calculate left and right activity areas with bounds checking
        left_activity_right = min(windowactivity_leftactivity_bottomright_x, resized_width - 100)
        left_activity_bottom = min(windowactivity_leftactivity_bottomright_y, resized_height - 50)
        
        cv2.rectangle(
            full_grid,
            (windowactivity_leftactivity_topleft_x, windowactivity_leftactivity_topleft_y),
            (left_activity_right, left_activity_bottom),
            (0, 255, 0),
            -1
        )
        
        right_activity_left = min(windowactivity_rightactivity_topleft_x, resized_width - 200)
        right_activity_right = min(windowactivity_rightactivity_bottomright_x, resized_width - 50)
        right_activity_bottom = min(windowactivity_rightactivity_bottomright_y, resized_height - 50)
        
        cv2.rectangle(
            full_grid,
            (right_activity_left, windowactivity_rightactivity_topleft_y),
            (right_activity_right, right_activity_bottom),
            (0, 0, 255),
            -1
        )

        # Set up list view parameters with bounds checking
        list_left = min(windowactivity_leftactivity_topleft_x + 20, resized_width - 300)
        list_top = min(windowactivity_leftactivity_topleft_y + 80, resized_height - 200)
        row_height = min(90, (resized_height - list_top - 100) // 10)  # Limit rows to fit screen
        preview_size = min(80, row_height - 10)  # Make sure preview fits in row
        spacing = 10

        # Safely place text with bounds checking
        safe_text_top = min(list_top - 50, resized_height - 100)
        if safe_text_top > 0:
            cv2.putText(full_grid, "Preview", (list_left, safe_text_top), font, font_scale, (255, 255, 255), font_thickness)
        
        column_1_x = min(list_left + preview_size + spacing, resized_width - 300)
        column_2_x = min(list_left + preview_size + 280, resized_width - 200)
        column_3_x = min(list_left + preview_size + 530, resized_width - 100)
        
        safe_text_top_2 = min(list_top - 20, resized_height - 80)
        if safe_text_top_2 > 0:
            cv2.putText(full_grid, "Address", (column_1_x, safe_text_top_2), font, font_scale, (255, 255, 255), font_thickness)
            cv2.putText(full_grid, "Location", (column_2_x, safe_text_top_2), font, font_scale, (255, 255, 255), font_thickness)
            cv2.putText(full_grid, "Resolution", (column_3_x, safe_text_top_2), font, font_scale, (255, 255, 255), font_thickness)

        # Calculate how many rows we can safely display
        max_rows = min(10, (resized_height - list_top - 50) // row_height)
        visible_ips = inputs[:max_rows] if inputs else []

        for idx, input_id in enumerate(visible_ips):
            y = list_top + idx * row_height
            
            # Skip if we're out of bounds
            if y + preview_size > resized_height:
                break
                
            x = list_left

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
            
            # Safely place text with bounds checking
            text_y_1 = y + 45
            if text_y_1 < resized_height and column_1_x < resized_width:
                # Truncate text if needed
                ip_display = ip_address
                if len(ip_display) > 25:  # Prevent long text from causing issues
                    ip_display = ip_display[:22] + "..."
                cv2.putText(full_grid, ip_display, (column_1_x, text_y_1), font, 0.7, (255, 255, 255), font_thickness)

            # Get geolocation data
            location = get_geolocation(ip_address)
            
            # Get resolution if the frame exists
            resolution_text = "Unknown"
            if preview_frame is not None:
                try:
                    height, width = preview_frame.shape[:2]
                    resolution_text = f"{width}x{height}"
                except Exception as e:
                    print(f"Error getting resolution for {input_id}: {e}")
                    resolution_text = "Error"

            # Safely place text with bounds checking
            text_y_2 = y + 30
            if text_y_2 < resized_height:
                # Truncate location text if needed
                if len(location) > 20:  # Prevent long text from causing issues
                    location = location[:17] + "..."
                
                if column_2_x < resized_width:
                    cv2.putText(full_grid, location, (column_2_x, text_y_2), font, font_scale, (255, 255, 255), font_thickness)
                
                if column_3_x < resized_width:
                    cv2.putText(full_grid, resolution_text, (column_3_x, text_y_2), font, font_scale, (255, 255, 255), font_thickness)

    # Rest of the function remains the same
    uptime = time.time() - start_time
    
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
        if numcams == 1:
            return "1 cam online"
        else:
            return f"{numcams} cams online"

    camera_count = get_camera_text(len(frames_dict))

    # Write the text
    cv2.putText(full_grid, camera_count, (graph_padding_offset, 30), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

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

    return final_full_grid

def main():
    # Aquire la data
    download_ip2loc_db_if_not_exists()

    ranges, countries = load_ip2loc_db()

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

    while True:
        with lock:
            listinput = get_ip_range("rawips.txt", 1, 10)
            grid = layout_frames(frames, borders, labels, selected_page=selected_page, inputs=listinput)
        cv2.imshow("SilverFlag Stream Viewer", grid)
        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_on_click(click_handler)
    main()
