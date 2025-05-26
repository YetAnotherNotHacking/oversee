import tkinter as tk
from tkinter import ttk
from backend.cameraup import CameraMovement
import threading
import time

class MovementGUI:
    def __init__(self, parent, camera_url):
        # Create a new window
        self.window = tk.Toplevel(parent)
        self.window.title("Camera Movement Control")
        self.window.geometry("400x300")
        
        # Make it non-modal
        self.window.transient(parent)
        # Remove grab_set() to make it non-modal
        
        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.window.winfo_screenheight() // 2) - (300 // 2)
        self.window.geometry(f"400x300+{x}+{y}")
        
        # Initialize camera movement controller
        self.camera = CameraMovement(camera_url)
        
        # Create main frame
        self.main_frame = ttk.Frame(self.window, padding="5")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        
        # Create camera info section
        self.create_camera_info_section()
        
        # Create movement controls
        self.create_movement_controls()
        
        # Bind window close event
        self.window.protocol("WM_DELETE_WINDOW", self.cleanup)
        
    def create_camera_info_section(self):
        """Create camera information display section"""
        info_frame = ttk.LabelFrame(self.main_frame, text="Camera Information", padding="5")
        info_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)
        
        # Get camera info
        info = self.camera.get_camera_info()
        
        # Create info table
        info_table = ttk.Treeview(info_frame, columns=("Property", "Value"), show="headings", height=3)
        info_table.heading("Property", text="Property")
        info_table.heading("Value", text="Value")
        info_table.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Add camera info
        info_table.insert("", "end", values=("Brand", info['brand']))
        info_table.insert("", "end", values=("Model", info['model']))
        info_table.insert("", "end", values=("Movement", "Supported" if info['movement_supported'] else "Not Supported"))
        
        # Create movement capabilities table
        capabilities_frame = ttk.LabelFrame(self.main_frame, text="Movement Capabilities", padding="5")
        capabilities_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)
        
        capabilities_table = ttk.Treeview(capabilities_frame, columns=("Feature", "Supported"), show="headings", height=3)
        capabilities_table.heading("Feature", text="Feature")
        capabilities_table.heading("Supported", text="Supported")
        capabilities_table.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Add movement capabilities
        for feature, supported in self.camera.get_movement_table():
            capabilities_table.insert("", "end", values=(feature, "Yes" if supported else "No"))
            
    def create_movement_controls(self):
        """Create camera movement control buttons"""
        control_frame = ttk.Frame(self.main_frame)
        control_frame.grid(row=2, column=0, columnspan=3, pady=5)
        
        # Create movement buttons
        ttk.Button(control_frame, text="↑", width=3, command=lambda: self.move_camera("up")).grid(row=0, column=1)
        ttk.Button(control_frame, text="↓", width=3, command=lambda: self.move_camera("down")).grid(row=2, column=1)
        ttk.Button(control_frame, text="←", width=3, command=lambda: self.move_camera("left")).grid(row=1, column=0)
        ttk.Button(control_frame, text="→", width=3, command=lambda: self.move_camera("right")).grid(row=1, column=2)
        
        # Create zoom buttons
        zoom_frame = ttk.Frame(control_frame)
        zoom_frame.grid(row=1, column=3, padx=5)
        ttk.Button(zoom_frame, text="+", width=3, command=lambda: self.move_camera("zoom_in")).grid(row=0, column=0)
        ttk.Button(zoom_frame, text="-", width=3, command=lambda: self.move_camera("zoom_out")).grid(row=1, column=0)
        
    def move_camera(self, direction):
        """Move camera in specified direction"""
        if self.camera.move(direction):
            print(f"Camera moved {direction}")
        else:
            print(f"Failed to move camera {direction}")
            
    def cleanup(self):
        """Clean up resources"""
        self.window.destroy() 