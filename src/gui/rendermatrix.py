import cv2
import numpy as np
import math
import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from utility.iplist import get_ip_range
import settings

# Import the camera backend functions
try:
    from backend.cameradown import camera_frames, start_camera_stream, frame_lock
    CAMERA_BACKEND_AVAILABLE = True
except ImportError:
    print("Warning: Camera backend not available, matrix view will be empty")
    CAMERA_BACKEND_AVAILABLE = False
    camera_frames = {}
    frame_lock = None

class CameraStreamManager:
    """Manages camera streams in background threads to prevent UI blocking"""
    
    def __init__(self):
        self.active_streams = set()
        self.stream_status = {}  # Track status of each stream
        self.initialization_lock = threading.Lock()
        self.pending_streams = set()  # Streams that are being initialized
        self.failed_streams = set()  # Streams that have failed
        self.connection_timestamps = {}  # Track when connections started
        self.max_connection_time = 30  # Max seconds to wait for connection
        
    def get_all_camera_frames(self):
        """
        Get all camera frames from the camera backend (non-blocking).
        
        Returns:
            dict: Dictionary mapping camera_id to frame data
        """
        if not CAMERA_BACKEND_AVAILABLE:
            return {}
        
        try:
            if frame_lock is not None:
                # Use timeout to prevent blocking
                if frame_lock.acquire(timeout=0.1):
                    try:
                        return camera_frames.copy()
                    finally:
                        frame_lock.release()
                else:
                    print("Warning: Could not acquire frame lock, returning empty frames")
                    return {}
            else:
                return camera_frames.copy()
        except Exception as e:
            print(f"Error getting camera frames: {e}")
            return {}

    def _start_single_camera_stream_async(self, camera_url):
        """
        Start a single camera stream asynchronously without blocking.
        This runs in a separate thread and doesn't wait for frames.
        
        Args:
            camera_url: Full camera URL (e.g., "202.245.13.81:80/cgi-bin/camera")
        """
        if not CAMERA_BACKEND_AVAILABLE:
            return
            
        try:
            print(f"Starting async stream for: {camera_url}")
            
            # Mark as pending with timestamp
            with self.initialization_lock:
                self.pending_streams.add(camera_url)
                self.stream_status[camera_url] = 'connecting'
                self.connection_timestamps[camera_url] = time.time()
            
            # Start the camera stream (this creates its own thread)
            start_camera_stream(camera_url)
            
            # Mark as active immediately (the actual streaming happens in cameradown.py)
            with self.initialization_lock:
                self.active_streams.add(camera_url)
                self.pending_streams.discard(camera_url)
                self.stream_status[camera_url] = 'active'
            
            print(f"Stream thread started for: {camera_url}")
                
        except Exception as e:
            print(f"Failed to start stream thread for {camera_url}: {e}")
            with self.initialization_lock:
                self.pending_streams.discard(camera_url)
                self.failed_streams.add(camera_url)
                self.stream_status[camera_url] = 'failed'

    def _cleanup_timed_out_connections(self):
        """Remove connections that have been pending too long"""
        current_time = time.time()
        timed_out = []
        
        with self.initialization_lock:
            for camera_url in list(self.pending_streams):
                if camera_url in self.connection_timestamps:
                    elapsed = current_time - self.connection_timestamps[camera_url]
                    if elapsed > self.max_connection_time:
                        timed_out.append(camera_url)
            
            for camera_url in timed_out:
                print(f"Connection timeout for {camera_url}")
                self.pending_streams.discard(camera_url)
                self.failed_streams.add(camera_url)
                self.stream_status[camera_url] = 'failed'
                self.connection_timestamps.pop(camera_url, None)

    def ensure_camera_streams_started(self, camera_urls):
        """
        Ensure camera streams are started for the given camera URLs (completely non-blocking).
        
        Args:
            camera_urls: List of camera URLs to start streams for
        """
        if not CAMERA_BACKEND_AVAILABLE:
            return
        
        # Clean up timed out connections first
        self._cleanup_timed_out_connections()
        
        # Start streams for any URLs that aren't already active, pending, or failed
        for camera_url in camera_urls:
            with self.initialization_lock:
                if (camera_url not in self.active_streams and 
                    camera_url not in self.pending_streams and 
                    camera_url not in self.failed_streams):
                    # Start each camera stream in its own thread immediately
                    thread = threading.Thread(
                        target=self._start_single_camera_stream_async,
                        args=(camera_url,),
                        name=f"CameraInit-{camera_url}",
                        daemon=True
                    )
                    thread.start()

    def get_connecting_or_active_cameras(self, camera_urls):
        """
        Get list of cameras that are either connecting or have frames.
        Excludes failed cameras.
        
        Args:
            camera_urls: List of all camera URLs
            
        Returns:
            list: Filtered list of camera URLs that should be displayed
        """
        frames = self.get_all_camera_frames()
        display_cameras = []
        
        with self.initialization_lock:
            for camera_url in camera_urls:
                # Include if: has frames, is connecting, or is active but no frames yet
                if (camera_url in frames and frames[camera_url] is not None) or \
                   (camera_url in self.pending_streams) or \
                   (camera_url in self.active_streams and camera_url not in self.failed_streams):
                    display_cameras.append(camera_url)
        
        return display_cameras

    def get_camera_border_color(self, camera_id):
        """
        Get border color for a camera based on its status.
        
        Args:
            camera_id: String identifier for the camera
            
        Returns:
            tuple: BGR color tuple for the border
        """
        colors = {
            'active': (0, 255, 0),      # Green - receiving frames
            'connecting': (0, 255, 255), # Yellow - connecting
            'failed': (0, 0, 255),      # Red - failed
            'no_frames': (255, 0, 0),   # Blue - stream active but no frames yet
            'default': (128, 128, 128)  # Gray - unknown
        }
        
        # Check current status
        with self.initialization_lock:
            if camera_id in self.pending_streams:
                return colors['connecting']
            
            status = self.stream_status.get(camera_id, 'default')
            
            # Check if we have recent frames
            frames = self.get_all_camera_frames()
            if camera_id in frames and frames[camera_id] is not None:
                return colors['active']
            elif camera_id in self.active_streams:
                return colors['no_frames']  # Stream started but no frames yet
            elif status == 'failed':
                return colors['failed']
            else:
                return colors['default']

    def get_stream_stats(self):
        """Get statistics about stream status"""
        with self.initialization_lock:
            stats = {
                'active_streams': len(self.active_streams),
                'pending_streams': len(self.pending_streams),
                'failed_streams': len(self.failed_streams),
                'total_attempted': len(self.stream_status)
            }
        
        # Count cameras with actual frames
        frames = self.get_all_camera_frames()
        stats['cameras_with_frames'] = len([f for f in frames.values() if f is not None])
        
        return stats

