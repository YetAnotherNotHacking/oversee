import os
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import threading

# Add src directory to path
sys.path.append(str(Path(__file__).parent / 'src'))

from gui.maingui import runmaingui
from initdata.getiplistcoordinates import process_ip_list

def show_loading_window():
    """Show a loading window while initializing data"""
    root = tk.Tk()
    root.title("Initializing...")
    root.geometry("400x150")
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (400 // 2)
    y = (root.winfo_screenheight() // 2) - (150 // 2)
    root.geometry(f"400x150+{x}+{y}")
    
    # Create loading frame
    frame = ttk.Frame(root, padding="20")
    frame.pack(fill="both", expand=True)
    
    # Add loading label
    label = ttk.Label(frame, text="Initializing IP coordinates...")
    label.pack(pady=10)
    
    # Add progress bar
    progress = ttk.Progressbar(frame, mode='indeterminate')
    progress.pack(fill="x", pady=10)
    progress.start()
    
    # Add status label
    status = ttk.Label(frame, text="This may take a few minutes...")
    status.pack(pady=10)
    
    return root, status

def initialize_data():
    """Initialize all required data"""
    # Show loading window
    root, status = show_loading_window()
    
    def init_thread():
        try:
            # Process IP coordinates
            process_ip_list()
            
            # Update status
            root.after(0, lambda: status.config(text="Initialization complete!"))
            root.after(1000, root.destroy)  # Close after 1 second
        except Exception as e:
            root.after(0, lambda: status.config(text=f"Error: {str(e)}"))
            root.after(3000, root.destroy)  # Close after 3 seconds on error
    
    # Start initialization in a separate thread
    threading.Thread(target=init_thread, daemon=True).start()
    
    # Run the loading window
    root.mainloop()

if __name__ == "__main__":
    # Initialize data first
    initialize_data()
    
    # Then run the main GUI
    runmaingui() 