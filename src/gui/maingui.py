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
from documentationmd.views import documentationviews
from gui.movementgui import MovementGUI
from gui.settingsgui import SettingsWindow
from gui.focusedmapgui import FocusedMapWindow
from gui.markdownhelpgui import show_markdown_docs
from concurrent.futures import ThreadPoolExecutor
import queue
import requests
from gui.aboutgui import AboutGUI
import json
import webbrowser
import io
import socket

ip_list_file = settings.ip_list_file

# Documentations
viewtypemarkdown = documentationviews

class MainGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SilverFlag | OVERSEE Device Manager v{settings.overseeversion}")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Initialize view state tracking
        self.active_view = "list"
        self.matrix_update_active = False
        self.preview_active = False
        self.current_preview_thread = None
        self.status_checker_active = True
        self.is_shutting_down = False
        
        # Initialize thread pool for camera checks
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Initialize status checker thread
        self.status_checker_thread = None
        
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
        
        # Configure entry and combobox styles
        self.style.configure('TEntry',
            fieldbackground='#3c3f41',
            foreground='#ffffff',
            insertcolor='#ffffff'
        )
        
        self.style.configure('TCombobox',
            fieldbackground='#3c3f41',
            background='#3c3f41',
            foreground='#ffffff',
            arrowcolor='#ffffff'
        )
        
        # Configure combobox popup list
        self.style.map('TCombobox',
            fieldbackground=[('readonly', '#3c3f41')],
            selectbackground=[('readonly', '#4b6eaf')],
            selectforeground=[('readonly', '#ffffff')]
        )
        
        # Configure root window
        self.root.configure(bg='#2b2b2b')
        
        # Initialize database
        self.init_database()
        
        # Apply logo from the remote repository
        try:
            url = "https://raw.githubusercontent.com/YetAnotherNotHacking/oversee/refs/heads/main/assets/logo.png"
            with urllib.request.urlopen(url) as response:
                data = response.read()
            ico = Image.open(BytesIO(data))
            photo = ImageTk.PhotoImage(ico)
            self.root.wm_iconphoto(False, photo)
        except Exception as e:
            print("Failed to load app icon from URL:", e)
            pass

        # Configure grid weights for resizing
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Initialize camera data
        self.camera_data = {}
        
        self.setup_gui()
        self.update_system_info()
        
        # Start background camera status checker
        self.start_camera_status_checker()
        
    def init_database(self):
        """Initialize SQLite database for camera status tracking"""
        db_path = settings.cameras_db
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
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
        return sqlite3.connect(settings.cameras_db, check_same_thread=False)

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
            while self.status_checker_active and not self.is_shutting_down:
                try:
                    # Get all cameras from database
                    conn = self.get_thread_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT ip FROM cameras')
                    cameras = cursor.fetchall()
                    conn.close()
                    
                    for (ip,) in cameras:
                        if not self.status_checker_active or self.is_shutting_down:
                            break
                        # Submit camera check to thread pool
                        if not self.thread_pool._shutdown and not self.is_shutting_down:
                            self.thread_pool.submit(self.check_camera_status, ip, ip)
                    
                    # Wait before next check
                    for _ in range(300):  # Check every 5 minutes, but check status every second
                        if not self.status_checker_active or self.is_shutting_down:
                            break
                        time.sleep(1)
                except Exception as e:
                    print(f"Error in camera status checker: {e}")
                    if self.status_checker_active and not self.is_shutting_down:
                        time.sleep(60)  # Wait a minute before retrying
        
        # Start status checker in a dedicated thread
        if not self.status_checker_thread or not self.status_checker_thread.is_alive():
            self.status_checker_thread = threading.Thread(target=status_checker, daemon=True)
            self.status_checker_thread.start()

    def check_camera_status(self, item_id, ip):
        """Check if camera is accessible and update status"""
        if self.is_shutting_down or not hasattr(self, 'thread_pool') or self.thread_pool._shutdown:
            return
            
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
                if not self.is_shutting_down:
                    self.tree.after(0, lambda: self.update_tree_item(item_id, ip, status))
            else:
                self.update_camera_status(ip=ip, status="Offline")
                if not self.is_shutting_down:
                    self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Offline"))
                
        except Exception as e:
            print(f"Error checking camera status: {e}")
            self.update_camera_status(ip=ip, status="Error")
            if not self.is_shutting_down:
                self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Error"))
        
    def setup_gui(self):
        # Create menu bar
        self.create_menu_bar()
        
        # Create main container
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Create main notebook for categories
        self.main_notebook = ttk.Notebook(main_frame)
        self.main_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create category tabs
        self.create_cameras_tab()
        self.create_printers_tab()
        
        # Create status bar
        self.create_status_bar()
        
    def create_cameras_tab(self):
        """Create the Cameras tab with all camera-related functionality"""
        cameras_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(cameras_frame, text="Cameras")
        
        # Configure grid for cameras frame
        cameras_frame.grid_rowconfigure(0, weight=1)
        cameras_frame.grid_columnconfigure(0, weight=1)
        
        # Create notebook for camera views
        self.notebook = ttk.Notebook(cameras_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Create camera view tabs
        self.create_map_view()
        self.create_matrix_view()
        self.create_list_view()
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
        
    def create_printers_tab(self):
        """Create the Printers tab"""
        printers_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(printers_frame, text="Printers")
        
        # Configure grid for printers frame
        printers_frame.grid_rowconfigure(0, weight=1)
        printers_frame.grid_columnconfigure(0, weight=1)
        
        # Create content frame
        content_frame = ttk.Frame(printers_frame)
        content_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Add placeholder content
        placeholder_label = ttk.Label(
            content_frame,
            text="Printer management functionality coming soon...",
            justify='center',
            font=('Arial', 12)
        )
        placeholder_label.pack(expand=True)
        
    def create_map_view(self):
        map_frame = ttk.Frame(self.notebook)
        self.notebook.add(map_frame, text="Map View")
        
        map_frame.grid_rowconfigure(0, weight=1)
        map_frame.grid_columnconfigure(0, weight=1)
        
        try:
            from tkintermapview import TkinterMapView
            
            # Create the map widget
            map_widget = TkinterMapView(map_frame, width=800, height=600, corner_radius=0)
            map_widget.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            
            # Set initial position and zoom
            map_widget.set_position(0, 0)
            map_widget.set_zoom(2)
            
            # Add map style selector
            control_frame = ttk.Frame(map_frame)
            control_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            
            style_label = ttk.Label(control_frame, text="Map Style:")
            style_label.grid(row=0, column=0, padx=5, pady=5)
            
            style_var = tk.StringVar(value="OpenStreetMap")
            style_combo = ttk.Combobox(control_frame, textvariable=style_var, state="readonly")
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
            style_combo.grid(row=0, column=1, padx=5, pady=5)
            
            def change_map_style(event=None):
                style = style_var.get()
                if style == "OpenStreetMap":
                    map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
                elif style == "Google normal":
                    map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
                elif style == "Google satellite":
                    map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
                elif style == "Painting style":
                    map_widget.set_tile_server("http://c.tile.stamen.com/watercolor/{z}/{x}/{y}.png")
                elif style == "Black and white":
                    map_widget.set_tile_server("http://a.tile.stamen.com/toner/{z}/{x}/{y}.png")
                elif style == "Hiking map":
                    map_widget.set_tile_server("https://tiles.wmflabs.org/hikebike/{z}/{x}/{y}.png")
                elif style == "No labels":
                    map_widget.set_tile_server("https://tiles.wmflabs.org/osm-no-labels/{z}/{x}/{y}.png")
                elif style == "Swiss topo":
                    map_widget.set_tile_server("https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/{z}/{x}/{y}.jpeg")
            
            style_combo.bind('<<ComboboxSelected>>', change_map_style)
            
            # Add marker count control
            count_frame = ttk.Frame(control_frame)
            count_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5)
            
            ttk.Label(count_frame, text="Markers to load:").pack(side="left", padx=5)
            count_var = tk.StringVar(value="100")
            count_entry = ttk.Entry(count_frame, textvariable=count_var, width=10)
            count_entry.pack(side="left", padx=5)
            
            # Add progress bar
            progress_frame = ttk.Frame(map_frame)
            progress_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
            
            self.progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
            progress_bar.pack(side="left", fill="x", expand=True)
            
            # Add counter label
            self.counter_label = ttk.Label(progress_frame, text="0/0")
            self.counter_label.pack(side="right", padx=5)
            
            def load_markers_thread():
                """Load markers in a separate thread"""
                try:
                    # Clear existing markers
                    map_widget.delete_all_marker()
                    
                    # Get number of markers to load
                    try:
                        num_markers = int(count_var.get())
                    except ValueError:
                        num_markers = 100
                    
                    # Connect to database
                    conn = sqlite3.connect(settings.ip_info_db)
                    cursor = conn.cursor()
                    cursor.execute('SELECT ip, lat, lon, city, country FROM ip_info LIMIT ?', (num_markers,))
                    results = cursor.fetchall()
                    conn.close()
                    
                    total_ips = len(results)
                    processed = 0
                    
                    # Reset progress
                    self.progress_var.set(0)
                    self.counter_label.config(text=f"0/{total_ips}")
                    
                    for ip, lat, lon, city, country in results:
                        # Create marker with IP info
                        marker_text = f"{ip}\n{city}, {country}"
                        
                        # Add marker in main thread
                        def add_marker(ip=ip, lat=lat, lon=lon, text=marker_text):
                            # Create click handler
                            def click_marker_event(marker):
                                print("marker clicked:", marker.text)
                                # Extract base IP from marker text
                                base_ip = marker.text.split('\n')[0]  # Get first line which is the IP
                                
                                # Switch to list view and select the IP
                                self.notebook.select(2)  # Switch to list view tab
                                
                                # Find and select the item in the tree
                                for item in self.tree.get_children():
                                    item_ip = self.tree.item(item)['values'][0]
                                    # Compare base IPs (without endpoints)
                                    item_base_ip = item_ip.split('/')[0] if '/' in item_ip else item_ip
                                    item_base_ip = item_base_ip.split(':')[0] if ':' in item_base_ip else item_base_ip
                                    
                                    if item_base_ip == base_ip:
                                        self.tree.selection_set(item)
                                        self.tree.see(item)
                                        # Trigger the selection event to show camera preview
                                        self.on_item_select(None)
                                        break
                            
                            # Create marker with click handler
                            marker = map_widget.set_marker(lat, lon, text=text, command=click_marker_event)
                            
                            # Add hover effect
                            if hasattr(marker, 'canvas_item'):
                                map_widget.canvas.tag_bind(marker.canvas_item, '<Enter>', 
                                    lambda e: map_widget.canvas.itemconfig(marker.canvas_item, fill='red'))
                                map_widget.canvas.tag_bind(marker.canvas_item, '<Leave>', 
                                    lambda e: map_widget.canvas.itemconfig(marker.canvas_item, fill='blue'))
                        
                        # Schedule marker addition in main thread
                        self.root.after(0, lambda: add_marker())
                        
                        # Update progress
                        processed += 1
                        progress = (processed / total_ips) * 100
                        self.progress_var.set(progress)
                        self.counter_label.config(text=f"{processed}/{total_ips}")
                        
                        # Small delay to keep GUI responsive
                        time.sleep(0.01)
                    
                    print(f"Loaded {processed} markers from database")
                    
                except Exception as e:
                    print(f"Error loading markers: {e}")
            
            def start_loading():
                """Start loading markers in a separate thread"""
                # Start loading thread
                threading.Thread(target=load_markers_thread, daemon=True).start()
            
            # Add load markers button
            load_button = ttk.Button(control_frame, text="Load Markers", command=start_loading)
            load_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
            
            # Store the map widget for later use
            self.map_widget = map_widget
            
            # Set initial map style
            change_map_style()
            
            # Load initial markers after a delay
            self.root.after(1000, start_loading)
            
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
        matrix_frame.grid_rowconfigure(1, weight=1)  # Changed from 0 to 1
        matrix_frame.grid_columnconfigure(0, weight=1)
        
        # Create control panel frame
        control_frame = ttk.Frame(matrix_frame)
        control_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Add thread count control
        ttk.Label(control_frame, text="Camera Tasks:").pack(side="left", padx=(0, 5))
        self.thread_count_var = tk.StringVar(value="200")  # Default value
        thread_count_entry = ttk.Entry(control_frame, textvariable=self.thread_count_var, width=6)
        thread_count_entry.pack(side="left", padx=(0, 5))
        
        # Add apply button
        apply_button = ttk.Button(control_frame, text="Apply", command=self.update_thread_count)
        apply_button.pack(side="left")
        
        # Create canvas for matrix display
        self.matrix_canvas = tk.Canvas(matrix_frame, bg='#2b2b2b', highlightthickness=0)
        self.matrix_canvas.grid(row=1, column=0, sticky="nsew")  # Changed from row 0 to 1
        
        # Initialize matrix state
        self.matrix_update_active = False
        self.matrix_photo = None
        self.matrix_thread = None
        self.matrix_lock = threading.Lock()
        self.matrix_queue = queue.Queue(maxsize=1)
        
        # Bind canvas resize event
        self.matrix_canvas.bind('<Configure>', self.on_matrix_canvas_resize)
        
        # Start matrix update thread
        self.start_matrix_updates()
        
    def update_thread_count(self):
        """Update the number of threads used for camera tasks"""
        try:
            new_count = int(self.thread_count_var.get())
            if new_count < 1:
                raise ValueError("Thread count must be positive")
                
            # Clean up existing camera manager
            from gui.rendermatrix import cleanup_camera_manager
            cleanup_camera_manager()
            
            # Create new camera manager with updated thread count
            from gui.rendermatrix import CameraManager
            global camera_manager
            camera_manager = CameraManager()
            camera_manager.connection_semaphore = threading.Semaphore(new_count)
            camera_manager.active = True
            camera_manager.load_camera_urls()
            
            # Force matrix update by restarting the matrix view
            self.matrix_update_active = False
            if self.matrix_thread and self.matrix_thread.is_alive():
                self.matrix_thread.join(timeout=1.0)
            self.matrix_update_active = True
            self.start_matrix_updates()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for thread count")
            self.thread_count_var.set("200")  # Reset to default
            
    def on_matrix_canvas_resize(self, event):
        """Handle canvas resize events"""
        if self.matrix_update_active:
            # Force an immediate update when canvas is resized
            self.update_matrix_display()
            
    def start_matrix_updates(self):
        """Start the matrix update thread"""
        def matrix_update_worker():
            while self.matrix_update_active and not self.is_shutting_down:
                try:
                    with self.matrix_lock:
                        # Get canvas dimensions
                        canvas_width = self.matrix_canvas.winfo_width()
                        canvas_height = self.matrix_canvas.winfo_height()
                        
                        if canvas_width <= 1 or canvas_height <= 1:
                            time.sleep(0.1)
                            continue
                        
                        # Create matrix view using the camera manager
                        try:
                            # Clear any old frames from the queue
                            while not self.matrix_queue.empty():
                                try:
                                    self.matrix_queue.get_nowait()
                                except queue.Empty:
                                    break
                            
                            # Get new frame
                            matrix_image = render_matrix(canvas_width, canvas_height)
                            
                            if matrix_image is not None and not self.is_shutting_down:
                                # Convert CV2 image to PIL then to PhotoImage
                                matrix_rgb = cv2.cvtColor(matrix_image, cv2.COLOR_BGR2RGB)
                                pil_image = Image.fromarray(matrix_rgb)
                                
                                # Put the new frame in the queue
                                try:
                                    self.matrix_queue.put_nowait(pil_image)
                                except queue.Full:
                                    pass  # Skip this frame if queue is full
                                
                                # Update canvas in main thread
                                if not self.is_shutting_down:
                                    self.root.after(0, self.update_matrix_canvas)
                            
                        except Exception as e:
                            print(f"Error in render_matrix: {e}")
                            time.sleep(1)
                            continue
                    
                    # Sleep for a short time to prevent high CPU usage
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Matrix update error: {e}")
                    time.sleep(1)  # Wait before retrying
        
        # Start matrix update thread
        self.matrix_thread = threading.Thread(target=matrix_update_worker, daemon=True)
        self.matrix_thread.start()
        
    def update_matrix_canvas(self):
        """Update the matrix canvas with the current image"""
        try:
            with self.matrix_lock:
                if not self.is_shutting_down:
                    # Get the latest frame from the queue
                    try:
                        pil_image = self.matrix_queue.get_nowait()
                        # Convert to PhotoImage
                        self.matrix_photo = ImageTk.PhotoImage(pil_image)
                        
                        # Clear canvas and display image
                        self.matrix_canvas.delete("all")
                        self.matrix_canvas.create_image(
                            self.matrix_canvas.winfo_width()//2,
                            self.matrix_canvas.winfo_height()//2,
                            image=self.matrix_photo,
                            anchor="center"
                        )
                    except queue.Empty:
                        pass  # No new frame available
        except Exception as e:
            print(f"Error updating matrix canvas: {e}")
            
    def on_tab_change(self, event):
        """Handle tab changes to manage active views and threads"""
        current_tab = self.notebook.select()
        tab_text = self.notebook.tab(current_tab, "text")
        
        # Update active view
        self.active_view = tab_text.lower().replace(" view", "")
        
        # Handle matrix view
        if self.active_view == "matrix":
            self.matrix_update_active = True
            # Start matrix updates if not already running
            if not self.matrix_thread or not self.matrix_thread.is_alive():
                self.start_matrix_updates()
        else:
            # Stop matrix updates if switching away
            self.matrix_update_active = False
            # Clear matrix canvas if switching away
            if hasattr(self, 'matrix_canvas'):
                self.matrix_canvas.delete("all")
                # Clear the frame queue
                while not self.matrix_queue.empty():
                    try:
                        self.matrix_queue.get_nowait()
                    except queue.Empty:
                        break
                # Force cleanup of any remaining matrix resources
                try:
                    from gui.rendermatrix import cleanup_camera_manager
                    cleanup_camera_manager()
                except (ImportError, Exception) as e:
                    print(f"Error cleaning up camera manager: {e}")
        
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
        """Update treeview item with new status and resort if needed"""
        try:
            # Get current item values
            current_values = self.tree.item(item_id)['values']
            if not current_values:
                return
                
            # Update the item with new status
            self.tree.item(item_id, values=(current_values[0], status))
            
            # Set appropriate tag based on status
            if status == "ONLINE":
                self.tree.item(item_id, tags=('online',))
                # Move online items to top
                self.tree.move(item_id, '', 0)
            elif status == "offline":
                self.tree.item(item_id, tags=('offline',))
            elif status == "Error":
                self.tree.item(item_id, tags=('error',))
            else:
                self.tree.item(item_id, tags=('unknown',))
                
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
        # Get the currently selected camera from the tree
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Camera Selected", "Please select a camera first.")
            return
            
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
            
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Open movement control window
        MovementGUI(self.root, ip)

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
        
        # Extract IP with port but without endpoint
        if '/' in ip:
            base_ip = ip.split('/')[0]
        else:
            base_ip = ip
        
        # Open in browser
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

    def reinit_all(self):
        import shutil
        import sys
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        answer = messagebox.askyesno("Reinitialize All Data", "This will delete all data and redownload everything. Are you sure?")
        if answer:
            try:
                if os.path.exists(data_dir):
                    shutil.rmtree(data_dir)
                messagebox.showinfo("Restarting", "The application will now restart to reinitialize data.")
                python = sys.executable
                os.execl(python, python, *sys.argv)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reinitialize: {e}")

    def reset_list_view(self):
        """Reset the list view to show all items"""
        # Clear search
        self.search_var.set("")
        
        # Clear the tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Reload all IP addresses
        self.load_ip_addresses()
        
        # Clear selection
        self.tree.selection_remove(self.tree.selection())

    def on_search_change(self, *args):
        """Handle search input changes"""
        search_text = self.search_var.get().lower()
        
        # Clear current selection
        self.tree.selection_remove(self.tree.selection())
        
        # If search is empty, show all items
        if not search_text:
            for item in self.tree.get_children():
                self.tree.reattach(item, '', 'end')
            return
        
        # Search through all items
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if not values:
                continue
                
            ip = values[0].lower()
            # Check if search text matches IP or endpoint
            if search_text in ip:
                # Select the first match
                if not self.tree.selection():
                    self.tree.selection_set(item)
                    self.tree.see(item)
                # Make sure matching items are visible
                self.tree.reattach(item, '', 'end')
            else:
                # Hide non-matching items
                self.tree.detach(item)

    def open_camera_stream(self):
        """Open the selected camera's stream in a new window"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera first.")
            return
            
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
            
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Open stream in new window
        from gui.focusedstreamgui import FocusedStreamWindow
        FocusedStreamWindow(ip)

    def open_in_ipinfo(self):
        """Open the selected camera's IP in IPINFO"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera first.")
            return
            
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
            
        camera_info = self.camera_data[item_id]
        ip = camera_info['ip']
        
        # Extract base IP without port or endpoint
        base_ip = ip.split('/')[0] if '/' in ip else ip
        base_ip = base_ip.split(':')[0] if ':' in base_ip else base_ip
        
        # Open in browser
        webbrowser.open(f"https://ipinfo.io/{base_ip}")

    def create_list_view(self):
        list_frame = ttk.Frame(self.notebook)
        self.notebook.add(list_frame, text="List View")
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
        
        list_frame.grid_rowconfigure(1, weight=1)  # Changed to 1 to make room for search
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_columnconfigure(1, weight=2)
        
        # Add search frame at the top
        search_frame = ttk.Frame(list_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        
        # Search label and entry
        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)  # Bind to search changes
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side="left", fill="x", expand=True)
        
        # Add reset button
        reset_button = ttk.Button(search_frame, text="Reset List", command=self.reset_list_view)
        reset_button.pack(side="left", padx=5)
        
        # Left panel - scrollable list
        left_panel = ttk.Frame(list_frame)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        
        # Create treeview for list items
        self.tree = ttk.Treeview(left_panel, columns=('Name', 'Status'), show='tree headings')
        self.tree.heading('#0', text='ID')
        self.tree.heading('Name', text='IP Address')
        self.tree.heading('Status', text='Status')
        
        self.tree.column('#0', width=50)
        self.tree.column('Name', width=150)
        self.tree.column('Status', width=100)
        
        # Configure status colors
        self.tree.tag_configure('online', background='#1a472a', foreground='#ffffff')  # Dark green
        self.tree.tag_configure('offline', background='#4a1a1a', foreground='#ffffff')  # Dark red
        self.tree.tag_configure('error', background='#4a3a1a', foreground='#ffffff')    # Dark yellow
        self.tree.tag_configure('unknown', background='#2b2b2b', foreground='#ffffff')  # Dark gray
        
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
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # Image display area
        self.image_frame = ttk.LabelFrame(right_panel, text="Camera Preview", padding=10)
        self.image_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Placeholder for image
        self.image_label = ttk.Label(self.image_frame, text="Select a camera to view preview", 
                                width=40, anchor='center')
        self.image_label.grid(row=0, column=0, pady=20, ipady=50)
        
        # Quick Actions Frame
        quick_actions_frame = ttk.LabelFrame(right_panel, text="Quick Actions", padding=10)
        quick_actions_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        # Create quick action buttons in a grid
        actions = [
            ("Deep Analysis", self.analyze_host),
            ("Open Stream", self.open_camera_stream),
            ("Show on Map", self.show_camera_on_map),
            ("Open in Browser", self.open_camera_in_browser),
            ("Get IP Info", self.get_ip_info),
            ("Open in IPInfo", self.open_in_ipinfo),
            ("Move Camera", self.open_move_camera_window)
        ]
        
        # Create buttons in a grid layout
        for i, (text, command) in enumerate(actions):
            row = i // 2
            col = i % 2
            btn = ttk.Button(quick_actions_frame, text=text, command=command)
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        
        # Configure grid weights for even spacing
        quick_actions_frame.grid_columnconfigure(0, weight=1)
        quick_actions_frame.grid_columnconfigure(1, weight=1)
        
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

    def create_menu_bar(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Settings dropdown
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Preferences", command=self.open_preferences)
        settings_menu.add_command(label="Network Config", command=self.open_network_config)
        settings_menu.add_separator()
        settings_menu.add_command(label="About", command=self.show_about)

        # Advanced dropdown
        advanced_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Advanced", menu=advanced_menu)
        advanced_menu.add_command(label="Reinit all", command=self.reinit_all)
        
    def open_preferences(self):
        """Open the preferences window"""
        SettingsWindow(self.root)
    
    def open_network_config(self):
        """Open network configuration dialog"""
        messagebox.showinfo("Settings", "Network configuration dialog would open here")
    
    def show_about(self):
        """Show about window"""
        AboutGUI(self.root)

    def cleanup_on_close(self):
        """Clean up resources when closing the application"""
        try:
            # Set shutdown flag first
            self.is_shutting_down = True
            
            # Stop all background operations
            self.preview_active = False
            self.matrix_update_active = False
            self.status_checker_active = False
            
            # Clear the matrix queue
            while not self.matrix_queue.empty():
                try:
                    self.matrix_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Wait for status checker thread to finish
            if self.status_checker_thread and self.status_checker_thread.is_alive():
                self.status_checker_thread.join(timeout=1.0)
                
            # Wait for matrix thread to finish
            if self.matrix_thread and self.matrix_thread.is_alive():
                self.matrix_thread.join(timeout=1.0)
            
            # Clean up images
            while not self.image_queue.empty():
                try:
                    img = self.image_queue.get_nowait()
                    if hasattr(img, '_PhotoImage__photo'):
                        del img._PhotoImage__photo
                except:
                    pass
            
            # Import and cleanup the camera manager
            try:
                from gui.rendermatrix import cleanup_camera_manager
                cleanup_camera_manager()
            except ImportError:
                pass
            except Exception as e:
                print(f"Error cleaning up camera manager: {e}")
            
            # Shutdown thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=False)
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        # Destroy the root window
        self.root.destroy()

    def analyze_host(self):
        """Analyze the selected camera for vulnerabilities and information"""
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
        
        # Create new window for analysis
        analysis_window = tk.Toplevel(self.root)
        analysis_window.title(f"Deep Analysis: {base_ip}")
        analysis_window.geometry("600x400")
        
        # Make it modal
        analysis_window.transient(self.root)
        analysis_window.grab_set()
        
        # Center the window
        analysis_window.update_idletasks()
        x = (analysis_window.winfo_screenwidth() // 2) - (600 // 2)
        y = (analysis_window.winfo_screenheight() // 2) - (400 // 2)
        analysis_window.geometry(f"600x400+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(analysis_window, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # Add progress bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill="x", pady=(0, 10))
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
        progress_bar.pack(side="left", fill="x", expand=True)
        
        # Add status label
        status_label = ttk.Label(progress_frame, text="Starting analysis...")
        status_label.pack(side="right", padx=5)
        
        # Add text widget for results
        text_widget = tk.Text(main_frame, wrap="word", height=15)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def update_progress(value, status):
            progress_var.set(value)
            status_label.config(text=status)
            analysis_window.update()
        
        def run_analysis():
            try:
                # Basic port scan
                update_progress(10, "Scanning common ports...")
                text_widget.insert("end", "=== Port Scan Results ===\n")
                
                common_ports = [80, 443, 554, 8080, 8000, 37777, 37778, 37779]
                for port in common_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex((base_ip, port))
                        if result == 0:
                            text_widget.insert("end", f"Port {port}: Open\n")
                        sock.close()
                    except:
                        pass
                
                # HTTP/HTTPS analysis
                update_progress(30, "Analyzing web services...")
                text_widget.insert("end", "\n=== Web Service Analysis ===\n")
                
                for protocol in ['http', 'https']:
                    try:
                        url = f"{protocol}://{base_ip}"
                        response = requests.get(url, timeout=2)
                        text_widget.insert("end", f"\n{protocol.upper()} Service:\n")
                        text_widget.insert("end", f"Status Code: {response.status_code}\n")
                        text_widget.insert("end", f"Server: {response.headers.get('Server', 'Unknown')}\n")
                    except:
                        pass
                
                # RTSP analysis
                update_progress(50, "Checking RTSP services...")
                text_widget.insert("end", "\n=== RTSP Analysis ===\n")
                
                rtsp_ports = [554, 8554]
                for port in rtsp_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex((base_ip, port))
                        if result == 0:
                            text_widget.insert("end", f"RTSP port {port}: Open\n")
                        sock.close()
                    except:
                        pass
                
                # ONVIF analysis
                update_progress(70, "Checking ONVIF services...")
                text_widget.insert("end", "\n=== ONVIF Analysis ===\n")
                
                try:
                    url = f"http://{base_ip}/onvif/device_service"
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        text_widget.insert("end", "ONVIF service detected\n")
                except:
                    pass
                
                # Final analysis
                update_progress(90, "Finalizing analysis...")
                text_widget.insert("end", "\n=== Summary ===\n")
                text_widget.insert("end", f"IP Address: {base_ip}\n")
                text_widget.insert("end", f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                update_progress(100, "Analysis complete!")
                
            except Exception as e:
                text_widget.insert("end", f"\nError during analysis: {str(e)}")
                update_progress(100, "Analysis failed!")
            
            # Make text read-only
            text_widget.configure(state="disabled")
        
        # Start analysis in a separate thread
        threading.Thread(target=run_analysis, daemon=True).start()
        
        # Add close button
        close_button = ttk.Button(analysis_window, text="Close", command=analysis_window.destroy)
        close_button.pack(pady=10)
        
        # Bind ESC key to close
        analysis_window.bind('<Escape>', lambda e: analysis_window.destroy())


def runmaingui():
    root = tk.Tk()
    app = MainGUI(root)
    def on_closing():
        app.cleanup_on_close()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()