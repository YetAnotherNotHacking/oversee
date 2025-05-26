import requests
import time
import random
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple

class CameraMovement:
    """Class to handle camera movement controls for different camera types"""
    
    # Camera brand/model patterns
    CAMERA_PATTERNS = {
        'canon_vb': {
            'brand': 'Canon',
            'model': 'VB Series',
            'patterns': ['/-wvhttp-01-/GetOneShot'],
            'endpoints': ['/-wvhttp-01-/GetOneShot', '/-wvhttp-01-/claim.cgi', '/-wvhttp-01-/control.cgi'],
            'movement': {
                'pan': True,
                'tilt': True,
                'zoom': True,
                'presets': False,
                'scan': False
            }
        },
        'panasonic': {
            'brand': 'Panasonic',
            'model': 'BL-C Series',
            'patterns': ['/SnapshotJPEG'],
            'endpoints': ['/SnapshotJPEG', '/nphControlCamera'],
            'movement': {
                'pan': True,
                'tilt': True,
                'zoom': True,
                'presets': True,
                'scan': True
            }
        },
        'mobotic': {
            'brand': 'Mobotic',
            'model': 'M12',
            'patterns': ['/control/userimage.html'],
            'endpoints': ['/control/userimage.html', '/control/click.cgi'],
            'movement': {
                'pan': False,
                'tilt': False,
                'zoom': True,
                'presets': False,
                'scan': False
            }
        },
        'axis': {
            'brand': 'Axis',
            'model': 'Generic',
            'patterns': ['/video.mjpg'],
            'endpoints': ['/video.mjpg', '/axis-cgi/com/ptz.cgi'],
            'movement': {
                'pan': True,
                'tilt': True,
                'zoom': True,
                'presets': True,
                'scan': True
            }
        },
        'bosch': {
            'brand': 'Bosch',
            'model': 'Generic',
            'patterns': ['/snap.jpg'],
            'endpoints': ['/snap.jpg', '/ptz.cgi'],
            'movement': {
                'pan': True,
                'tilt': True,
                'zoom': True,
                'presets': True,
                'scan': True
            }
        },
        'stardot': {
            'brand': 'StarDot',
            'model': 'Generic',
            'patterns': ['/nph-jpeg.cgi'],
            'endpoints': ['/nph-jpeg.cgi', '/cgi-bin/ptz.cgi'],
            'movement': {
                'pan': True,
                'tilt': True,
                'zoom': True,
                'presets': True,
                'scan': True
            }
        }
    }
    
    def __init__(self, base_url: str):
        """
        Initialize camera movement controller
        
        Args:
            base_url: Base URL of the camera (e.g. http://192.168.1.100:8080)
        """
        self.base_url = base_url.rstrip('/')
        self.camera_info = self._detect_camera()
        self.session_id = None
        self.claim_token = None
        
    def _detect_camera(self) -> Dict[str, Any]:
        """Detect camera type, brand, model and capabilities"""
        url_lower = self.base_url.lower()
        
        # Try to detect camera type
        for camera_type, info in self.CAMERA_PATTERNS.items():
            for pattern in info['patterns']:
                if pattern.lower() in url_lower:
                    return {
                        'type': camera_type,
                        'brand': info['brand'],
                        'model': info['model'],
                        'endpoints': info['endpoints'],
                        'movement': info['movement'],
                        'movement_supported': True
                    }
        
        # If no specific type detected, try to detect generic movement support
        try:
            # Try common PTZ endpoints
            test_endpoints = [
                '/ptz.cgi',
                '/axis-cgi/com/ptz.cgi',
                '/cgi-bin/ptz.cgi',
                '/nphControlCamera'
            ]
            
            for endpoint in test_endpoints:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=2)
                    if response.status_code == 200:
                        return {
                            'type': 'generic',
                            'brand': 'Unknown',
                            'model': 'Generic PTZ',
                            'endpoints': [endpoint],
                            'movement': {
                                'pan': True,
                                'tilt': True,
                                'zoom': True,
                                'presets': False,
                                'scan': False
                            },
                            'movement_supported': True
                        }
                except:
                    continue
        except:
            pass
            
        # Return unknown camera info
        return {
            'type': 'unknown',
            'brand': 'Unknown',
            'model': 'Unknown',
            'endpoints': [],
            'movement': {
                'pan': False,
                'tilt': False,
                'zoom': False,
                'presets': False,
                'scan': False
            },
            'movement_supported': False
        }
        
    def _get_session_id(self) -> Optional[str]:
        """Get a session ID for cameras that require it"""
        if self.camera_info['type'] == 'canon_vb':
            try:
                # Generate a random sequence number
                seq = random.random()
                
                # Make the claim request
                claim_url = f"{self.base_url}/-wvhttp-01-/claim.cgi?s=&seq={seq}"
                response = requests.get(claim_url, timeout=5)
                
                if response.status_code == 200:
                    # Extract session ID from response
                    # Format: s=822d-5165781b
                    for line in response.text.split('\n'):
                        if 's=' in line:
                            self.session_id = line.split('s=')[1].strip()
                            return self.session_id
            except Exception as e:
                print(f"Error getting session ID: {e}")
        return None
        
    def move(self, direction: str, speed: int = 1) -> bool:
        """
        Move the camera in the specified direction
        
        Args:
            direction: Direction to move ('up', 'down', 'left', 'right', 'zoom_in', 'zoom_out')
            speed: Movement speed (1-10)
            
        Returns:
            bool: True if movement was successful
        """
        if self.camera_info['type'] == 'unknown':
            return False
            
        try:
            if self.camera_info['type'] == 'canon_vb':
                return self._move_canon(direction, speed)
            elif self.camera_info['type'] == 'panasonic':
                return self._move_panasonic(direction, speed)
            elif self.camera_info['type'] == 'mobotic':
                return self._move_mobotic(direction, speed)
            else:
                return False
        except Exception as e:
            print(f"Error moving camera: {e}")
            return False
            
    def _move_canon(self, direction: str, speed: int) -> bool:
        """Move Canon VB camera"""
        if not self.session_id:
            self.session_id = self._get_session_id()
            if not self.session_id:
                return False
                
        # Map direction to control parameters
        control_map = {
            'up': ('tilt', 1000),
            'down': ('tilt', -9000),
            'left': ('pan', -17000),
            'right': ('pan', 17000),
            'zoom_in': ('zoom', 320),
            'zoom_out': ('zoom', 6040)
        }
        
        if direction not in control_map:
            return False
            
        param, value = control_map[direction]
        seq = random.random()
        
        try:
            url = f"{self.base_url}/-wvhttp-01-/control.cgi?s={self.session_id}&c.1.{param}={value}&seq={seq}"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Error moving Canon camera: {e}")
            return False
            
    def _move_panasonic(self, direction: str, speed: int) -> bool:
        """Move Panasonic camera"""
        # Map direction to control parameters
        control_map = {
            'up': 'TiltUp',
            'down': 'TiltDown',
            'left': 'PanLeft',
            'right': 'PanRight',
            'zoom_in': 'ZoomTele',
            'zoom_out': 'ZoomWide'
        }
        
        if direction not in control_map:
            return False
            
        try:
            url = f"{self.base_url}/nphControlCamera?Direction={control_map[direction]}&Resolution=640x480&Quality=Standard&Mode=MPEG-4&RPeriod=0&Size=STD&PresetOperation=Move&Language=11"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Error moving Panasonic camera: {e}")
            return False
            
    def _move_mobotic(self, direction: str, speed: int) -> bool:
        """Move Mobotic camera"""
        if direction not in ['zoom_in', 'zoom_out']:
            return False
            
        try:
            zoom_value = 250 if direction == 'zoom_in' else 200
            url = f"{self.base_url}/control/click.cgi?zoomrel={zoom_value}&dummy={int(time.time())}"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Error moving Mobotic camera: {e}")
            return False
            
    def get_camera_info(self) -> Dict[str, Any]:
        """Get detailed information about the camera"""
        return {
            'type': self.camera_info['type'],
            'brand': self.camera_info['brand'],
            'model': self.camera_info['model'],
            'base_url': self.base_url,
            'has_session': bool(self.session_id),
            'movement_supported': self.camera_info['movement_supported'],
            'endpoints': self.camera_info['endpoints'],
            'movement_capabilities': self.camera_info['movement']
        }
        
    def get_movement_table(self) -> List[Tuple[str, bool]]:
        """Get movement capabilities in a table format"""
        return [
            ('Pan Support', self.camera_info['movement']['pan']),
            ('Tilt Support', self.camera_info['movement']['tilt']),
            ('Zoom Support', self.camera_info['movement']['zoom']),
            ('Presets Support', self.camera_info['movement']['presets']),
            ('Scan Support', self.camera_info['movement']['scan'])
        ]