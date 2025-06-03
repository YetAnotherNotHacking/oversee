import cv2
import threading
import time
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from backend.cameradown import read_stream, camera_frames, camera_metadata, frame_lock, capture_single_frame, default_stream_params

class FocusedStreamWindow:
    def __init__(self, ip):
        self.ip = ip
        self.stream_active = True
        
        # Create Tkinter window
        self.window = tk.Toplevel()
        self.window.title(f"Camera Stream: {ip}")
        self.window.geometry("800x600")
        self.window.minsize(400, 300)
        
        # Configure grid weights for resizing
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        
        # Create main frame
        main_frame = ttk.Frame(self.window)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Create image label
        self.image_label = ttk.Label(main_frame)
        self.image_label.grid(row=0, column=0, sticky="nsew")
        
        # Create status label
        self.status_label = ttk.Label(main_frame, text="Initializing...")
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        # Format the camera URL properly with appropriate endpoint and parameters
        if not ip.startswith(('http://', 'rtsp://')):
            # Extract endpoint from IP if it exists
            if '/' in ip:
                base_ip, endpoint = ip.split('/', 1)
                self.camera_url = f"http://{base_ip}/{endpoint}"
            else:
                self.camera_url = f"http://{ip}/video"
            
            # Add parameters based on endpoint
            for endpoint, params in default_stream_params.items():
                if endpoint.lower() in self.camera_url.lower():
                    if '?' not in self.camera_url:
                        self.camera_url = f"{self.camera_url}{params}"
                    break
        else:
            self.camera_url = ip
        
        print(f"Starting focused stream for: {self.camera_url}")
        
        # Bind window close event
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start stream thread
        self.stream_thread = threading.Thread(target=self.stream_worker, daemon=True)
        self.stream_thread.start()
        
        # Start window resize handler
        self.window.bind('<Configure>', self.on_window_resize)
        
        # Store current window size
        self.window_width = 800
        self.window_height = 600
    
    def on_window_resize(self, event):
        """Handle window resize events"""
        if event.widget == self.window:
            self.window_width = event.width - 20  # Account for padding
            self.window_height = event.height - 60  # Account for padding and status label
    
    def on_closing(self):
        """Handle window closing"""
        self.stream_active = False
        self.window.destroy()
    
    def stream_worker(self):
        """Worker thread for camera stream"""
        try:
            # Try to capture a single frame first to test connection
            test_frame = capture_single_frame(self.camera_url)
            if test_frame is None:
                print(f"Failed to capture test frame from {self.camera_url}")
                self.status_label.config(text="Camera not responding")
                return
            
            # Start the camera stream
            stream_thread = threading.Thread(
                target=read_stream,
                args=(self.camera_url, camera_frames, {}, frame_lock),
                daemon=True
            )
            stream_thread.start()
            
            # Wait a bit for initial connection
            time.sleep(1)
            
            while self.stream_active:
                try:
                    with frame_lock:
                        frame = camera_frames.get(self.camera_url)
                        if frame is not None:
                            # Get metadata
                            metadata = camera_metadata.get(self.camera_url, {})
                            resolution = metadata.get('resolution', 'Unknown')
                            
                            # Calculate aspect ratio preserving resize
                            h, w = frame.shape[:2]
                            aspect = w / h
                            
                            # Calculate new dimensions
                            if self.window_width / self.window_height > aspect:
                                new_height = self.window_height
                                new_width = int(new_height * aspect)
                            else:
                                new_width = self.window_width
                                new_height = int(new_width / aspect)
                            
                            # Resize frame
                            frame = cv2.resize(frame, (new_width, new_height))
                            
                            # Convert to RGB and then to PhotoImage
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            photo = ImageTk.PhotoImage(img)
                            
                            # Update image in main thread
                            self.window.after(0, lambda p=photo: self.update_image(p))
                            
                            # Update status
                            self.window.after(0, lambda r=resolution: self.status_label.config(
                                text=f"Resolution: {r}"
                            ))
                    
                    time.sleep(0.03)  # Limit frame rate
                
                except Exception as e:
                    print(f"Error in stream loop: {str(e)}")
                    self.window.after(0, lambda: self.status_label.config(
                        text=f"Stream error: {str(e)}"
                    ))
                    time.sleep(1)
        
        except Exception as e:
            print(f"Fatal error in stream: {str(e)}")
            self.window.after(0, lambda: self.status_label.config(
                text=f"Fatal error: {str(e)}"
            ))
    
    def update_image(self, photo):
        """Update the image in the main thread"""
        if self.stream_active:
            self.image_label.config(image=photo)
            self.image_label.image = photo  # Keep a reference 
    
    def open_ipinfo(self):
        """Open the camera's IP in IPINFO"""
        import webbrowser
        
        # Extract base IP without port or endpoint
        base_ip = self.ip.split('/')[0] if '/' in self.ip else self.ip
        base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
        
        # Open in browser
        webbrowser.open(f"https://ipinfo.io/{base_ip}") 