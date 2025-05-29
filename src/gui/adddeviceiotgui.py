import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import sqlite3
import os

class AddDeviceIoTDialog:
    def __init__(self, parent, device_types, on_device_added=None):
        self.parent = parent
        self.device_types = device_types
        self.on_device_added = on_device_added
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New IoT Device")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Configure grid
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)
        
        # Create main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Add New IoT Device",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Network Information Section
        network_frame = ttk.LabelFrame(main_frame, text="Network Information", padding="10")
        network_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        network_frame.grid_columnconfigure(1, weight=1)
        
        # IP Address
        ttk.Label(network_frame, text="IP Address:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ttk.Entry(network_frame)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Port
        ttk.Label(network_frame, text="Port:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.port_entry = ttk.Entry(network_frame)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.port_entry.insert(0, "80")  # Default port
        
        # Device Information Section
        device_frame = ttk.LabelFrame(main_frame, text="Device Information", padding="10")
        device_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        device_frame.grid_columnconfigure(1, weight=1)
        
        # Device Type
        ttk.Label(device_frame, text="Device Type:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.device_type_var = tk.StringVar()
        self.device_type_combo = ttk.Combobox(
            device_frame,
            textvariable=self.device_type_var,
            state="readonly",
            values=device_types
        )
        self.device_type_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Device Name
        ttk.Label(device_frame, text="Device Name:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.name_entry = ttk.Entry(device_frame)
        self.name_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # Location Information Section
        location_frame = ttk.LabelFrame(main_frame, text="Location Information", padding="10")
        location_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        location_frame.grid_columnconfigure(1, weight=1)
        
        # Location
        ttk.Label(location_frame, text="Location:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.location_entry = ttk.Entry(location_frame)
        self.location_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Additional Information Section
        info_frame = ttk.LabelFrame(main_frame, text="Additional Information", padding="10")
        info_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_rowconfigure(0, weight=1)
        
        # Notes
        ttk.Label(info_frame, text="Notes:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.notes_text = tk.Text(info_frame, height=6, width=40)
        self.notes_text.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Add scrollbar to notes
        notes_scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.notes_text.yview)
        notes_scrollbar.grid(row=1, column=1, sticky="ns")
        self.notes_text.configure(yscrollcommand=notes_scrollbar.set)
        
        # Button Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        # Save Button
        save_button = ttk.Button(
            button_frame,
            text="Save Device",
            command=self.save_device,
            style='Accent.TButton'
        )
        save_button.pack(side="left", padx=5)
        
        # Cancel Button
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        )
        cancel_button.pack(side="left", padx=5)
        
        # Configure style for accent button
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
        
        # Center the dialog
        self.center_dialog()
        
        # Bind Enter key to save
        self.dialog.bind('<Return>', lambda e: self.save_device())
        # Bind Escape key to close
        self.dialog.bind('<Escape>', lambda e: self.dialog.destroy())
        
    def center_dialog(self):
        """Center the dialog on the screen"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
    def save_device(self):
        """Save the device information to the database"""
        try:
            # Get values
            ip = self.ip_entry.get().strip()
            port = self.port_entry.get().strip()
            device_type = self.device_type_var.get()
            device_name = self.name_entry.get().strip()
            location = self.location_entry.get().strip()
            notes = self.notes_text.get("1.0", tk.END).strip()
            
            # Validate required fields
            if not all([ip, port, device_type]):
                messagebox.showerror("Error", "Please fill in all required fields (IP, Port, and Device Type)")
                return
            
            try:
                port = int(port)
                if not (0 <= port <= 65535):
                    raise ValueError("Port must be between 0 and 65535")
            except ValueError:
                messagebox.showerror("Error", "Port must be a valid number between 0 and 65535")
                return
            
            # Save to database
            db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'iot_devices.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO devices (
                    ip, port, device_type, device_name, location,
                    status, last_seen, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ip, port, device_type, device_name, location,
                "Unknown", datetime.now(), notes
            ))
            
            conn.commit()
            conn.close()
            
            # Notify parent if callback provided
            if self.on_device_added:
                self.on_device_added(
                    f"{ip}:{port}",
                    device_type,
                    "Unknown",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            
            # Close dialog
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add device: {str(e)}") 