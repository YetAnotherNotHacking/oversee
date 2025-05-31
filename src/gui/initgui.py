import tkinter as tk
from tkinter import ttk
import threading
import time
import os
import sys

class StartUpMenu:
    def __init__(self):
        self.loadup_status = "Initializing..."
        self.loadup_percentage = 0.0
        self.scraping_status = "Waiting..."
        self.scraping_percentage = 0.0
        self.window = None
        self.running = False
        self.completion_callback = None
        
    def create_loading_window(self):
        self.window = tk.Tk()
        self.window.title("Loading...")
        
        window_width = 450
        window_height = 350
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.window.focus_force()
        
        self.window.resizable(False, False)
        self.window.configure(bg='black')
        
        style = ttk.Style()
        style.configure("TProgressbar", 
                       troughcolor='black',
                       background='#2c3e50',
                       bordercolor='black',
                       lightcolor='black',
                       darkcolor='black')
        
        self.window.after(100, lambda: self.window.overrideredirect(True))
        
        main_frame = tk.Frame(self.window, bg='black', padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)
        
        title_label = tk.Label(
            main_frame, 
            text="Loading Application...", 
            font=('Arial', 16, 'bold'),
            fg='white',
            bg='black'
        )
        title_label.pack(pady=(0, 15))
        
        # Main progress section
        main_progress_frame = tk.Frame(main_frame, bg='black')
        main_progress_frame.pack(fill='x', pady=(0, 15))
        
        tk.Label(
            main_progress_frame,
            text="Overall Progress:",
            font=('Arial', 9, 'bold'),
            fg='#ecf0f1',
            bg='black'
        ).pack(anchor='w')
        
        self.status_label = tk.Label(
            main_progress_frame,
            text=self.loadup_status,
            font=('Arial', 10),
            fg='#ecf0f1',
            bg='black',
            wraplength=400
        )
        self.status_label.pack(pady=(2, 5), anchor='w')
        
        self.progress_bar = ttk.Progressbar(
            main_progress_frame,
            length=400,
            mode='determinate',
            maximum=100,
            style="TProgressbar"
        )
        self.progress_bar.pack(pady=(0, 5))
        
        self.percentage_label = tk.Label(
            main_progress_frame,
            text="0%",
            font=('Arial', 10),
            fg='#ecf0f1',
            bg='black'
        )
        self.percentage_label.pack(anchor='w')
        
        # Scraping progress section
        scraping_progress_frame = tk.Frame(main_frame, bg='black')
        scraping_progress_frame.pack(fill='x', pady=(0, 30))  # Increased padding
        
        tk.Label(
            scraping_progress_frame,
            text="Web Scraping Progress:",
            font=('Arial', 9, 'bold'),
            fg='#ecf0f1',
            bg='black'
        ).pack(anchor='w')
        
        self.scraping_status_label = tk.Label(
            scraping_progress_frame,
            text=self.scraping_status,
            font=('Arial', 10),
            fg='#bdc3c7',
            bg='black',
            wraplength=400
        )
        self.scraping_status_label.pack(pady=(2, 5), anchor='w')
        
        self.scraping_progress_bar = ttk.Progressbar(
            scraping_progress_frame,
            length=400,
            mode='determinate',
            maximum=100,
            style="TProgressbar"
        )
        self.scraping_progress_bar.pack(pady=(0, 5))
        
        self.scraping_percentage_label = tk.Label(
            scraping_progress_frame,
            text="0%",
            font=('Arial', 10),
            fg='#bdc3c7',
            bg='black'
        )
        self.scraping_percentage_label.pack(anchor='w')
        
        # Add skip button with more padding and larger size
        skip_button = tk.Button(
            main_frame,
            text="Skip IP2LOC Loading",
            command=self._skip_loading,
            bg='#2c3e50',
            fg='white',
            font=('Arial', 14, 'bold'),  # Increased font size further
            relief='flat',
            padx=30,  # Increased horizontal padding
            pady=15,  # Increased vertical padding
            cursor='hand2',
            activebackground='#34495e',  # Darker color when pressed
            activeforeground='white'
        )
        skip_button.pack(pady=(30, 0))  # Increased top padding
        
        # Force window update and visibility
        self.window.update_idletasks()
        self.window.deiconify()
        
        # Additional visibility forcing for macOS
        self.window.after(200, self._ensure_visible)
        
    def _ensure_visible(self):
        """Ensure window is visible - especially important on macOS"""
        if self.window and self.running:
            try:
                self.window.lift()
                self.window.focus_force()
                self.window.attributes('-topmost', True)
                # Re-center after overrideredirect
                self.window.update_idletasks()
                window_width = 450
                window_height = 350
                screen_width = self.window.winfo_screenwidth()
                screen_height = self.window.winfo_screenheight()
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            except tk.TclError:
                pass
        
    def update_status(self, status, percentage):
        """Update main status - this method can be called from any thread"""
        self.loadup_status = status
        self.loadup_percentage = percentage
        
        # Schedule GUI update on main thread
        if self.window and self.running:
            self.window.after(0, self._update_main_gui)
    
    def update_scraping_status(self, status, percentage):
        """Update scraping status - this method can be called from any thread"""
        self.scraping_status = status
        self.scraping_percentage = percentage
        
        # Schedule GUI update on main thread
        if self.window and self.running:
            self.window.after(0, self._update_scraping_gui)
    
    def _update_main_gui(self):
        """Update main GUI elements - runs on main thread"""
        if self.window and self.running:
            try:
                self.status_label.config(text=self.loadup_status)
                progress_value = max(0, min(100, self.loadup_percentage))
                self.progress_bar['value'] = progress_value
                self.percentage_label.config(text=f"{progress_value:.1f}%")
                self.window.update_idletasks()
            except tk.TclError:
                pass
    
    def _update_scraping_gui(self):
        """Update scraping GUI elements - runs on main thread"""
        if self.window and self.running:
            try:
                self.scraping_status_label.config(text=self.scraping_status)
                progress_value = max(0, min(100, self.scraping_percentage))
                self.scraping_progress_bar['value'] = progress_value
                self.scraping_percentage_label.config(text=f"{progress_value:.1f}%")
                self.window.update_idletasks()
            except tk.TclError:
                pass
    
    def start_with_tasks(self, task_function, completion_callback=None):
        """Start the GUI and run tasks in background"""
        self.completion_callback = completion_callback
        self.create_loading_window()
        self.running = True
        
        print("Loading window created, starting background tasks...")
        
        # Start the background tasks
        task_thread = threading.Thread(target=self._run_tasks, args=(task_function,), daemon=True)
        task_thread.start()
        
        print("Background tasks started, entering main loop...")
        
        # Start the GUI main loop (this will block until window is closed)
        try:
            self.window.mainloop()
        except Exception as e:
            print(f"GUI main loop error: {e}")
        finally:
            self.running = False
            print("GUI main loop ended")
    
    def _run_tasks(self, task_function):
        """Run the task function in background thread"""
        try:
            print("Running initialization tasks...")
            task_function(self)
            print("Initialization tasks completed")
        except Exception as e:
            print(f"Error during initialization: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Schedule completion on main thread
            if self.window and self.running:
                self.window.after(100, self._complete_loading)
    
    def _complete_loading(self):
        """Complete the loading process"""
        print("Completing loading process...")
        if self.completion_callback:
            try:
                self.completion_callback()
            except Exception as e:
                print(f"Completion callback error: {e}")
        self.overandout()
    
    def overandout(self):
        """Close the loading window"""
        print("Closing loading window...")
        self.running = False
        if self.window:
            try:
                self.window.quit()
                self.window.destroy()
            except Exception as e:
                print(f"Error closing window: {e}")
            self.window = None
    
    def _skip_loading(self):
        """Skip the IP2LOC loading process"""
        print("Skipping IP2LOC loading...")
        self._complete_loading()

def init_gui():
    """Initialize the GUI"""
    try:
        # Create data directory if it doesn't exist
        os.makedirs(settings.data_dir, exist_ok=True)
        
        # Initialize database
        init_database()
        
        # Start GUI
        from gui.maingui import runmaingui
        runmaingui()
        
    except Exception as e:
        print(f"Error during GUI initialization: {e}")
        sys.exit(1)