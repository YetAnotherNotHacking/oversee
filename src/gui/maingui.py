import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import time
from datetime import datetime
from PIL import Image, ImageTk
from gui.rendermatrix import create_matrix_view as render_matrix
import os
import gui
import settings

ip_list_file = settings.ip_list_file

class MainGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SilverFlag | OVERSEE {settings.overseeversion}")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Apply logo (not chatgpt generated I swaer)
        ico = Image.open('assets/logo.png')
        photo = ImageTk.PhotoImage(ico)
        self.root.wm_iconphoto(False, photo)

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
                                        cell_width=cell_width, cell_height=cell_height)
            
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
        self.tree.heading('Name', text='Name')
        self.tree.heading('Status', text='Status')
        
        self.tree.column('#0', width=50)
        self.tree.column('Name', width=150)
        self.tree.column('Status', width=80)
        
        # Add items to treeview
        for item in self.list_items:
            self.tree.insert('', 'end', text=str(item['id']), 
                           values=(item['name'], item['status']))
        
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
        self.image_frame = ttk.LabelFrame(right_panel, text="Camera View", padding=10)
        self.image_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Placeholder for image
        self.image_label = ttk.Label(self.image_frame, text="No image selected", 
                                   background='lightgray', width=40, anchor='center')
        self.image_label.grid(row=0, column=0, pady=20)
        
        # Properties frame
        self.properties_frame = ttk.LabelFrame(right_panel, text="Properties", padding=10)
        self.properties_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Properties labels
        self.prop_name = ttk.Label(self.properties_frame, text="Name: Select an item", font=('Arial', 10, 'bold'))
        self.prop_name.grid(row=0, column=0, sticky="w", pady=2)
        
        self.prop_location = ttk.Label(self.properties_frame, text="Location: -")
        self.prop_location.grid(row=1, column=0, sticky="w", pady=2)
        
        self.prop_ip = ttk.Label(self.properties_frame, text="IP Address: -")
        self.prop_ip.grid(row=2, column=0, sticky="w", pady=2)
        
        self.prop_status = ttk.Label(self.properties_frame, text="Status: -")
        self.prop_status.grid(row=3, column=0, sticky="w", pady=2)
        
        # Buttons frame
        buttons_frame = ttk.Frame(right_panel)
        buttons_frame.grid(row=2, column=0, sticky="ew")
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
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
    
    def on_item_select(self, event):
        selection = self.tree.selection()
        if selection:
            item_id = self.tree.item(selection[0])['text']
            # Find the item data
            selected_item = next((item for item in self.list_items if str(item['id']) == item_id), None)
            
            if selected_item:
                # Update properties display
                self.prop_name.config(text=f"Name: {selected_item['name']}")
                self.prop_location.config(text=f"Location: {selected_item['location']}")
                self.prop_ip.config(text=f"IP Address: {selected_item['ip']}")
                self.prop_status.config(text=f"Status: {selected_item['status']}")
                
                # Update image placeholder
                self.image_label.config(text=f"Image for {selected_item['name']}\n(ID: {item_id})")
    
    def placeholder_action(self):
        messagebox.showinfo("Action", "This is a placeholder button action!")
    
    def open_preferences(self):
        messagebox.showinfo("Settings", "Preferences dialog would open here")
    
    def open_network_config(self):
        messagebox.showinfo("Settings", "Network configuration dialog would open here")
    
    def show_about(self):
        messagebox.showinfo("About", "Main Application v1.0\nA comprehensive GUI application")

def runmaingui():
    root = tk.Tk()
    app = MainGUI(root)
    
    # Handle window close event properly
    def on_closing():
        app.cleanup_on_close()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()