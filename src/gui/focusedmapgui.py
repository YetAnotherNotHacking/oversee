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
        
        # Create control frame at the top
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        # Add map style selector
        style_label = ttk.Label(control_frame, text="Map Style:")
        style_label.pack(side="left", padx=5)
        
        self.style_var = tk.StringVar(value="OpenStreetMap")
        style_combo = ttk.Combobox(control_frame, textvariable=self.style_var, state="readonly")
        style_combo['values'] = (
            "OpenStreetMap",
            "Google normal",
            "Google satellite",
            "Painting style",
            "Black and white",
            "Hiking map",
            "No labels",
            "Swiss topo"
        )
        style_combo.pack(side="left", padx=5)
        
        # Bind style change
        style_combo.bind('<<ComboboxSelected>>', self.change_map_style)
        
        # Create map widget
        self.map_widget = TkinterMapView(self.window, width=800, height=550, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        
        # Add close button
        close_button = ttk.Button(self.window, text="Close", command=self.window.destroy)
        close_button.pack(pady=5)
        
        # Bind ESC key to close
        self.window.bind('<Escape>', lambda e: self.window.destroy())
        
        # Load and display camera location
        self.load_camera_location(ip)
        
        # Set initial map style
        self.change_map_style()
    
    def change_map_style(self, event=None):
        """Change the map style"""
        style = self.style_var.get()
        if style == "OpenStreetMap":
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        elif style == "Google normal":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif style == "Google satellite":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif style == "Painting style":
            self.map_widget.set_tile_server("http://c.tile.stamen.com/watercolor/{z}/{x}/{y}.png")
        elif style == "Black and white":
            self.map_widget.set_tile_server("http://a.tile.stamen.com/toner/{z}/{x}/{y}.png")
        elif style == "Hiking map":
            self.map_widget.set_tile_server("https://tiles.wmflabs.org/hikebike/{z}/{x}/{y}.png")
        elif style == "No labels":
            self.map_widget.set_tile_server("https://tiles.wmflabs.org/osm-no-labels/{z}/{x}/{y}.png")
        elif style == "Swiss topo":
            self.map_widget.set_tile_server("https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/{z}/{x}/{y}.jpeg")
    
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
                
                # Create a click handler for the marker
                def click_marker_event(marker):
                    print("marker clicked:", marker.text)
                    # Toggle the circle visibility
                    if hasattr(self, 'circle'):
                        if self.circle.is_hidden:
                            self.circle.hide(False)
                        else:
                            self.circle.hide(True)
                
                # Create the marker with click handler
                marker = self.map_widget.set_marker(lat, lon, text=marker_text, command=click_marker_event)
                
                # Add a small circle around the marker to make it more visible
                self.circle = self.map_widget.set_circle(lat, lon, 1000, fill_color="red", outline_color="red", border_width=2, opacity=0.3)
                
                # Add hover effect to marker
                if hasattr(marker, 'canvas_item'):
                    self.map_widget.canvas.tag_bind(marker.canvas_item, '<Enter>', 
                        lambda e: self.map_widget.canvas.itemconfig(marker.canvas_item, fill='red'))
                    self.map_widget.canvas.tag_bind(marker.canvas_item, '<Leave>', 
                        lambda e: self.map_widget.canvas.itemconfig(marker.canvas_item, fill='blue'))
            else:
                # If no location data, center on (0,0) and show message
                self.map_widget.set_position(0, 0)
                self.map_widget.set_zoom(2)
                self.map_widget.set_marker(0, 0, text="Location data not available")
                
        except Exception as e:
            print(f"Error loading camera location: {e}")
            # Only show error if we haven't already set a marker
            if not self.map_widget.canvas.find_withtag("marker"):
                self.map_widget.set_position(0, 0)
                self.map_widget.set_zoom(2)
                self.map_widget.set_marker(0, 0, text="Error loading location data") 