# Global camera manager instance
camera_manager = CameraStreamManager()

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

def create_matrix_view(ip_range_start=1, ip_range_end=50, max_cell_width=320, max_cell_height=240, max_display_cameras=2000):
    """
    Create a matrix view of camera streams from the IP list.
    This function is completely non-blocking and returns immediately.
    Only shows cameras that are connecting or have frames (excludes failed cameras).
    
    Args:
        ip_range_start: Starting index in IP list (1-based)
        ip_range_end: Ending index in IP list (1-based)
        max_cell_width: Maximum width of each camera cell in pixels
        max_cell_height: Maximum height of each camera cell in pixels
        max_display_cameras: Maximum number of cameras to display at once
    
    Returns:
        numpy.ndarray: Combined matrix image
    """
    try:
        # Get camera URLs from the range
        all_camera_urls = get_ip_range(settings.ip_list_file, ip_range_start, min(ip_range_end, ip_range_start + max_display_cameras - 1))
        
        if not all_camera_urls:
            return _create_placeholder_matrix(max_cell_width, max_cell_height, "No camera URLs found")
        
        # Start camera streams in background (completely non-blocking)
        camera_manager.ensure_camera_streams_started(all_camera_urls)
        
        # Get only cameras that are connecting or active (exclude failed ones)
        display_cameras = camera_manager.get_connecting_or_active_cameras(all_camera_urls)
        
        # If no cameras are connecting or active yet, show connection status
        if not display_cameras:
            stats = camera_manager.get_stream_stats()
            message = f"Initializing {len(all_camera_urls)} cameras...\n"
            message += f"Failed: {stats['failed_streams']}, "
            message += f"Total attempted: {stats['total_attempted']}"
            return _create_placeholder_matrix(max_cell_width, max_cell_height, message)
        
        # Get all current camera frames (non-blocking)
        all_frames = camera_manager.get_all_camera_frames()
        
        # Filter frames for cameras we're displaying
        active_frames = {}
        for camera_url in display_cameras:
            if camera_url in all_frames and all_frames[camera_url] is not None:
                active_frames[camera_url] = all_frames[camera_url]
        
        # Calculate optimal cell size based on number of cameras
        num_display_cameras = len(display_cameras)
        cols, rows = calculate_optimal_grid_size(num_display_cameras)
        
        # Adjust cell size based on grid size to keep reasonable display size
        if num_display_cameras > 100:
            # Scale down cell size for large grids
            scale_factor = max(0.3, 100.0 / num_display_cameras)
            cell_width = max(80, int(max_cell_width * scale_factor))
            cell_height = max(60, int(max_cell_height * scale_factor))
        else:
            cell_width = max_cell_width
            cell_height = max_cell_height
        
        return _create_matrix_from_frames(active_frames, display_cameras, cell_width, cell_height, cols, rows)
        
    except Exception as e:
        print(f"Error in create_matrix_view: {e}")
        return _create_placeholder_matrix(max_cell_width, max_cell_height, f"Error: {str(e)}")

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
    global camera_manager
    with camera_manager.initialization_lock:
        camera_manager.active_streams.clear()
        camera_manager.pending_streams.clear()
        camera_manager.failed_streams.clear()
        camera_manager.stream_status.clear()
        camera_manager.connection_timestamps.clear()
    print("Camera manager cleaned up")