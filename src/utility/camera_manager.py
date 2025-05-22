import threading
import time
import logging
from utility.ip2loc import get_geolocation
from backend.cameradown import start_camera_stream, get_camera_frame, get_camera_metadata, capture_single_frame

class Camera:
    def __init__(self, camera_id, url, name=None, location=None):
        self.id = camera_id
        self.url = url
        self.name = name or f"Camera {camera_id}"
        self.location = location
        self.ip_address = self.extract_ip_from_url(url)
        self.geolocation = get_geolocation(self.ip_address) if self.ip_address else "Unknown"
        self.stream_thread = None
        self.is_streaming = False
        self.preview_frame = None
        self.last_preview_capture = 0
        
    def extract_ip_from_url(self, url):
        """Extract IP address from camera URL."""
        try:
            if "://" in url:
                # Remove protocol
                url = url.split("://")[1]
            
            # Remove path
            if "/" in url:
                url = url.split("/")[0]
            
            # Remove port
            if ":" in url:
                url = url.split(":")[0]
            
            return url
        except:
            return None
    
    def start_streaming(self):
        """Start streaming from this camera."""
        if not self.is_streaming:
            self.stream_thread = start_camera_stream(self.url)
            self.is_streaming = True
            logging.info(f"Started streaming from {self.name} ({self.url})")
    
    def stop_streaming(self):
        """Stop streaming from this camera."""
        self.is_streaming = False
        logging.info(f"Stopped streaming from {self.name}")
    
    def get_current_frame(self):
        """Get the current frame from the camera stream."""
        return get_camera_frame(self.url)
    
    def get_metadata(self):
        """Get camera metadata."""
        return get_camera_metadata(self.url)
    
    def get_preview_frame(self, force_refresh=False):
        """Get a preview frame (cached for performance)."""
        current_time = time.time()
        
        # Refresh preview every 30 seconds or if forced
        if (force_refresh or 
            self.preview_frame is None or 
            current_time - self.last_preview_capture > 30):
            
            self.preview_frame = capture_single_frame(self.url)
            self.last_preview_capture = current_time
        
        return self.preview_frame

class CameraManager:
    def __init__(self):
        self.cameras = {}
        self.active_streams = set()
        self.lock = threading.Lock()
        
    def add_camera(self, camera_id, url, name=None, location=None):
        """Add a new camera to the manager."""
        with self.lock:
            camera = Camera(camera_id, url, name, location)
            self.cameras[camera_id] = camera
            logging.info(f"Added camera: {camera.name} at {url}")
            return camera
    
    def remove_camera(self, camera_id):
        """Remove a camera from the manager."""
        with self.lock:
            if camera_id in self.cameras:
                camera = self.cameras[camera_id]
                camera.stop_streaming()
                del self.cameras[camera_id]
                self.active_streams.discard(camera_id)
                logging.info(f"Removed camera: {camera.name}")
    
    def start_camera_stream(self, camera_id):
        """Start streaming from a specific camera."""
        with self.lock:
            if camera_id in self.cameras:
                camera = self.cameras[camera_id]
                camera.start_streaming()
                self.active_streams.add(camera_id)
                return True
        return False
    
    def stop_camera_stream(self, camera_id):
        """Stop streaming from a specific camera."""
        with self.lock:
            if camera_id in self.cameras:
                camera = self.cameras[camera_id]
                camera.stop_streaming()
                self.active_streams.discard(camera_id)
                return True
        return False
    
    def get_camera(self, camera_id):
        """Get a camera object by ID."""
        return self.cameras.get(camera_id)
    
    def get_all_cameras(self):
        """Get all cameras."""
        with self.lock:
            return list(self.cameras.values())
    
    def get_cameras_by_location(self):
        """Get cameras grouped by location."""
        location_groups = {}
        
        with self.lock:
            for camera in self.cameras.values():
                location = camera.location or camera.geolocation or "Unknown"
                if location not in location_groups:
                    location_groups[location] = []
                location_groups[location].append(camera)
        
        return location_groups
    
    def get_active_cameras(self):
        """Get list of cameras that are currently streaming."""
        with self.lock:
            return [self.cameras[cam_id] for cam_id in self.active_streams 
                   if cam_id in self.cameras]
    
    def load_cameras_from_file(self, filename):
        """Load cameras from a text file (one URL per line)."""
        try:
            with open(filename, 'r') as f:
                for i, line in enumerate(f):
                    url = line.strip()
                    if url and not url.startswith('#'):
                        # Generate camera ID and name
                        camera_id = f"cam_{i+1}"
                        name = f"Camera {i+1}"
                        
                        # Try to determine location from IP
                        self.add_camera(camera_id, url, name)
            
            logging.info(f"Loaded {len(self.cameras)} cameras from {filename}")
            
        except Exception as e:
            logging.error(f"Error loading cameras from file: {e}")
    
    def start_all_streams(self):
        """Start streaming from all cameras."""
        for camera_id in self.cameras:
            self.start_camera_stream(camera_id)
    
    def stop_all_streams(self):
        """Stop all camera streams."""
        for camera_id in list(self.active_streams):
            self.stop_camera_stream(camera_id)
    
    def get_camera_stats(self):
        """Get statistics about cameras."""
        with self.lock:
            total_cameras = len(self.cameras)
            active_streams = len(self.active_streams)
            locations = len(set(camera.geolocation for camera in self.cameras.values()))
            
            return {
                'total_cameras': total_cameras,
                'active_streams': active_streams,
                'locations': locations
            }