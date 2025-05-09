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
except ImportError as e:
    print("Did you run 'pip3 install -r requirements.txt? You are missing something.'")
    print(f"Missing package {e}")

logging.basicConfig(level=logging.DEBUG)

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

def test_output():
    start_on_click(show_popup(text=str(get_current_cursor_position())))
    print(str(get_current_cursor_position()))

def start_on_click(target_func):
    triggered = False

    def on_click(x, y, button, pressed):
        nonlocal triggered
        if pressed and not triggered:
            triggered = True
            threading.Thread(target=target_func, daemon=True).start()

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

def get_current_cursor_position():
    return pyautogui.position()

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
                        img_array = np.asarray(bytearray(resp.read()), dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                        if frame is not None:
                            with lock:
                                frames[input_id] = frame
                except Exception as e:
                    print(f"[{input_id}] JPEG poll error: {e}")
                time.sleep(0.1)

        else:
            print(f"[{input_id}] Opening stream with OpenCV: {full_url}")
            cap = cv2.VideoCapture(full_url)
            if not cap.isOpened():
                print(f"[{input_id}] Failed to open stream")
                return
            print(f"[{input_id}] Successfully opened stream")
            while True:
                ret, frame = cap.read()
                if not ret:
                    print(f"[{input_id}] Frame read failed, ending stream")
                    break
                with lock:
                    frames[input_id] = frame
                time.sleep(0.03)
            cap.release()
    except Exception as outer:
        print(f"[{input_id}] Fatal error: {outer}")
    finally:
        with lock:
            frames.pop(input_id, None)
            borders.pop(input_id, None)
        print(f"[{input_id}] Stream handler exiting")

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

def layout_frames(frames_dict, borders_dict, labels_dict):
    global last_update_time
    if time.time() - last_update_time >= 1:
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
    
    screen_w, screen_h = get_screen_x(), get_screen_y()

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

            frame = cv2.resize(frame, (cell_w - 6, cell_h - 6))
            
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
    
    uptime = time.time() - start_time
    


    height, width = full_grid.shape[:2]

    # Global styling layout variables
    graph_padding_offset = 40

    # Top left information center
    information_center_width = 400

    # Draw the background frfr
    cv2.rectangle(full_grid, (graph_padding_offset, 0), (information_center_width + graph_padding_offset, graph_padding_offset), (150, 150, 100), -1)

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
    graphs_background_box_width = 730
    
    # Draw the background for the bottom left section
    cv2.rectangle(full_grid, (graph_padding_offset, height - 40), (graph_padding_offset + graphs_background_box_width, height), (150, 150, 100), -1)

    # Graph 1
    graph1_x = 160
    
    graph1_y = height - graph_height
    
    cpu_graph_label = "SYS CPU:"
    
    cv2.putText(full_grid, cpu_graph_label, (graph1_x - 120, graph1_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    draw_usage_graph(full_grid, cpu_usage_history, (graph1_x, graph1_y), (graph_width, graph_height), (0, 255, 0))

    # Graph 2
    graph2_x = graph1_x + graph_width + 250
    graph2_y = graph1_y
    cpu_graph_label = "PROGRAM MEMORY:"

    cv2.putText(full_grid, cpu_graph_label, (graph2_x - 240, graph2_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    draw_usage_graph(full_grid, mem_usage_history, (graph2_x, graph2_y), (graph_width, graph_height), (0, 128, 255))
    final_full_grid = add_logo(full_grid)

    return final_full_grid

def main():
    with open("ip_list.txt") as f:
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
            grid = layout_frames(frames, borders, labels)
        cv2.imshow("SilverFlag Stream Viewer", grid)
        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_on_click(test_output)
    main()
