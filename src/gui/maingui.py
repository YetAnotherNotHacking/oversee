import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import psutil
import time
import threading
from datetime import datetime
from PIL import Image, ImageTk
import cv2
import sqlite3
import os
from gui.rendermatrix import create_matrix_view as render_matrix
from utility.ip2loc import get_geolocation
from utility.iplist import get_ip_range
import os
import gui
import settings
import numpy as np
from gui.movementgui import MovementControlWindow
from gui.settingsgui import SettingsWindow
from gui.focusedmapgui import FocusedMapWindow
from concurrent.futures import ThreadPoolExecutor
import queue

ip_list_file = settings.ip_list_file

class MainGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SilverFlag | OVERSEE Worldwide Viewer v{settings.overseeversion}")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Initialize view state tracking
        self.active_view = "list"
        self.matrix_update_active = False
        self.preview_active = False
        self.current_preview_thread = None
        
        # Initialize thread pool
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Initialize image queue for cleanup
        self.image_queue = queue.Queue()
        
        # Count total IPs in file
        self.total_ips = self.count_valid_ips()
        
        # Set dark theme colors
        self.style = ttk.Style()
        self.style.theme_use('default')  # Reset to default theme
        
        # Configure dark theme colors
        self.style.configure('.',
            background='#2b2b2b',
            foreground='#ffffff',
            fieldbackground='#3c3f41',
            troughcolor='#3c3f41',
            selectbackground='#4b6eaf',
            selectforeground='#ffffff'
        )
        
        # Configure specific widget styles
        self.style.configure('TFrame', background='#2b2b2b')
        self.style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TButton', background='#3c3f41', foreground='#ffffff')
        self.style.configure('Treeview', 
            background='#2b2b2b',
            foreground='#ffffff',
            fieldbackground='#2b2b2b'
        )
        self.style.configure('Treeview.Heading',
            background='#3c3f41',
            foreground='#ffffff'
        )
        self.style.map('Treeview',
            background=[('selected', '#4b6eaf')],
            foreground=[('selected', '#ffffff')]
        )
        
        # Configure root window
        self.root.configure(bg='#2b2b2b')
        
        # Initialize database
        self.init_database()
        
        # Apply logo
        try:
            ico = Image.open('assets/logo.png')
            photo = ImageTk.PhotoImage(ico)
            self.root.wm_iconphoto(False, photo)
        except:
            print("Failed to load app icon, something might be up with your environment")
            pass

        # Configure grid weights for resizing
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Initialize camera data
        self.camera_data = {}
        
        # Initialize group data
        self.group_data = [
            {"id": 101, "name": "Security Cameras", "count": 0, "location": "All Locations", "status": "Monitoring"},
            {"id": 102, "name": "Public Cameras", "count": 0, "location": "Public Access", "status": "Monitoring"},
            {"id": 103, "name": "Private Cameras", "count": 0, "location": "Restricted", "status": "Monitoring"}
        ]
        
        self.setup_gui()
        self.update_system_info()
        
        # Start background camera status checker
        self.start_camera_status_checker()
        
    def init_database(self):
        """Initialize SQLite database for camera status tracking"""
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cameras.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Create initial connection to set up database
        conn = sqlite3.connect(db_path)
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
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cameras.db')
        return sqlite3.connect(db_path, check_same_thread=False)

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

    def get_camera_status(self, ip):
        """Get camera status from database"""
        try:
            conn = self.get_thread_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cameras WHERE ip = ?', (ip,))
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            print(f"Error getting camera status from database: {e}")
            return None

    def start_camera_status_checker(self):
        """Start background thread to check camera statuses"""
        def status_checker():
            while True:
                try:
                    # Get all cameras from database
                    conn = self.get_thread_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT ip FROM cameras')
                    cameras = cursor.fetchall()
                    conn.close()
                    
                    for (ip,) in cameras:
                        # Submit camera check to thread pool
                        self.thread_pool.submit(self.check_camera_status, ip, ip)
                    
                    # Wait before next check
                    time.sleep(300)  # Check every 5 minutes
                except Exception as e:
                    print(f"Error in camera status checker: {e}")
                    time.sleep(60)  # Wait a minute before retrying
        
        # Start status checker in thread pool
        self.thread_pool.submit(status_checker)

    def check_camera_status(self, item_id, ip):
        """Check if camera is accessible and update status"""
        try:
            from backend.cameradown import capture_single_frame, default_stream_params
            
            # Format camera URL with endpoint and parameters
            if '/' in ip:
                base_ip, endpoint = ip.split('/', 1)
                camera_url = f"http://{base_ip}/{endpoint}"
            else:
                camera_url = f"http://{ip}/video"
            
            # Add parameters based on endpoint
            for endpoint, params in default_stream_params.items():
                if endpoint.lower() in camera_url.lower():
                    if '?' not in camera_url:
                        camera_url = f"{camera_url}{params}"
                    break
            
            # Try to capture a frame
            frame = capture_single_frame(camera_url)
            
            if frame is not None:
                height, width = frame.shape[:2]
                resolution = f"{width}x{height}"
                status = "Online"
                
                # Get location information
                try:
                    location = get_geolocation(ip)
                except:
                    location = "Unknown"
                
                # Update database
                self.update_camera_status(
                    ip=ip,
                    status=status,
                    resolution=resolution,
                    stream_type="JPEG",
                    endpoint=endpoint if '/' in ip else "video",
                    location=location
                )
                
                # Update tree if item exists
                self.tree.after(0, lambda: self.update_tree_item(item_id, ip, status))
            else:
                self.update_camera_status(ip=ip, status="Offline")
                self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Offline"))
                
        except Exception as e:
            print(f"Error checking camera status: {e}")
            self.update_camera_status(ip=ip, status="Error")
            self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Error"))

    def setup_gui(self):
        # Create menu bar
        self.create_menu_bar()
        
        # Create main container
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Create tabs
        self.create_map_view()
        self.create_matrix_view()
        self.create_list_view()
        
        # Create status bar
        self.create_status_bar()
        
    def create_menu_bar(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Settings dropdown
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Preferences", command=self.open_preferences)
        settings_menu.add_command(label="Network Config", command=self.open_network_config)
        settings_menu.add_separator()
        settings_menu.add_command(label="About", command=self.show_about)
    
    def open_preferences(self):
        """Open the preferences window"""
        SettingsWindow(self.root)

    def open_network_config(self):
        messagebox.showinfo("Settings", "Network configuration dialog would open here")

    def show_about(self):
        messagebox.showinfo("About", "Main Application v1.0\nA comprehensive GUI application")

    def create_map_view(self):
        map_frame = ttk.Frame(self.notebook)
        self.notebook.add(map_frame, text="Map View")
        
        map_frame.grid_rowconfigure(0, weight=1)
        map_frame.grid_columnconfigure(0, weight=1)
        
        try:
            from tkintermapview import TkinterMapView
            import requests
            import json
            from utility.iplist import get_ip_range
            import sqlite3
            import os
            import threading
            
            # Initialize IP info database
            def init_ip_info_db():
                db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ip_info.db')
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ip_info (
                        ip TEXT PRIMARY KEY,
                        lat REAL,
                        lon REAL,
                        city TEXT,
                        country TEXT,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                conn.close()
                return db_path
            
            self.ip_info_db_path = init_ip_info_db()
            
            # Create the map widget
            map_widget = TkinterMapView(map_frame, width=800, height=600, corner_radius=0)
            map_widget.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            
            # Set initial position and zoom
            map_widget.set_position(0, 0)
            map_widget.set_zoom(2)
            
            # Add a marker at (0,0)
            marker = map_widget.set_marker(0, 0, text="Center of the World")
            
            # Add some controls
            control_frame = ttk.Frame(map_frame)
            control_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
            
            # Add map style selector
            ttk.Label(control_frame, text="Map Style:").grid(row=0, column=0, padx=5)
            map_style_var = tk.StringVar(value=getattr(settings, 'tile_server', 'OpenStreetMap'))
            map_style_combo = ttk.Combobox(control_frame, textvariable=map_style_var, 
                                         values=["OpenStreetMap", "Google normal", "Google satellite"],
                                         state='readonly', width=15)
            map_style_combo.grid(row=0, column=1, padx=5)
            
            def change_map_style(event=None):
                new_style = map_style_var.get()
                if new_style == "OpenStreetMap":
                    map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
                elif new_style == "Google normal":
                    map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
                elif new_style == "Google satellite":
                    map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
                # Update settings
                settings.tile_server = new_style
            
            map_style_combo.bind('<<ComboboxSelected>>', change_map_style)
            
            # Add zoom controls
            ttk.Button(control_frame, text="Zoom In", 
                      command=lambda: map_widget.set_zoom(map_widget.zoom + 1)).grid(row=0, column=2, padx=5)
            ttk.Button(control_frame, text="Zoom Out", 
                      command=lambda: map_widget.set_zoom(map_widget.zoom - 1)).grid(row=0, column=3, padx=5)
            
            # Add a button to reset view
            ttk.Button(control_frame, text="Reset View", 
                      command=lambda: map_widget.set_position(0, 0)).grid(row=0, column=4, padx=5)
            
            # Add process data button and progress bar
            process_frame = ttk.Frame(map_frame)
            process_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
            
            self.progress_var = tk.DoubleVar()
            self.progress_bar = ttk.Progressbar(process_frame, variable=self.progress_var, maximum=100)
            self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 5))
            
            # Add counter label
            self.counter_label = ttk.Label(process_frame, text="0/0")
            self.counter_label.grid(row=0, column=1, padx=5)
            
            def get_cached_ip_info(ip):
                """Get IP info from database"""
                try:
                    conn = sqlite3.connect(self.ip_info_db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT lat, lon, city, country FROM ip_info WHERE ip = ?', (ip,))
                    result = cursor.fetchone()
                    conn.close()
                    
                    if result:
                        return {
                            'ip': ip,
                            'lat': result[0],
                            'lon': result[1],
                            'city': result[2],
                            'country': result[3],
                            'base_ip': ip
                        }
                except Exception as e:
                    print(f"Error getting cached IP info: {e}")
                return None
            
            def save_ip_info(data):
                """Save IP info to database"""
                try:
                    conn = sqlite3.connect(self.ip_info_db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO ip_info (ip, lat, lon, city, country, last_updated)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (data['ip'], data['lat'], data['lon'], data['city'], data['country']))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Error saving IP info: {e}")
            
            def add_marker_to_map(result):
                """Add a marker to the map (called from main thread)"""
                if result:
                    # Create marker with IP info
                    marker_text = f"{result['base_ip']}\n{result['city']}, {result['country']}"
                    marker = map_widget.set_marker(result['lat'], result['lon'], text=marker_text)
                    
                    # Add click event using standard Tkinter binding
                    def on_marker_click(event, ip=result['ip']):
                        # Switch to list view and select the IP
                        self.notebook.select(2)  # Switch to list view tab
                        for item in self.tree.get_children():
                            if self.tree.item(item)['values'][0] == ip:
                                self.tree.selection_set(item)
                                self.tree.see(item)
                                break
                    
                    # Bind click event to the marker's canvas item
                    if hasattr(marker, 'canvas_item'):
                        map_widget.canvas.tag_bind(marker.canvas_item, '<Button-1>', on_marker_click)
            
            def process_ip_data():
                # Clear existing markers
                map_widget.delete_all_marker()
                
                # Get IP list
                ip_list = get_ip_range(settings.ip_list_file, 1, self.total_ips)
                total_ips = len(ip_list)
                processed_count = 0
                
                # Reset progress
                self.progress_var.set(0)
                self.counter_label.config(text=f"0/{total_ips}")
                
                def process_next_ip(index=0):
                    if index >= len(ip_list):
                        return
                    
                    ip = ip_list[index]
                    try:
                        # Extract base IP without endpoint or port
                        base_ip = ip.split('/')[0] if '/' in ip else ip
                        base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
                        
                        # Check cache first
                        result = get_cached_ip_info(base_ip)
                        
                        if not result:
                            # Get IP info from API
                            response = requests.get(f"https://ipinfo.io/{base_ip}")
                            if response.status_code == 200:
                                data = response.json()
                                if 'loc' in data:
                                    lat, lon = map(float, data['loc'].split(','))
                                    result = {
                                        'ip': base_ip,
                                        'lat': lat,
                                        'lon': lon,
                                        'city': data.get('city', ''),
                                        'country': data.get('country', ''),
                                        'base_ip': base_ip
                                    }
                                    # Save to database
                                    save_ip_info(result)
                        
                        if result:
                            # Add marker in main thread
                            self.root.after(0, lambda r=result: add_marker_to_map(r))
                        
                        # Update progress
                        nonlocal processed_count
                        processed_count += 1
                        progress = (processed_count / total_ips) * 100
                        self.root.after(0, lambda: self.progress_var.set(progress))
                        self.root.after(0, lambda: self.counter_label.config(text=f"{processed_count}/{total_ips}"))
                        
                        # Process next IP with a small delay to keep GUI responsive
                        self.root.after(10, lambda: process_next_ip(index + 1))
                        
                    except Exception as e:
                        print(f"Error processing IP {ip}: {e}")
                        # Continue with next IP
                        self.root.after(10, lambda: process_next_ip(index + 1))
                
                # Start processing in a separate thread
                self.thread_pool.submit(process_next_ip)
            
            ttk.Button(process_frame, text="Process IP Data", 
                      command=process_ip_data).grid(row=0, column=2, padx=5)
            
            # Store the map widget for later use
            self.map_widget = map_widget
            
            # Set initial map style
            change_map_style()
            
            # Start processing on startup
            self.root.after(1000, process_ip_data)  # Start after 1 second to let GUI initialize
            
        except ImportError:
            # If tkintermapview is not installed, show an error message
            error_label = ttk.Label(
                map_frame,
                text="Map view requires the 'tkintermapview' package.\nPlease install it using: pip install tkintermapview",
                justify='center',
                foreground='red'
            )
            error_label.grid(row=0, column=0, padx=10, pady=10)

    def create_matrix_view(self):
        matrix_frame = ttk.Frame(self.notebook)
        self.notebook.add(matrix_frame, text="Matrix View")
        
        # Configure frame for resizing
        matrix_frame.grid_rowconfigure(0, weight=1)
        matrix_frame.grid_columnconfigure(0, weight=1)
        
        # Create canvas for matrix display
        self.matrix_canvas = tk.Canvas(matrix_frame, bg='#2b2b2b', highlightthickness=0)
        self.matrix_canvas.grid(row=0, column=0, sticky="nsew")
        
        # Start matrix update thread
        self.update_matrix_display()

    def update_matrix_display(self):
        """Update the matrix display with current camera streams"""
        # Only update if matrix view is active
        if not self.matrix_update_active:
            self.root.after(2000, self.update_matrix_display)
            return
            
        # Get canvas dimensions
        canvas_width = self.matrix_canvas.winfo_width()
        canvas_height = self.matrix_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready yet, try again later
            self.root.after(100, self.update_matrix_display)
            return
        
        try:
            # Create matrix view using the camera manager
            matrix_image = render_matrix(canvas_width, canvas_height)
            
            if matrix_image is not None:
                # Convert CV2 image to PIL then to PhotoImage
                matrix_rgb = cv2.cvtColor(matrix_image, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(matrix_rgb)
                
                # Keep reference to prevent garbage collection
                self.matrix_photo = ImageTk.PhotoImage(pil_image)
                
                # Clear canvas and display image
                self.matrix_canvas.delete("all")
                self.matrix_canvas.create_image(
                    canvas_width//2, canvas_height//2,
                    image=self.matrix_photo,
                    anchor="center"
                )
            
        except Exception as e:
            print(f"Matrix display error: {e}")
            self.matrix_canvas.delete("all")
            self.matrix_canvas.create_text(
                canvas_width//2, canvas_height//2,
                text=f"Display error: {str(e)[:50]}...",
                fill="red",
                font=('Arial', 12),
                justify="center"
            )
        
        # Schedule next update
        self.root.after(2000, self.update_matrix_display)

    def cleanup_on_close(self):
        """Clean up resources when closing the application"""
        try:
            # Stop all background operations
            self.preview_active = False
            self.matrix_update_active = False
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=False)
            
            # Clean up images
            while not self.image_queue.empty():
                try:
                    img = self.image_queue.get_nowait()
                    if hasattr(img, '_PhotoImage__photo'):
                        del img._PhotoImage__photo
                except:
                    pass
            
            # Import and cleanup the camera manager
            from gui.rendermatrix import cleanup_camera_manager
            cleanup_camera_manager()
        except ImportError:
            pass
        
        # Destroy the root window
        self.root.destroy()

    def create_list_view(self):
        list_frame = ttk.Frame(self.notebook)
        self.notebook.add(list_frame, text="List View")
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_columnconfigure(1, weight=2)
        
        # Left panel - scrollable list
        left_panel = ttk.Frame(list_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        
        # Create treeview for list items
        self.tree = ttk.Treeview(left_panel, columns=('Name', 'Status'), show='tree headings')
        self.tree.heading('#0', text='ID')
        self.tree.heading('Name', text='IP Address')
        self.tree.heading('Status', text='Status')
        
        self.tree.column('#0', width=50)
        self.tree.column('Name', width=150)
        self.tree.column('Status', width=80)
        
        # Initialize camera data storage
        self.camera_data = {}
        self.current_preview_thread = None
        self.preview_active = False
        
        # Initialize active view tracking
        self.active_view = "list"
        self.matrix_update_active = False
        
        # Load IP addresses and populate treeview
        self.load_ip_addresses()
        
        # Scrollbar for treeview
        tree_scroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self.on_item_select)
        
        # Right panel - details view
        right_panel = ttk.Frame(list_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # Image display area
        self.image_frame = ttk.LabelFrame(right_panel, text="Camera Preview", padding=10)
        self.image_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Placeholder for image
        self.image_label = ttk.Label(self.image_frame, text="Select a camera to view preview", 
                                width=40, anchor='center')
        self.image_label.grid(row=0, column=0, pady=20, ipady=50)
        
        # Camera controls frame
        controls_frame = ttk.LabelFrame(right_panel, text="Camera Controls", padding=10)
        controls_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        # Create buttons
        ttk.Button(controls_frame, text="Favourite Camera", 
                  command=self.favourite_camera).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(controls_frame, text="Move Camera", 
                  command=self.open_move_camera_window).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(controls_frame, text="Open in Browser", 
                  command=self.open_camera_in_browser).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(controls_frame, text="Get IPINFO", 
                  command=self.get_ip_info).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(controls_frame, text="Show on Map", 
                  command=self.show_camera_on_map).grid(row=0, column=4, padx=5, pady=5)
        
        # Properties frame
        self.properties_frame = ttk.LabelFrame(right_panel, text="Properties", padding=10)
        self.properties_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        
        # Properties labels
        self.prop_name = ttk.Label(self.properties_frame, text="IP Address: Select a camera", font=('Arial', 10, 'bold'))
        self.prop_name.grid(row=0, column=0, sticky="w", pady=2)
        
        self.prop_location = ttk.Label(self.properties_frame, text="Location: -")
        self.prop_location.grid(row=1, column=0, sticky="w", pady=2)
        
        self.prop_status = ttk.Label(self.properties_frame, text="Status: -")
        self.prop_status.grid(row=2, column=0, sticky="w", pady=2)
        
        self.prop_resolution = ttk.Label(self.properties_frame, text="Resolution: -")
        self.prop_resolution.grid(row=3, column=0, sticky="w", pady=2)

    def on_tab_change(self, event):
        """Handle tab changes to manage active views and threads"""
        current_tab = self.notebook.select()
        tab_text = self.notebook.tab(current_tab, "text")
        
        # Update active view
        self.active_view = tab_text.lower().replace(" view", "")
        
        # Handle matrix view
        if self.active_view == "matrix":
            self.matrix_update_active = True
        else:
            self.matrix_update_active = False
            # Clear matrix canvas if switching away
            if hasattr(self, 'matrix_canvas'):
                self.matrix_canvas.delete("all")
        
        # Handle list view
        if self.active_view != "list":
            # Stop camera preview if switching away from list view
            self.preview_active = False
            if self.current_preview_thread and self.current_preview_thread.is_alive():
                self.current_preview_thread.join(timeout=1)
            self.image_label.config(image='', text="Select a camera to view preview")

    def load_ip_addresses(self):
        """Load IP addressses from file and populate the treeview"""
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Get IP addresses from file (loading all valid IPs)
            ip_list = get_ip_range(settings.ip_list_file, 1, self.total_ips)
            
            # Populate treeview with IP addresses
            for i, ip in enumerate(ip_list, 1):
                item_id = self.tree.insert('', 'end', text=str(i), 
                                        values=(ip, "Unknown"))
                
                # Initialize camera data
                self.camera_data[item_id] = {
                    'ip': ip,
                    'status': 'Unknown',
                    'location': None,
                    'resolution': None,
                    'last_check': None
                }
                
                # Submit camera check to thread pool
                self.thread_pool.submit(self.check_camera_status, item_id, ip)
                
        except Exception as e:
            print(f"Error loading IP addresses: {e}")

    def update_tree_item(self, item_id, ip, status):
        """Update treeview item with new status"""
        try:
            # Set status color based on state
            if status == "Online":
                status_color = "#00ff00"  # Green
            elif status == "Offline":
                status_color = "#ff0000"  # Red
            elif status == "Processing":
                status_color = "#000080"  # Navy Blue
            else:
                status_color = "#ffffff"  # White for unknown/other states
            
            self.tree.item(item_id, values=(ip, status), tags=(status,))
            self.tree.tag_configure(status, foreground=status_color)
        except tk.TclError:
            pass  # Item may have been deleted

    def on_item_select(self, event):
        """Handle item selection and start camera preview"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
        
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Update properties display
        self.prop_name.config(text=f"IP Address: {ip}")
        self.prop_location.config(text=f"Location: {camera_info.get('location', 'Checking...')}")
        self.prop_status.config(text=f"Status: {camera_info['status']}")
        self.prop_resolution.config(text=f"Resolution: {camera_info.get('resolution', '-')}")
        
        # Always try to start preview, but show appropriate status
        self.image_label.config(image='', text="Initializing camera connection...")
        
        # Start camera check in a separate thread
        threading.Thread(
            target=self.start_camera_preview,
            args=(ip,),
            daemon=True
        ).start()

    def start_camera_preview(self, ip):
        """Start camera preview in a separate thread"""
        # Stop current preview
        self.preview_active = False
        if self.current_preview_thread and self.current_preview_thread.is_alive():
            self.current_preview_thread.join(timeout=1)
        
        # Start new preview
        self.preview_active = True
        self.current_preview_thread = threading.Thread(
            target=self.camera_preview_worker, args=(ip,), daemon=True
        )
        self.current_preview_thread.start()

    def camera_preview_worker(self, ip):
        """Worker thread for camera preview"""
        try:
            from backend.cameradown import read_stream, camera_frames, camera_metadata, frame_lock, capture_single_frame, default_stream_params
            
            # Format the camera URL properly with appropriate endpoint and parameters
            if not ip.startswith(('http://', 'rtsp://')):
                # Extract endpoint from IP if it exists
                if '/' in ip:
                    base_ip, endpoint = ip.split('/', 1)
                    camera_url = f"http://{base_ip}/{endpoint}"
                else:
                    camera_url = f"http://{ip}/video"
                
                # Add parameters based on endpoint
                for endpoint, params in default_stream_params.items():
                    if endpoint.lower() in camera_url.lower():
                        if '?' not in camera_url:
                            camera_url = f"{camera_url}{params}"
                        break
            else:
                camera_url = ip
            
            print(f"Starting camera preview for: {camera_url}")
            
            # Try to capture a single frame first to test connection
            test_frame = capture_single_frame(camera_url)
            if test_frame is None:
                print(f"Failed to capture test frame from {camera_url}")
                self.image_label.after(0, lambda: self.image_label.config(
                    image='', text="Camera not responding"
                ))
                return
            
            # Start the camera stream
            stream_thread = threading.Thread(
                target=read_stream,
                args=(camera_url, camera_frames, {}, frame_lock),
                daemon=True
            )
            stream_thread.start()
            
            # Wait a bit for initial connection
            time.sleep(1)
            
            while self.preview_active:
                try:
                    with frame_lock:
                        frame = camera_frames.get(camera_url)
                        if frame is not None:
                            # Resize frame for display
                            frame = cv2.resize(frame, (320, 240))
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            
                            # Convert to PhotoImage
                            img = Image.fromarray(frame_rgb)
                            photo = ImageTk.PhotoImage(img)
                            
                            # Update label in main thread
                            self.image_label.after(0, lambda p=photo: self.update_preview_image(p))
                            
                            # Get metadata
                            metadata = camera_metadata.get(camera_url, {})
                            self.prop_resolution.config(text=f"Resolution: {metadata.get('resolution', '-')}")
                            self.prop_status.config(text=f"Status: {metadata.get('stream_type', 'Unknown')}")
                        else:
                            # Update status if no frame available
                            self.image_label.after(0, lambda: self.image_label.config(
                                image='', text="Waiting for camera feed..."
                            ))
                            
                    time.sleep(0.1)  # Limit frame rate
                    
                except Exception as e:
                    print(f"Error in preview loop: {str(e)}")  # Debug log
                    self.image_label.after(0, lambda: self.image_label.config(
                        image='', text=f"Preview error: {str(e)}"
                    ))
                    time.sleep(1)  # Wait before retrying
                
        except Exception as e:
            print(f"Fatal error in camera preview: {str(e)}")  # Debug log
            self.image_label.after(0, lambda: self.image_label.config(
                image='', text=f"Camera error: {str(e)}"
            ))

    def update_preview_image(self, photo):
        """Update preview image in main thread"""
        try:
            # Store old image for cleanup
            if hasattr(self.image_label, 'image'):
                self.image_queue.put(self.image_label.image)
            
            self.image_label.config(image=photo, text='')
            self.image_label.image = photo  # Keep a reference to prevent garbage collection
        except tk.TclError:
            pass

    def create_status_bar(self):
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.grid_columnconfigure(4, weight=1)  # Make time label expand
        
        # System info labels with dark theme
        self.cpu_label = ttk.Label(status_frame, text="CPU: 0%")
        self.cpu_label.grid(row=0, column=0, padx=5, pady=2)
        
        self.ram_label = ttk.Label(status_frame, text="RAM: 0GB/0GB")
        self.ram_label.grid(row=0, column=1, padx=5, pady=2)
        
        self.network_up_label = ttk.Label(status_frame, text="↑ 0 KB/s")
        self.network_up_label.grid(row=0, column=2, padx=5, pady=2)
        
        self.network_down_label = ttk.Label(status_frame, text="↓ 0 KB/s")
        self.network_down_label.grid(row=0, column=3, padx=5, pady=2)
        
        # Time label (right-aligned)
        self.time_label = ttk.Label(status_frame, text="00:00:00")
        self.time_label.grid(row=0, column=4, padx=5, pady=2, sticky="e")
    
    def update_system_info(self):
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_label.config(text=f"CPU: {cpu_percent:.1f}%")
            
            # Memory usage
            memory = psutil.virtual_memory()
            used_gb = memory.used / (1024**3)
            total_gb = memory.total / (1024**3)
            self.ram_label.config(text=f"RAM: {used_gb:.1f}GB/{total_gb:.1f}GB")
            
            # Network usage (simplified - you may want to track deltas)
            net_io = psutil.net_io_counters()
            self.network_up_label.config(text=f"↑ {net_io.bytes_sent // 1024} KB")
            self.network_down_label.config(text=f"↓ {net_io.bytes_recv // 1024} KB")
            
            # Current time
            current_time = datetime.now().strftime("%H:%M:%S")
            self.time_label.config(text=current_time)
            
        except Exception as e:
            print(f"Error updating system info: {e}")
        
        # Schedule next update
        self.root.after(1000, self.update_system_info)
    
    def placeholder_action(self):
        messagebox.showinfo("Action", "This is a placeholder button action!")

    def favourite_camera(self):
        """Placeholder for favourite camera functionality"""
        messagebox.showinfo("Favourite Camera", "This feature is not implemented yet.")

    def open_move_camera_window(self):
        """Open window for camera movement controls"""
        MovementControlWindow(self.root)

    def get_ip_info(self):
        """Show IP information in a new window"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera first.")
            return
            
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
            
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Extract base IP without endpoint or port
        base_ip = ip.split('/')[0] if '/' in ip else ip
        base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
        
        # Create new window
        info_window = tk.Toplevel(self.root)
        info_window.title(f"IP Information: {base_ip}")
        info_window.geometry("400x500")
        
        # Make it modal
        info_window.transient(self.root)
        info_window.grab_set()
        
        # Center the window
        info_window.update_idletasks()
        x = (info_window.winfo_screenwidth() // 2) - (400 // 2)
        y = (info_window.winfo_screenheight() // 2) - (500 // 2)
        info_window.geometry(f"400x500+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(info_window, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Add scrollable text widget
        text_widget = tk.Text(main_frame, wrap="word", height=20, width=40)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Get IP info from database
        try:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ip_info.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ip_info WHERE ip = ?', (base_ip,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Format and display the information
                info_text = f"IP Address: {result[0]}\n"
                info_text += f"Latitude: {result[1]}\n"
                info_text += f"Longitude: {result[2]}\n"
                info_text += f"City: {result[3]}\n"
                info_text += f"Country: {result[4]}\n"
                info_text += f"Last Updated: {result[5]}\n"
                
                # Add additional information from ipinfo.io
                try:
                    import requests
                    response = requests.get(f"https://ipinfo.io/{base_ip}/json")
                    if response.status_code == 200:
                        data = response.json()
                        info_text += "\nAdditional Information:\n"
                        info_text += f"Hostname: {data.get('hostname', 'N/A')}\n"
                        info_text += f"Organization: {data.get('org', 'N/A')}\n"
                        info_text += f"Postal Code: {data.get('postal', 'N/A')}\n"
                        info_text += f"Region: {data.get('region', 'N/A')}\n"
                        info_text += f"Timezone: {data.get('timezone', 'N/A')}\n"
                except Exception as e:
                    info_text += f"\nError fetching additional info: {str(e)}"
            else:
                info_text = "No IP information available in database."
                
        except Exception as e:
            info_text = f"Error loading IP information: {str(e)}"
        
        # Insert text and make it read-only
        text_widget.insert("1.0", info_text)
        text_widget.configure(state="disabled")
        
        # Add close button
        close_button = ttk.Button(info_window, text="Close", command=info_window.destroy)
        close_button.pack(pady=10)
        
        # Bind ESC key to close
        info_window.bind('<Escape>', lambda e: info_window.destroy())

    def open_camera_in_browser(self):
        """Open the selected camera's IP in the default browser"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera first.")
            return
            
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
            
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Extract base IP without endpoint or port
        base_ip = ip.split('/')[0] if '/' in ip else ip
        base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
        
        # Open in browser
        import webbrowser
        webbrowser.open(f"http://{base_ip}")

    def show_camera_on_map(self):
        """Open a focused map view for the selected camera"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera first.")
            return
            
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
            
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Open focused map window
        FocusedMapWindow(self.root, ip)

    def count_valid_ips(self):
        """Count the number of valid IPs in the file"""
        try:
            with open(settings.ip_list_file, 'r') as f:
                # Count non-empty lines that don't start with # or whitespace
                count = sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
            return count
        except Exception as e:
            print(f"Error counting IPs: {e}")
            return 100  # Fallback to default value


def runmaingui():
    root = tk.Tk()
    app = MainGUI(root)
    def on_closing():
        app.cleanup_on_close()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()