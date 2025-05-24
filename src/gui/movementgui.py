import tkinter as tk
from tkinter import ttk

class MovementControlWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Camera Movement Controls")
        self.window.geometry("300x400")
        
        # Create movement controls
        control_frame = ttk.Frame(self.window, padding=10)
        control_frame.grid(row=0, column=0, sticky="nsew")
        
        # Movement buttons
        ttk.Button(control_frame, text="↑", width=5).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(control_frame, text="←", width=5).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(control_frame, text="→", width=5).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(control_frame, text="↓", width=5).grid(row=2, column=1, padx=5, pady=5)
        
        # Scan controls
        ttk.Label(control_frame, text="Scan Controls").grid(row=3, column=0, columnspan=3, pady=10)
        ttk.Button(control_frame, text="Scan ↑", width=10).grid(row=4, column=0, columnspan=3, padx=5, pady=5)
        ttk.Button(control_frame, text="Scan ↓", width=10).grid(row=5, column=0, columnspan=3, padx=5, pady=5)
        ttk.Button(control_frame, text="Scan ←", width=10).grid(row=6, column=0, columnspan=3, padx=5, pady=5)
        ttk.Button(control_frame, text="Scan →", width=10).grid(row=7, column=0, columnspan=3, padx=5, pady=5)
        
        # Zoom controls
        ttk.Label(control_frame, text="Zoom Controls").grid(row=8, column=0, columnspan=3, pady=10)
        ttk.Button(control_frame, text="Zoom In", width=10).grid(row=9, column=0, columnspan=3, padx=5, pady=5)
        ttk.Button(control_frame, text="Zoom Out", width=10).grid(row=10, column=0, columnspan=3, padx=5, pady=5)
        
        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()
        
        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (300 // 2)
        y = (self.window.winfo_screenheight() // 2) - (400 // 2)
        self.window.geometry(f"300x400+{x}+{y}") 