import cv2
import numpy as np
import urllib.request
import time
import threading
import logging
import random
from PIL import Image
import io

# Global storage for camera data
camera_frames = {}
camera_metadata = {}
camera_borders = {}
frame_lock = threading.Lock()

def should_poll_jpeg(url):
    """Determine if URL should be polled as JPEG."""
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

def add_custom_params(url):
    """Add custom parameters to URL if needed."""
    # Add any custom parameters for camera access
    return url

def get_camera_frame(camera_id):
    """Get the latest frame for a camera."""
    with frame_lock:
        return camera_frames.get(camera_id, None)

def get_camera_metadata(camera_id):
    """Get metadata for a camera."""
    with frame_lock:
        return camera_metadata.get(camera_id, {})

def get_all_camera_frames():
    """Get all current camera frames."""
    with frame_lock:
        return camera_frames.copy()

def get_camera_border_color(camera_id):
    """Get the border color for a camera."""
    with frame_lock:
        return camera_borders.get(camera_id, (255, 255, 255))

def capture_single_frame(camera_url, timeout=5):
    """Capture a single frame from a camera for preview purposes."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "close"
        }
        
        full_url = add_custom_params(camera_url)
        req = urllib.request.Request(full_url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            img_data = resp.read(2 * 1024 * 1024)  # 2MB limit for preview
            
            if not img_data:
                return None
                
            img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if frame is not None and frame.size > 0:
                # Resize for preview if too large
                if frame.shape[0] > 480 or frame.shape[1] > 640:
                    scale = min(640 / frame.shape[1], 480 / frame.shape[0])
                    new_width = int(frame.shape[1] * scale)
                    new_height = int(frame.shape[0] * scale)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                return frame
    except Exception as e:
        logging.error(f"Error capturing frame from {camera_url}: {e}")
        return None

def frame_to_pil_image(frame):
    """Convert OpenCV frame to PIL Image."""
    if frame is None:
        return None
    try:
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_frame)
    except Exception as e:
        logging.error(f"Error converting frame to PIL: {e}")
        return None

def read_stream(input_id, frames, borders, lock):
    """Main camera stream reading function."""
    try:
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
                    
                    req = urllib.request.Request(full_url, headers=headers)
                    
                    with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                        img_data = resp.read(5 * 1024 * 1024)  # 5MB limit
                        
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
                                
                                # Resize larger frames
                                if frame.shape[0] > 1080 or frame.shape[1] > 1920:
                                    if frame.shape[1] > frame.shape[0]:  # Landscape
                                        scale = min(1.0, 1920 / frame.shape[1])
                                    else:  # Portrait
                                        scale = min(1.0, 1080 / frame.shape[0])
                                        
                                    new_width = int(frame.shape[1] * scale)
                                    new_height = int(frame.shape[0] * scale)
                                    frame = cv2.resize(frame, (new_width, new_height), 
                                                      interpolation=cv2.INTER_AREA)
                                
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
                                    if time_diff >= 5:
                                        camera_metadata[input_id]["fps"] = round(frames_count / time_diff, 1)
                                        frames_count = 0
                                        last_fps_time = now
                                
                                # Adaptive sleep
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

def start_camera_stream(camera_id):
    """Start streaming from a camera in a separate thread."""
    thread = threading.Thread(
        target=read_stream, 
        args=(camera_id, camera_frames, camera_borders, frame_lock),
        daemon=True
    )
    thread.start()
    return thread