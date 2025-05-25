import cv2
import numpy as np
import math
import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from utility.iplist import get_ip_range
import settings
from datetime import datetime
import sqlite3
import os
import urllib.request
import urllib.parse
from backend.cameradown import capture_single_frame, default_stream_params

# Import the camera backend functions
try:
    from backend.cameradown import camera_frames, start_camera_stream, frame_lock
    CAMERA_BACKEND_AVAILABLE = True
except ImportError:
    print("Warning: Camera backend not available, matrix view will be empty")
    CAMERA_BACKEND_AVAILABLE = False
    camera_frames = {}
    frame_lock = None

class CameraManager:
    def __init__(self):
        self.frames = {}
        self.borders = {}
        self.labels = {}
        self.lock = threading.Lock()
        self.active = False
        self.threads = {}
        self.executor = ThreadPoolExecutor(max_workers=200)  # Increased from 20 to 200
        self.last_update = 0
        self.update_interval = 2.0  # Update every 2 seconds
        self.db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cameras.db')
        self.camera_metadata = {}
        self.camera_urls = []
        self.url_lock = threading.Lock()
        self.connection_semaphore = threading.Semaphore(200)  # Increased from 20 to 200
        self.frame_lock = threading.Lock()
        self.last_matrix_update = 0
        self.matrix_update_interval = 0.1  # Update matrix every 100ms
        
        # Initialize database
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for camera status tracking"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Create initial connection to set up database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create cameras table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cameras (
                ip TEXT PRIMARY KEY,
                status TEXT,
                last_check TIMESTAMP,
                resolution TEXT,
                stream_type TEXT,
                endpoint TEXT,
                location TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_thread_db_connection(self):
        """Create a new database connection for the current thread"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def update_camera_status(self, ip, status, resolution=None, stream_type=None, endpoint=None, location=None):
        """Update camera status in database"""
        try:
            # Create a new connection for this thread
            conn = self.get_thread_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO cameras 
                (ip, status, last_check, resolution, stream_type, endpoint, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ip, status, datetime.now(), resolution, stream_type, endpoint, location))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating camera status in database: {e}")
    
    def get_online_cameras(self):
        """Get list of online cameras from database"""
        try:
            conn = self.get_thread_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT ip, status FROM cameras WHERE status = "Online"')
            cameras = cursor.fetchall()
            conn.close()
            return cameras
        except Exception as e:
            print(f"Error getting online cameras: {e}")
            return []
    
    def should_poll_jpeg(self, url):
        """Check if URL should be polled as JPEG stream"""
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
    
    def add_custom_params(self, url):
        """Add appropriate parameters to camera URL"""
        for endpoint, params in default_stream_params.items():
            if endpoint.lower() in url.lower():
                if '?' not in url:
                    return f"{url}{params}"
                break
        return url
    
    def load_camera_urls(self):
        """Load camera URLs from rawips.txt"""
        try:
            # Read from rawips.txt
            with open(settings.ip_list_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Format the URL properly
                        if not line.startswith(('http://', 'rtsp://')):
                            if '/' in line:
                                base_ip, endpoint = line.split('/', 1)
                                camera_url = f"http://{base_ip}/{endpoint}"
                            else:
                                camera_url = f"http://{line}/video"
                        else:
                            camera_url = line
                        self.camera_urls.append(camera_url)
            
            # Remove duplicates while preserving order
            self.camera_urls = list(dict.fromkeys(self.camera_urls))
            
            print(f"Loaded {len(self.camera_urls)} unique camera URLs")
            
        except Exception as e:
            print(f"Error loading camera URLs: {e}")
            self.camera_urls = []
    
    def read_stream(self, camera_url):
        """Read camera stream and update frames dictionary"""
        # Initialize metadata
        with self.lock:
            if camera_url not in self.camera_metadata:
                self.camera_metadata[camera_url] = {
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
        
        # Format URL properly
        full_url = self.add_custom_params(camera_url)
        
        # Stream handling parameters
        max_consecutive_failures = 3  # Reduced from 5 to 3
        consecutive_failures = 0
        min_timeout = 0.5  # Reduced from 1.0 to 0.5
        max_timeout = 2.0  # Reduced from 3.0 to 2.0
        current_timeout = min_timeout
        last_fps_time = time.time()
        frames_count = 0
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "close"
        }
        
        while self.active:
            try:
                # Acquire semaphore before attempting connection
                with self.connection_semaphore:
                    # Mark connection attempt
                    with self.lock:
                        self.camera_metadata[camera_url]["connection_attempts"] += 1
                    
                    if self.should_poll_jpeg(full_url):
                        # Handle JPEG polling
                        req = urllib.request.Request(full_url, headers=headers)
                        with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                            img_data = resp.read(2 * 1024 * 1024)  # Reduced from 5MB to 2MB
                            
                            if not img_data:
                                raise ValueError("Empty image data received")
                            
                            img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    else:
                        # Handle other stream types
                        frame = capture_single_frame(full_url)
                    
                    if frame is not None and frame.size > 0:
                        # Verify frame dimensions
                        if frame.shape[0] > 0 and frame.shape[1] > 0 and frame.shape[2] == 3:
                            # Reset failure counter on success
                            consecutive_failures = 0
                            current_timeout = max(min_timeout, current_timeout * 0.9)
                            
                            # Mark success
                            with self.lock:
                                self.camera_metadata[camera_url]["last_success"] = time.time()
                            
                            # Resize larger frames
                            if frame.shape[0] > 720 or frame.shape[1] > 1280:  # Reduced from 1080/1920
                                if frame.shape[1] > frame.shape[0]:  # Landscape
                                    scale = min(1.0, 1280 / frame.shape[1])
                                else:  # Portrait
                                    scale = min(1.0, 720 / frame.shape[0])
                                
                                new_width = int(frame.shape[1] * scale)
                                new_height = int(frame.shape[0] * scale)
                                frame = cv2.resize(frame, (new_width, new_height), 
                                                 interpolation=cv2.INTER_AREA)
                            
                            # Update frame
                            with self.frame_lock:
                                self.frames[camera_url] = frame.copy()
                                self.camera_metadata[camera_url]["frames_received"] += 1
                                self.camera_metadata[camera_url]["last_frame_time"] = time.time()
                                self.camera_metadata[camera_url]["resolution"] = f"{frame.shape[1]}x{frame.shape[0]}"
                                
                                # Calculate FPS
                                frames_count += 1
                                now = time.time()
                                time_diff = now - last_fps_time
                                if time_diff >= 5:  # Update FPS every 5 seconds
                                    self.camera_metadata[camera_url]["fps"] = round(frames_count / time_diff, 1)
                                    frames_count = 0
                                    last_fps_time = now
                            
                            # Adaptive sleep based on FPS
                            fps = self.camera_metadata[camera_url]["fps"]
                            if fps > 0:
                                target_fps = 2  # Reduced from 5 to 2
                                max_sleep_time = 0.2  # Reduced from 0.5 to 0.2
                                
                                if fps > target_fps:
                                    sleep_time = min(max_sleep_time, 1.0 / target_fps - 1.0 / fps)
                                    if sleep_time > 0.01:
                                        time.sleep(sleep_time)
                        else:
                            consecutive_failures += 1
                            print(f"[{camera_url}] Invalid frame dimensions: {frame.shape}")
                    else:
                        consecutive_failures += 1
                        print(f"[{camera_url}] Failed to decode image")
                        
            except Exception as e:
                consecutive_failures += 1
                with self.lock:
                    self.camera_metadata[camera_url]["connection_failures"] += 1
                
                # Increase timeout on failure
                current_timeout = min(max_timeout, current_timeout * 1.2)
                print(f"[{camera_url}] Stream error: {e}")
                
                # Progressive backoff
                backoff_time = min(2.0, 0.1 * (2 ** min(consecutive_failures, 3)))  # Reduced max backoff
                time.sleep(backoff_time)
    
    def start_camera(self, camera_url):
        """Start a camera stream if not already running"""
        if camera_url not in self.threads or not self.threads[camera_url]:
            # Use thread pool instead of creating new threads
            self.executor.submit(self.read_stream, camera_url)
            self.threads[camera_url] = True  # Just mark that we've started this camera
    
    def stop_all_cameras(self):
        """Stop all camera streams"""
        self.active = False
        self.executor.shutdown(wait=False)
        self.threads.clear()
        self.frames.clear()
        self.camera_metadata.clear()
    
    def create_matrix_view(self, width, height):
        """Create matrix view of all active cameras"""
        try:
            # Load camera URLs if not already loaded
            if not self.camera_urls:
                self.load_camera_urls()
            
            if not self.camera_urls:
                return self._create_error_matrix(width, height, "No camera URLs found")
            
            # Start camera streams for all URLs
            for camera_url in self.camera_urls:
                self.start_camera(camera_url)
            
            # Get all frames that are available
            with self.frame_lock:
                available_frames = {k: v for k, v in self.frames.items() if v is not None}
            
            if not available_frames:
                return self._create_error_matrix(width, height, "Waiting for camera feeds...")
            
            # Calculate grid dimensions based on number of available frames
            count = len(available_frames)
            
            # Calculate optimal grid dimensions
            # Try to make it as square as possible while fitting the width/height ratio
            aspect_ratio = width / height
            cols = int(np.ceil(np.sqrt(count * aspect_ratio)))
            rows = int(np.ceil(count / cols))
            
            # Calculate cell dimensions
            cell_w = width // cols
            cell_h = height // rows
            
            # Create a blank canvas
            matrix = np.zeros((height, width, 3), dtype=np.uint8)
            matrix[:] = (43, 43, 43)  # Dark gray background
            
            # Place frames in the grid
            frame_list = list(available_frames.items())
            for i, (camera_url, frame) in enumerate(frame_list):
                if i >= cols * rows:
                    break
                    
                # Calculate position
                row = i // cols
                col = i % cols
                
                try:
                    # Resize frame to fit cell
                    resized = cv2.resize(frame, (cell_w, cell_h))
                    
                    # Calculate position in matrix
                    y_start = row * cell_h
                    y_end = y_start + cell_h
                    x_start = col * cell_w
                    x_end = x_start + cell_w
                    
                    # Ensure we don't exceed matrix bounds
                    if y_end <= height and x_end <= width:
                        matrix[y_start:y_end, x_start:x_end] = resized
                    
                except Exception as e:
                    print(f"Error processing frame for {camera_url}: {e}")
                    continue
            
            return matrix
            
        except Exception as e:
            print(f"Matrix view error: {e}")
            return self._create_error_matrix(width, height, str(e))
    
    def _create_error_matrix(self, width, height, message):
        """Create an error matrix with a message"""
        matrix = np.zeros((height, width, 3), dtype=np.uint8)
        matrix[:] = (43, 43, 43)  # Dark gray background
        
        cv2.putText(matrix, message, (30, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return matrix

# Global camera manager instance
camera_manager = CameraManager()
camera_manager.active = True  # Set active flag immediately
camera_manager.load_camera_urls()  # Load URLs once at startup

def calculate_optimal_grid_size(num_cameras):
    """
    Calculate optimal grid dimensions for any number of cameras.
    Tries to create a roughly square grid that can accommodate all cameras.
    
    Args:
        num_cameras: Number of cameras to display
        
    Returns:
        tuple: (cols, rows) for the grid
    """
    if num_cameras == 0:
        return 1, 1
    elif num_cameras == 1:
        return 1, 1
    elif num_cameras <= 4:
        return 2, 2
    elif num_cameras <= 9:
        return 3, 3
    elif num_cameras <= 16:
        return 4, 4
    elif num_cameras <= 25:
        return 5, 5
    elif num_cameras <= 36:
        return 6, 6
    elif num_cameras <= 49:
        return 7, 7
    elif num_cameras <= 64:
        return 8, 8
    elif num_cameras <= 100:
        return 10, 10
    elif num_cameras <= 144:
        return 12, 12
    elif num_cameras <= 225:
        return 15, 15
    elif num_cameras <= 400:
        return 20, 20
    elif num_cameras <= 625:
        return 25, 25
    elif num_cameras <= 900:
        return 30, 30
    elif num_cameras <= 1225:
        return 35, 35
    elif num_cameras <= 1600:
        return 40, 40
    elif num_cameras <= 2025:
        return 45, 45
    elif num_cameras <= 2500:
        return 50, 50
    else:
        # For very large numbers, calculate dynamically
        cols = math.ceil(math.sqrt(num_cameras))
        rows = math.ceil(num_cameras / cols)
        return cols, rows

def create_matrix_view(width, height):
    """Create matrix view of camera streams"""
    try:
        return camera_manager.create_matrix_view(width, height)
    except Exception as e:
        print(f"Error in create_matrix_view: {e}")
        return camera_manager._create_error_matrix(width, height, str(e))

def _create_placeholder_matrix(cell_width, cell_height, message):
    """Create a placeholder matrix with a message"""
    matrix_image = np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
    
    # Add message text
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    text_color = (255, 255, 255)
    text_thickness = 2
    
    # Split message into lines if too long
    lines = message.split('\n')
    processed_lines = []
    
    for line in lines:
        words = line.split()
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            text_size = cv2.getTextSize(test_line, font, font_scale, text_thickness)[0]
            
            if text_size[0] < cell_width - 20:
                current_line = test_line
            else:
                if current_line:
                    processed_lines.append(current_line)
                current_line = word
        
        if current_line:
            processed_lines.append(current_line)
    
    # Draw text lines
    line_height = 30
    start_y = cell_height // 2 - (len(processed_lines) * line_height) // 2
    
    for i, line in enumerate(processed_lines):
        text_size = cv2.getTextSize(line, font, font_scale, text_thickness)[0]
        text_x = (cell_width - text_size[0]) // 2
        text_y = start_y + i * line_height
        
        cv2.putText(matrix_image, line, (text_x, text_y), 
                   font, font_scale, text_color, text_thickness)
    
    return matrix_image

def _create_matrix_from_frames(active_frames, display_cameras, cell_width, cell_height, cols, rows):
    """Create matrix image from active camera frames, showing placeholders for pending cameras"""
    # Create the matrix canvas
    matrix_width = cols * cell_width
    matrix_height = rows * cell_height
    matrix_image = np.zeros((matrix_height, matrix_width, 3), dtype=np.uint8)
    
    # Fill the matrix with camera frames or placeholders
    for i, camera_url in enumerate(display_cameras):
        if i >= cols * rows:
            break
            
        # Calculate position in grid
        row = i // cols
        col = i % cols
        
        # Calculate pixel positions
        start_y = row * cell_height
        end_y = start_y + cell_height
        start_x = col * cell_width
        end_x = start_x + cell_width
        
        try:
            # Check if we have a frame for this camera
            if camera_url in active_frames:
                frame = active_frames[camera_url]
                # Resize frame to fit cell
                resized_frame = cv2.resize(frame, (cell_width, cell_height), 
                                         interpolation=cv2.INTER_AREA)
            else:
                # Create placeholder for cameras without frames yet
                resized_frame = np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
                # Add "Connecting..." text
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = min(0.6, cell_width / 400.0)  # Scale font with cell size
                text_color = (128, 128, 128)
                text_thickness = max(1, int(cell_width / 200))
                
                text = "Connecting..."
                text_size = cv2.getTextSize(text, font, font_scale, text_thickness)[0]
                text_x = (cell_width - text_size[0]) // 2
                text_y = (cell_height + text_size[1]) // 2
                
                cv2.putText(resized_frame, text, (text_x, text_y), 
                           font, font_scale, text_color, text_thickness)
            
            # Get border color for this camera
            border_color = camera_manager.get_camera_border_color(camera_url)
            
            # Add border (scale with cell size)
            border_thickness = max(1, cell_width // 160)
            cv2.rectangle(resized_frame, (0, 0), (cell_width-1, cell_height-1), 
                         border_color, border_thickness)
            
            # Add camera URL text (simplified display) - only for larger cells
            if cell_width > 100:
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = min(0.4, cell_width / 800.0)
                text_color = (255, 255, 255)
                text_thickness = max(1, int(cell_width / 320))
                
                # Extract IP part for display
                display_name = camera_url.split('/')[0] if '/' in camera_url else camera_url
                max_chars = max(10, cell_width // 16)
                if len(display_name) > max_chars:
                    display_name = display_name[:max_chars-3] + "..."
                
                text_size = cv2.getTextSize(display_name, font, font_scale, text_thickness)[0]
                text_x = 5
                text_y = cell_height - 10
                
                # Add text background
                cv2.rectangle(resized_frame, (text_x-2, text_y-text_size[1]-2), 
                             (text_x+text_size[0]+2, text_y+2), (0, 0, 0), -1)
                
                # Add text
                cv2.putText(resized_frame, display_name, (text_x, text_y), 
                           font, font_scale, text_color, text_thickness)
            
            # Place frame in matrix
            matrix_image[start_y:end_y, start_x:end_x] = resized_frame
            
        except Exception as e:
            print(f"Error processing frame for camera {camera_url}: {e}")
            # Fill with error placeholder
            error_frame = np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
            font_scale = min(0.7, cell_width / 400.0)
            cv2.putText(error_frame, "ERROR", (max(5, cell_width//2-30), cell_height//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), max(1, cell_width//160))
            matrix_image[start_y:end_y, start_x:end_x] = error_frame
    
    return matrix_image

def cleanup_camera_manager():
    """Clean up camera manager resources"""
    camera_manager.stop_all_cameras()