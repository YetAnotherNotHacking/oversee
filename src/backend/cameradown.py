import requests
import time
import random
import numpy as np
import cv2

def extract_ip_from_url(url):
    """Extract just the IP or hostname from a URL."""
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    parts = url.split('/')
    if parts:
        return parts[0].split(':')[0]
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
            if input_id.startswith("rtsp://"):
                camera_metadata[input_id]["stream_type"] = "RTSP"
            elif should_poll_jpeg(input_id):
                camera_metadata[input_id]["stream_type"] = "JPEG Poll"
            else:
                camera_metadata[input_id]["stream_type"] = "HTTP"
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
                    with lock:
                        camera_metadata[input_id]["connection_attempts"] += 1
                    camera_metadata[input_id]["connection_attempts"] += 1
                    req = urllib.request.Request(full_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                        img_data = resp.read(2 * 1024 * 1024) # PER STREAM BANDWIDTH CAP (PER POLL NOT PER SECOND!!!)
                        if not img_data:
                            consecutive_failures += 1
                            raise ValueError("Empty image data received")
                        img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if frame is not None and frame.size > 0:
                            if frame.shape[0] > 0 and frame.shape[1] > 0 and frame.shape[2] == 3:
                                consecutive_failures = 0
                                current_timeout = max(min_timeout, current_timeout * 0.9)
                                with lock:
                                    camera_metadata[input_id]["last_success"] = time.time()
                                if frame.shape[0] > 1080 or frame.shape[1] > 1920:
                                    if frame.shape[1] > frame.shape[0]:
                                        scale = min(1.0, 1920 / frame.shape[1])
                                    else:
                                        scale = min(1.0, 1080 / frame.shape[0])
                                    new_width = int(frame.shape[1] * scale)
                                    new_height = int(frame.shape[0] * scale)
                                    frame = cv2.resize(frame, (new_width, new_height), 
                                                      interpolation=cv2.INTER_AREA)
                                safe_frame = frame.copy()
                                with lock:
                                    frames[input_id] = safe_frame
                                    camera_metadata[input_id]["frames_received"] += 1
                                    camera_metadata[input_id]["last_frame_time"] = time.time()
                                    camera_metadata[input_id]["resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
                                    frames_count += 1
                                    now = time.time()
                                    time_diff = now - last_fps_time
                                    if time_diff >= 5:
                                        camera_metadata[input_id]["fps"] = round(frames_count / time_diff, 1)
                                        frames_count = 0
                                        last_fps_time = now
                                fps = camera_metadata[input_id]["fps"]
                                if fps > 0:
                                    target_fps = 5
                                    max_sleep_time = 0.5
                                    
                                    if fps > target_fps:
                                        sleep_time = min(max_sleep_time, 1.0 / target_fps - 1.0 / fps)
                                        if sleep_time > 0.01:
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
                    current_timeout = min(max_timeout, current_timeout * 1.2)
                    print(f"[{input_id}] JPEG poll error: {e}")
                    backoff_time = min(5.0, 0.1 * (2 ** min(consecutive_failures, 5)))
                    time.sleep(backoff_time)
                if consecutive_failures >= max_consecutive_failures:
                    print(f"[{input_id}] Too many consecutive failures, taking a break...")
                    time.sleep(5.0)
                    consecutive_failures = 0
                    
    except Exception as e:
        print(f"[{input_id}] Stream error: {e}")
        time.sleep(1.0)