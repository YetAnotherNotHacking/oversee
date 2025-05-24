import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import time
import threading
from datetime import datetime
from PIL import Image, ImageTk
from gui.rendermatrix import create_matrix_view as render_matrix
from utility.ip2loc import get_geolocation
from utility.iplist import get_ip_range
import os
import gui
import settings

ip_list_file = settings.ip_list_file

class MainGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SilverFlag | OVERSEE v{settings.overseeversion}")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Apply logo (not chatgpt generated I swaer)
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
        
        # Sample data for demonstration
        self.list_items = [
            {"id": 1, "name": "Camera Alpha", "location": "Building A", "status": "Active", "ip": "192.168.1.10"},
            {"id": 2, "name": "Camera Beta", "location": "Building B", "status": "Inactive", "ip": "192.168.1.11"},
            {"id": 3, "name": "Camera Gamma", "location": "Building C", "status": "Active", "ip": "192.168.1.12"},
        ]
        
        self.group_data = [
            {"id": 101, "name": "Security Cameras", "count": 15, "location": "Main Campus", "status": "Operational"},
            {"id": 102, "name": "Access Control", "count": 8, "location": "North Wing", "status": "Maintenance"},
            {"id": 103, "name": "Fire Safety", "count": 23, "location": "All Buildings", "status": "Active"},
        ]
        
        self.setup_gui()
        self.update_system_info()
        
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
        messagebox.showinfo("Settings", "Preferences dialog would open here")
    
    def open_network_config(self):
        messagebox.showinfo("Settings", "Network configuration dialog would open here")
    
    def show_about(self):
        messagebox.showinfo("About", "Main Application v1.0\nA comprehensive GUI application")

    def open_preferences(self):
        # Create preferences window
        prefs_window = tk.Toplevel(self.root)
        prefs_window.title("Preferences")
        prefs_window.geometry("400x300")
        prefs_window.resizable(False, False)
        
        # Make it modal
        prefs_window.transient(self.root)
        prefs_window.grab_set()
        
        # Center the window
        prefs_window.update_idletasks()
        x = (prefs_window.winfo_screenwidth() // 2) - (400 // 2)
        y = (prefs_window.winfo_screenheight() // 2) - (300 // 2)
        prefs_window.geometry(f"400x300+{x}+{y}")
        
        # Create notebook for tabs
        notebook = ttk.Notebook(prefs_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # General tab
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        
        # IP List File setting
        ttk.Label(general_frame, text="IP List File:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        
        ip_file_frame = ttk.Frame(general_frame)
        ip_file_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=5)
        ip_file_frame.grid_columnconfigure(0, weight=1)
        
        self.ip_file_var = tk.StringVar(value=getattr(settings, 'ip_list_file', ''))
        ip_file_entry = ttk.Entry(ip_file_frame, textvariable=self.ip_file_var, width=40)
        ip_file_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        
        def browse_ip_file():
            filename = filedialog.askopenfilename(
                title="Select IP List File",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                self.ip_file_var.set(filename)
        
        ttk.Button(ip_file_frame, text="Browse", command=browse_ip_file).grid(row=0, column=1)
        
        # Camera Settings tab
        camera_frame = ttk.Frame(notebook)
        notebook.add(camera_frame, text="Camera")
        
        ttk.Label(camera_frame, text="Default Camera URL Format:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.camera_url_var = tk.StringVar(value="http://{ip}/video")
        ttk.Entry(camera_frame, textvariable=self.camera_url_var, width=40).grid(row=1, column=0, sticky='ew', padx=10, pady=5)
        
        ttk.Label(camera_frame, text="Preview Frame Rate (FPS):").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.fps_var = tk.StringVar(value="10")
        ttk.Entry(camera_frame, textvariable=self.fps_var, width=10).grid(row=3, column=0, sticky='w', padx=10, pady=5)
        
        # Buttons frame
        button_frame = ttk.Frame(prefs_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def save_preferences():
            try:
                # Save settings (you'll need to implement settings saving)
                settings.ip_list_file = self.ip_file_var.get()
                # Add other settings as needed
                
                messagebox.showinfo("Success", "Preferences saved successfully")
                prefs_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save preferences: {str(e)}")
        
        def cancel_preferences():
            prefs_window.destroy()
    
        ttk.Button(button_frame, text="Save", command=save_preferences).pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=cancel_preferences).pack(side='right')
        
    def create_map_view(self):
        map_frame = ttk.Frame(self.notebook)
        self.notebook.add(map_frame, text="Map View")
        
        map_frame.grid_rowconfigure(0, weight=1)
        map_frame.grid_columnconfigure(0, weight=1)
        
        # Create scrollable frame for groups
        canvas = tk.Canvas(map_frame, bg='white')
        scrollbar = ttk.Scrollbar(map_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Add group items
        for i, group in enumerate(self.group_data):
            group_frame = ttk.LabelFrame(scrollable_frame, text=f"Group {group['id']}", padding=10)
            group_frame.grid(row=i, column=0, sticky="ew", padx=5, pady=5)
            
            # Group title
            title_label = ttk.Label(group_frame, text=group['name'], font=('Arial', 14, 'bold'))
            title_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
            
            # Group details
            details_text = f"Items: {group['count']} | Location: {group['location']} | Status: {group['status']}"
            details_label = ttk.Label(group_frame, text=details_text, font=('Arial', 10))
            details_label.grid(row=1, column=0, sticky="w")
            
        scrollable_frame.grid_columnconfigure(0, weight=1)
        
    def create_matrix_view(self):
        matrix_frame = ttk.Frame(self.notebook)
        self.notebook.add(matrix_frame, text="Matrix View")
        
        # Configure frame for resizing
        matrix_frame.grid_rowconfigure(0, weight=1)
        matrix_frame.grid_columnconfigure(0, weight=1)
        
        # Create canvas for matrix display
        self.matrix_canvas = tk.Canvas(matrix_frame, bg='black')
        self.matrix_canvas.grid(row=0, column=0, sticky="nsew")
        
        # Update matrix view periodically
        self.update_matrix_display()
            
    def update_matrix_display(self):
        """Update the matrix display with current camera streams (non-blocking version)"""
        # Get canvas dimensions first (outside try block)
        canvas_width = self.matrix_canvas.winfo_width()
        canvas_height = self.matrix_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # Canvas not ready yet, try again later
            self.root.after(100, self.update_matrix_display)
            return
        
        try:
            # Calculate cell dimensions (smaller to prevent memory issues)
            cell_width = min(320, canvas_width // 4)
            cell_height = min(240, canvas_height // 3)
            
            # Create matrix image (this is now non-blocking)
            matrix_image = render_matrix(ip_range_start=1, ip_range_end=50, 
                                        max_cell_width=cell_width, max_cell_height=cell_height)
            
            if matrix_image is not None:
                # Import cv2 here to avoid issues if not available
                import cv2
                
                # Convert CV2 image to PIL then to PhotoImage
                matrix_rgb = cv2.cvtColor(matrix_image, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(matrix_rgb)
                
                # Scale image to fit canvas
                img_width, img_height = pil_image.size
                scale_x = canvas_width / img_width
                scale_y = canvas_height / img_height
                scale = min(scale_x, scale_y, 1.0)  # Don't scale up
                
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                
                # Use LANCZOS for better quality, but catch errors
                try:
                    pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                except AttributeError:
                    # Fallback for older PIL versions
                    pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
                
                # Keep reference to prevent garbage collection
                self.matrix_photo = ImageTk.PhotoImage(pil_image)
                
                # Clear canvas and display image
                self.matrix_canvas.delete("all")
                self.matrix_canvas.create_image(canvas_width//2, canvas_height//2, 
                                                image=self.matrix_photo, anchor="center")
            else:
                # No active streams - show status message
                self.matrix_canvas.delete("all")
                self.matrix_canvas.create_text(canvas_width//2, canvas_height//2, 
                                                text="Initializing camera connections...\nPlease wait...", 
                                                fill="white", font=('Arial', 16), justify="center")
        
        except ImportError as e:
            # Handle missing cv2 or other import errors
            self.matrix_canvas.delete("all")
            self.matrix_canvas.create_text(canvas_width//2, canvas_height//2, 
                                            text=f"Matrix renderer not available\nError: {e}", 
                                            fill="white", font=('Arial', 12), justify="center")
        except Exception as e:
            # Handle any other errors gracefully
            print(f"Matrix display error: {e}")
            self.matrix_canvas.delete("all")
            self.matrix_canvas.create_text(canvas_width//2, canvas_height//2, 
                                            text=f"Display error: {str(e)[:50]}...", 
                                            fill="red", font=('Arial', 12), justify="center")
        
        # Schedule next update (increased to 2 seconds to reduce load)
        self.root.after(2000, self.update_matrix_display)
        
    def cleanup_on_close(self):
        """Clean up resources when closing the application"""
        try:
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
        
        # Properties frame
        self.properties_frame = ttk.LabelFrame(right_panel, text="Properties", padding=10)
        self.properties_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Properties labels
        self.prop_name = ttk.Label(self.properties_frame, text="IP Address: Select a camera", font=('Arial', 10, 'bold'))
        self.prop_name.grid(row=0, column=0, sticky="w", pady=2)
        
        self.prop_location = ttk.Label(self.properties_frame, text="Location: -")
        self.prop_location.grid(row=1, column=0, sticky="w", pady=2)
        
        self.prop_status = ttk.Label(self.properties_frame, text="Status: -")
        self.prop_status.grid(row=2, column=0, sticky="w", pady=2)
        
        self.prop_resolution = ttk.Label(self.properties_frame, text="Resolution: -")
        self.prop_resolution.grid(row=3, column=0, sticky="w", pady=2)
        
        # Control buttons
        button_frame = ttk.Frame(right_panel)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        
        self.refresh_btn = ttk.Button(button_frame, text="Refresh List", command=self.refresh_ip_list)
        self.refresh_btn.pack(side='left', padx=(0, 5))
        
        self.test_connection_btn = ttk.Button(button_frame, text="Test Connection", command=self.test_selected_camera)
        self.test_connection_btn.pack(side='left')

    def check_camera_status(self, item_id, ip):
        """Check if camera is accessible and update status"""
        try:
            # Try to connect to camera
            cap = cv2.VideoCapture(ip)  # Adjust URL format as needed
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    # Camera is working
                    height, width = frame.shape[:2]
                    resolution = f"{width}x{height}"
                    
                    self.camera_data[item_id].update({
                        'status': 'Online',
                        'resolution': resolution,
                        'last_check': time.time()
                    })
                    
                    # Update treeview in main thread
                    self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Online"))
                else:
                    self.camera_data[item_id]['status'] = 'No Signal'
                    self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "No Signal"))
            else:
                self.camera_data[item_id]['status'] = 'Offline'
                self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Offline"))
                
            cap.release()
            
        except Exception as e:
            self.camera_data[item_id]['status'] = 'Error'
            self.tree.after(0, lambda: self.update_tree_item(item_id, ip, "Error"))
        
        # Get location information
        try:
            location = get_geolocation(ip)
            self.camera_data[item_id]['location'] = location
        except Exception as e:
            self.camera_data[item_id]['location'] = "Location unavailable"

    def load_ip_addresses(self):
        """Load IP addresses from file and populate the treeview"""
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Get IP addresses from file (loading first 100 for performance)
            ip_list = get_ip_range(settings.ip_list_file, 1, 100)
            
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
                
                # Start background thread to check camera status
                threading.Thread(target=self.check_camera_status, 
                            args=(item_id, ip), daemon=True).start()
                
        except Exception as e:
            print(f"Error loading IP addresses: {e}")

    def update_tree_item(self, item_id, ip, status):
        """Update treeview item with new status"""
        try:
            self.tree.item(item_id, values=(ip, status))
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
        
        # Start camera preview if online
        if camera_info['status'] == 'Online':
            self.start_camera_preview(ip)
        else:
            self.image_label.config(image='', text=f"Camera {camera_info['status']}")

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
            cap = cv2.VideoCapture(f"http://{ip}/video")  # Adjust URL format as needed
            
            while self.preview_active and cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    # Resize frame for display
                    frame = cv2.resize(frame, (320, 240))
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Convert to PhotoImage
                    img = Image.fromarray(frame_rgb)
                    photo = ImageTk.PhotoImage(img)
                    
                    # Update label in main thread
                    self.image_label.after(0, lambda p=photo: self.update_preview_image(p))
                    
                    time.sleep(0.1)  # Limit frame rate
                else:
                    break
                    
            cap.release()
            
        except Exception as e:
            self.image_label.after(0, lambda: self.image_label.config(
                image='', text="Preview unavailable"
            ))

    def update_preview_image(self, photo):
        """Update preview image in main thread"""
        try:
            self.image_label.config(image=photo, text='')
            self.image_label.image = photo  # Keep a reference to prevent garbage collection
        except tk.TclError:
            pass

    def refresh_ip_list(self):
        """Refresh the IP address list"""
        self.preview_active = False  # Stop current preview
        self.load_ip_addresses()

    def test_selected_camera(self):
        """Test connection to selected camera"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        if item_id not in self.camera_data:
            return
        
        ip = self.camera_data[item_id]['ip']
        
        # Update status to "Testing..."
        self.tree.item(item_id, values=(ip, "Testing..."))
        
        # Start test in background thread
        threading.Thread(target=self.check_camera_status, 
                    args=(item_id, ip), daemon=True).start()
        
        # Three filler buttons
        ttk.Button(buttons_frame, text="Button 1", command=self.placeholder_action).grid(row=0, column=0, padx=2, pady=5, sticky="ew")
        ttk.Button(buttons_frame, text="Button 2", command=self.placeholder_action).grid(row=0, column=1, padx=2, pady=5, sticky="ew")
        ttk.Button(buttons_frame, text="Button 3", command=self.placeholder_action).grid(row=0, column=2, padx=2, pady=5, sticky="ew")
        
    def create_status_bar(self):
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.grid_columnconfigure(4, weight=1)  # Make time label expand
        
        # System info labels
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
    
    # def on_item_select(self, event):
    #     selection = self.tree.selection()
    #     if selection:
    #         item_id = self.tree.item(selection[0])['text']
    #         # Find the item data
    #         selected_item = next((item for item in self.list_items if str(item['id']) == item_id), None)
            
    #         if selected_item:
    #             # Update properties display
    #             self.prop_name.config(text=f"Name: {selected_item['name']}")
    #             self.prop_location.config(text=f"Location: {selected_item['location']}")
    #             self.prop_status.config(text=f"Status: {selected_item['status']}")
                
    #             # Update image placeholder
    #             self.image_label.config(text=f"Image for {selected_item['name']}\n(ID: {item_id})")
    
    def placeholder_action(self):
        messagebox.showinfo("Action", "This is a placeholder button action!")


def runmaingui():
    root = tk.Tk()
    app = MainGUI(root)
    def on_closing():
        app.cleanup_on_close()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()