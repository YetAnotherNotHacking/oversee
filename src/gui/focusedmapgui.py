import tkinter as tk
from tkinter import ttk
from tkintermapview import TkinterMapView
import sqlite3
import os

class FocusedMapWindow:
    def __init__(self, parent, ip):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Camera Location: {ip}")
        self.window.geometry("800x600")
        
        # Make it modal
        self.window.transient(parent)
        self.window.grab_set()
        
        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.window.winfo_screenheight() // 2) - (600 // 2)
        self.window.geometry(f"800x600+{x}+{y}")
        
        # Create map widget
        self.map_widget = TkinterMapView(self.window, width=800, height=600, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        
        # Add close button
        close_button = ttk.Button(self.window, text="Close", command=self.window.destroy)
        close_button.pack(pady=5)
        
        # Bind ESC key to close
        self.window.bind('<Escape>', lambda e: self.window.destroy())
        
        # Load and display camera location
        self.load_camera_location(ip)
    
    def load_camera_location(self, ip):
        """Load camera location from database and display on map"""
        try:
            # Extract base IP without endpoint or port
            base_ip = ip.split('/')[0] if '/' in ip else ip
            base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
            
            # Get location from database
            db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ip_info.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT lat, lon, city, country FROM ip_info WHERE ip = ?', (base_ip,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                lat, lon, city, country = result
                
                # Set map position and zoom
                self.map_widget.set_position(lat, lon)
                self.map_widget.set_zoom(10)  # Closer zoom for single camera
                
                # Add marker
                marker_text = f"{base_ip}\n{city}, {country}"
                marker = self.map_widget.set_marker(lat, lon, text=marker_text)
                
                # Add a small circle around the marker to make it more visible
                self.map_widget.set_circle(lat, lon, 1000, fill_color="red", outline_color="red", border_width=2, opacity=0.3)
            else:
                # If no location data, center on (0,0) and show message
                self.map_widget.set_position(0, 0)
                self.map_widget.set_zoom(2)
                self.map_widget.set_marker(0, 0, text="Location data not available")
                
        except Exception as e:
            print(f"Error loading camera location: {e}")
            # Show error on map
            self.map_widget.set_position(0, 0)
            self.map_widget.set_zoom(2)
            self.map_widget.set_marker(0, 0, text="Error loading location data") 