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
            
            # Mark as pending
            with self.initialization_lock:
                self.pending_streams.add(camera_url)
                self.stream_status[camera_url] = 'connecting'
            
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
                self.stream_status[camera_url] = 'failed'

    def ensure_camera_streams_started(self, camera_urls):
        """
        Ensure camera streams are started for the given camera URLs (completely non-blocking).
        
        Args:
            camera_urls: List of camera URLs to start streams for
        """
        if not CAMERA_BACKEND_AVAILABLE:
            return
        
        # Start streams for any URLs that aren't already active or pending
        for camera_url in camera_urls:
            with self.initialization_lock:
                if camera_url not in self.active_streams and camera_url not in self.pending_streams:
                    # Start each camera stream in its own thread immediately
                    thread = threading.Thread(
                        target=self._start_single_camera_stream_async,
                        args=(camera_url,),
                        name=f"CameraInit-{camera_url}",
                        daemon=True
                    )
                    thread.start()

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
                'failed_streams': len([s for s in self.stream_status.values() if s == 'failed']),
                'total_attempted': len(self.stream_status)
            }
        
        # Count cameras with actual frames
        frames = self.get_all_camera_frames()
        stats['cameras_with_frames'] = len([f for f in frames.values() if f is not None])
        
        return stats

# Global camera manager instance
camera_manager = CameraStreamManager()

def create_matrix_view(ip_range_start=1, ip_range_end=50, cell_width=320, cell_height=240):
    """
    Create a matrix view of camera streams from the IP list.
    This function is completely non-blocking and returns immediately.
    
    Args:
        ip_range_start: Starting index in IP list (1-based)
        ip_range_end: Ending index in IP list (1-based)
        cell_width: Width of each camera cell in pixels
        cell_height: Height of each camera cell in pixels
    
    Returns:
        numpy.ndarray: Combined matrix image
    """
    try:
        # Get camera URLs from the range
        camera_urls = get_ip_range(settings.ip_list_file, ip_range_start, ip_range_end)
        
        if not camera_urls:
            return _create_placeholder_matrix(cell_width, cell_height, "No camera URLs found")
        
        # Start camera streams in background (completely non-blocking)
        camera_manager.ensure_camera_streams_started(camera_urls)
        
        # Get all current camera frames (non-blocking)
        all_frames = camera_manager.get_all_camera_frames()
        
        # Filter frames that match our camera URLs
        active_frames = {}
        for camera_url in camera_urls:
            if camera_url in all_frames and all_frames[camera_url] is not None:
                active_frames[camera_url] = all_frames[camera_url]
        
        # Always return a matrix, even if no frames are ready yet
        if not active_frames:
            stats = camera_manager.get_stream_stats()
            message = f"Connecting to {len(camera_urls)} cameras...\n"
            message += f"Active: {stats['active_streams']}, "
            message += f"Pending: {stats['pending_streams']}, "
            message += f"With frames: {stats['cameras_with_frames']}"
            return _create_placeholder_matrix(cell_width, cell_height, message)
        
        return _create_matrix_from_frames(active_frames, camera_urls, cell_width, cell_height)
        
    except Exception as e:
        print(f"Error in create_matrix_view: {e}")
        return _create_placeholder_matrix(cell_width, cell_height, f"Error: {str(e)}")

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
    
    line_height = 30
    start_y = cell_height // 2 - (len(processed_lines) * line_height) // 2
    
    for i, line in enumerate(processed_lines):
        text_size = cv2.getTextSize(line, font, font_scale, text_thickness)[0]
        text_x = (cell_width - text_size[0]) // 2
        text_y = start_y + i * line_height
        
        cv2.putText(matrix_image, line, (text_x, text_y), 
                   font, font_scale, text_color, text_thickness)
    
    return matrix_image

def _create_matrix_from_frames(active_frames, all_camera_urls, cell_width, cell_height):
    """Create matrix image from active camera frames, showing placeholders for pending cameras"""
    # Use all camera URLs to determine grid size, not just active ones
    num_cameras = len(all_camera_urls)
    
    # Calculate grid dimensions
    if num_cameras == 1:
        cols, rows = 1, 1
    elif num_cameras <= 4:
        cols = 2
        rows = math.ceil(num_cameras / 2)
    elif num_cameras <= 9:
        cols = 3
        rows = math.ceil(num_cameras / 3)
    elif num_cameras <= 16:
        cols = 4
        rows = math.ceil(num_cameras / 4)
    else:
        # For larger numbers, try to keep it roughly square
        cols = math.ceil(math.sqrt(num_cameras))
        rows = math.ceil(num_cameras / cols)
    
    # Create the matrix canvas
    matrix_width = cols * cell_width
    matrix_height = rows * cell_height
    matrix_image = np.zeros((matrix_height, matrix_width, 3), dtype=np.uint8)
    
    # Fill the matrix with camera frames or placeholders
    for i, camera_url in enumerate(all_camera_urls):
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
                font_scale = 0.6
                text_color = (128, 128, 128)
                text_thickness = 1
                
                text = "Connecting..."
                text_size = cv2.getTextSize(text, font, font_scale, text_thickness)[0]
                text_x = (cell_width - text_size[0]) // 2
                text_y = (cell_height + text_size[1]) // 2
                
                cv2.putText(resized_frame, text, (text_x, text_y), 
                           font, font_scale, text_color, text_thickness)
            
            # Get border color for this camera
            border_color = camera_manager.get_camera_border_color(camera_url)
            
            # Add border (2 pixels)
            border_thickness = 2
            cv2.rectangle(resized_frame, (0, 0), (cell_width-1, cell_height-1), 
                         border_color, border_thickness)
            
            # Add camera URL text (simplified display)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.4
            text_color = (255, 255, 255)
            text_thickness = 1
            
            # Extract IP part for display
            display_name = camera_url.split('/')[0] if '/' in camera_url else camera_url
            if len(display_name) > 20:
                display_name = display_name[:17] + "..."
            
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
            cv2.putText(error_frame, "ERROR", (cell_width//2-30, cell_height//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            matrix_image[start_y:end_y, start_x:end_x] = error_frame
    
    return matrix_image

def cleanup_camera_manager():
    pass 