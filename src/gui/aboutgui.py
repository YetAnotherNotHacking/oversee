import tkinter as tk
from tkinter import ttk
import webbrowser
from PIL import Image, ImageTk
import requests
from io import BytesIO

class AboutGUI:
    def __init__(self, parent):
        # Create a new window
        self.window = tk.Toplevel(parent)
        self.window.title("About Oversee")
        self.window.geometry("400x300")
        
        # Make it non-modal
        self.window.transient(parent)
        
        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.window.winfo_screenheight() // 2) - (300 // 2)
        self.window.geometry(f"400x300+{x}+{y}")
        
        # Create main frame
        self.main_frame = ttk.Frame(self.window, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        
        # Create content
        self.create_content()
        
    def create_content(self):
        # Title
        title_label = ttk.Label(self.main_frame, text="Oversee", font=("Helvetica", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Description
        desc_text = "A camera management and control application"
        desc_label = ttk.Label(self.main_frame, text=desc_text, wraplength=350)
        desc_label.grid(row=1, column=0, pady=(0, 20))
        
        # Links frame
        links_frame = ttk.Frame(self.main_frame)
        links_frame.grid(row=2, column=0, pady=(0, 20))
        
        # Author link
        author_label = ttk.Label(links_frame, text="Author: ", cursor="hand2")
        author_label.grid(row=0, column=0, sticky=tk.W)
        author_link = ttk.Label(links_frame, text="github.com/yetanothernothacking", 
                              foreground="blue", cursor="hand2")
        author_link.grid(row=0, column=1, sticky=tk.W)
        author_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/yetanothernothacking"))
        
        # Source link
        source_label = ttk.Label(links_frame, text="Source: ", cursor="hand2")
        source_label.grid(row=1, column=0, sticky=tk.W)
        source_link = ttk.Label(links_frame, text="github.com/yetanothernothacking/oversee", 
                              foreground="blue", cursor="hand2")
        source_link.grid(row=1, column=1, sticky=tk.W)
        source_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/yetanothernothacking/oversee"))
        
        # Website link
        website_label = ttk.Label(links_frame, text="Website: ", cursor="hand2")
        website_label.grid(row=2, column=0, sticky=tk.W)
        website_link = ttk.Label(links_frame, text="silverflag.net/oversee", 
                               foreground="blue", cursor="hand2")
        website_link.grid(row=2, column=1, sticky=tk.W)
        website_link.bind("<Button-1>", lambda e: webbrowser.open("https://silverflag.net/oversee"))
        
        # Silverflag project text
        sf_frame = ttk.Frame(self.main_frame)
        sf_frame.grid(row=3, column=0, pady=(0, 10))
        
        sf_text = ttk.Label(sf_frame, text="Part of the ")
        sf_text.grid(row=0, column=0)
        
        sf_link = ttk.Label(sf_frame, text="Silverflag", foreground="blue", cursor="hand2")
        sf_link.grid(row=0, column=1)
        sf_link.bind("<Button-1>", lambda e: webbrowser.open("https://silverflag.net"))
        
        sf_text2 = ttk.Label(sf_frame, text=" project")
        sf_text2.grid(row=0, column=2)
        
        # Load and display Silverflag logo
        try:
            response = requests.get("https://raw.githubusercontent.com/Silverflag/sf-clearnet-v2/refs/heads/main/assets/logos/sf-logo-long-plain.webp")
            image = Image.open(BytesIO(response.content))
            # Resize image to fit window width while maintaining aspect ratio
            width = 350
            ratio = width / image.width
            height = int(image.height * ratio)
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            
            logo_label = ttk.Label(self.main_frame, image=photo)
            logo_label.image = photo  # Keep a reference
            logo_label.grid(row=4, column=0, pady=(10, 0))
        except Exception as e:
            print(f"Failed to load logo: {e}") 