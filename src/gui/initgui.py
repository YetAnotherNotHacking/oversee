import tkinter as tk
from tkinter import ttk
import threading
import time

class StartUpMenu:
    def __init__(self):
        self.loadup_status = "Initializing..."
        self.loadup_percentage = 0.0
        self.window = None
        self.running = False
        self.thread = None
        
    def create_loading_window(self):
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        window_width = 400
        window_height = 150
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.window.attributes('-topmost', True)
        self.window.resizable(False, False)
        self.window.configure(bg='#2c3e50')
        main_frame = tk.Frame(self.window, bg='#2c3e50', padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)
        title_label = tk.Label(
            main_frame, 
            text="Loading...", 
            font=('Arial', 16, 'bold'),
            fg='white',
            bg='#2c3e50'
        )
        title_label.pack(pady=(0, 15))
        self.status_label = tk.Label(
            main_frame,
            text=self.loadup_status,
            font=('Arial', 10),
            fg='#ecf0f1',
            bg='#2c3e50',
            wraplength=350
        )
        self.status_label.pack(pady=(0, 10))
        self.progress_bar = ttk.Progressbar(
            main_frame,
            length=350,
            mode='determinate',
            maximum=100
        )
        self.progress_bar.pack(pady=(0, 10))
        self.percentage_label = tk.Label(
            main_frame,
            text="0%",
            font=('Arial', 10),
            fg='#ecf0f1',
            bg='#2c3e50'
        )
        self.percentage_label.pack()
        
    def update_display(self):
        if self.window and self.running:
            try:
                self.status_label.config(text=self.loadup_status)
                progress_value = max(0, min(100, self.loadup_percentage))
                self.progress_bar['value'] = progress_value
                self.percentage_label.config(text=f"{progress_value:.1f}%")
                self.window.after(50, self.update_display)
                
            except tk.TclError:
                pass
    
    def window_loop(self):
        self.create_loading_window()
        self.running = True
        self.window.after(50, self.update_display)
        
        try:
            self.window.mainloop()
        except:
            pass
        finally:
            self.running = False
    
    def show_loading_window(self):
        if not self.running:
            self.thread = threading.Thread(target=self.window_loop, daemon=True)
            self.thread.start()
    
    def overandout(self):
        self.running = False
        if self.window:
            try:
                self.window.quit()
                self.window.destroy()
            except:
                pass
            self.window = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)