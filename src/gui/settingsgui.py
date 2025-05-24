import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import settings
import json
import os

# Default preferences
DEFAULT_PREFERENCES = {
    'ip_list_file': settings.ip_list_file,
    'tile_server': 'OpenStreetMap',
    'geo_mode': 'scrape',
    'online_color': '#00ff00',
    'offline_color': '#ff0000',
    'favorites_file': 'favorites.json'
}

class SettingsWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Preferences")
        self.window.geometry("600x500")
        self.window.resizable(False, False)
        
        # Load current preferences
        self.preferences = self.load_preferences()
        
        # Make it modal
        self.window.transient(parent)
        self.window.grab_set()
        
        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.window.winfo_screenheight() // 2) - (500 // 2)
        self.window.geometry(f"600x500+{x}+{y}")
        
        # Configure style for dark theme
        self.style = ttk.Style()
        self.style.configure('Settings.TLabel', foreground='white', background='#2b2b2b')
        self.style.configure('Settings.TFrame', background='#2b2b2b')
        self.style.configure('Settings.TCombobox', foreground='white', background='#3c3f41')
        self.style.configure('Settings.TEntry', foreground='white', background='#3c3f41')
        
        # Main container
        main_frame = ttk.Frame(self.window, style='Settings.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Search frame
        search_frame = ttk.Frame(main_frame, style='Settings.TFrame')
        search_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(search_frame, text="Search Settings:", style='Settings.TLabel').pack(side='left', padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_settings)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side='left', padx=5)
        
        # Settings container with scrollbar
        settings_container = ttk.Frame(main_frame, style='Settings.TFrame')
        settings_container.pack(fill='both', expand=True)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(settings_container, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, style='Settings.TFrame')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create settings sections
        self.create_settings_sections()
        
        # Create buttons
        self.create_buttons()
    
    def load_preferences(self):
        """Load preferences from preferences.json or return defaults"""
        try:
            if os.path.exists('preferences.json'):
                with open('preferences.json', 'r') as f:
                    prefs = json.load(f)
                    # Update defaults with any saved preferences
                    return {**DEFAULT_PREFERENCES, **prefs}
        except Exception as e:
            print(f"Error loading preferences: {e}")
        return DEFAULT_PREFERENCES.copy()
    
    def save_preferences(self, preferences):
        """Save preferences to preferences.json"""
        try:
            with open('preferences.json', 'w') as f:
                json.dump(preferences, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving preferences: {e}")
            return False
        
    def create_settings_sections(self):
        # Color options
        self.color_options = {
            'red': '#ff0000',
            'green': '#00ff00',
            'blue': '#0000ff',
            'pink': '#ff69b4',
            'orange': '#ffa500',
            'black': '#000000',
            'white': '#ffffff'
        }
        
        # Section headers and their settings
        sections = {
            "General Settings": [
                ("IP List File", "ip_list_file", "file", "Select IP List File", [("Text files", "*.txt"), ("All files", "*.*")])
            ],
            "Map Settings": [
                ("Map Style", "tile_server", "combo", ["OpenStreetMap", "Google normal", "Google satellite"])
            ],
            "List View Settings": [
                ("Geolocation Mode", "geo_mode", "combo", ["scrape", "local"]),
                ("Online Camera Color", "online_color", "color"),
                ("Offline Camera Color", "offline_color", "color"),
                ("Favorites File", "favorites_file", "file", "Select Favorites File", [("JSON files", "*.json"), ("All files", "*.*")])
            ]
        }
        
        # Create sections
        for section_name, settings_list in sections.items():
            section_frame = ttk.LabelFrame(self.scrollable_frame, text=section_name, style='Settings.TFrame')
            section_frame.pack(fill='x', padx=5, pady=5)
            
            for row, (label, setting_name, setting_type, *args) in enumerate(settings_list):
                ttk.Label(section_frame, text=label + ":", style='Settings.TLabel').grid(row=row, column=0, sticky='w', padx=5, pady=2)
                
                if setting_type == "combo":
                    var = tk.StringVar(value=self.preferences.get(setting_name, args[0][0]))
                    combo = ttk.Combobox(section_frame, textvariable=var, values=args[0], state='readonly', width=30)
                    combo.grid(row=row, column=1, sticky='w', padx=5, pady=2)
                    setattr(self, f"{setting_name}_var", var)
                
                elif setting_type == "color":
                    # Convert hex to color name if possible
                    current_color = self.preferences.get(setting_name, '#00ff00')
                    color_name = next((name for name, hex in self.color_options.items() if hex == current_color), 'green')
                    var = tk.StringVar(value=color_name)
                    combo = ttk.Combobox(section_frame, textvariable=var, values=list(self.color_options.keys()), state='readonly', width=30)
                    combo.grid(row=row, column=1, sticky='w', padx=5, pady=2)
                    setattr(self, f"{setting_name}_var", var)
                
                elif setting_type == "file":
                    file_frame = ttk.Frame(section_frame, style='Settings.TFrame')
                    file_frame.grid(row=row, column=1, sticky='w', padx=5, pady=2)
                    
                    var = tk.StringVar(value=self.preferences.get(setting_name, ''))
                    entry = ttk.Entry(file_frame, textvariable=var, width=30)
                    entry.pack(side='left', padx=(0, 5))
                    
                    def browse_file(var=var, title=args[0], filetypes=args[1]):
                        filename = filedialog.askopenfilename(title=title, filetypes=filetypes)
                        if filename:
                            var.set(filename)
                    
                    ttk.Button(file_frame, text="Browse", command=lambda v=var, t=args[0], f=args[1]: browse_file(v, t, f)).pack(side='left')
                    setattr(self, f"{setting_name}_var", var)
    
    def filter_settings(self, *args):
        search_text = self.search_var.get().lower()
        
        for child in self.scrollable_frame.winfo_children():
            if isinstance(child, ttk.LabelFrame):
                visible = False
                for widget in child.winfo_children():
                    if isinstance(widget, ttk.Label):
                        if search_text in widget.cget("text").lower():
                            visible = True
                            break
                child.pack(fill='x', padx=5, pady=5) if visible else child.pack_forget()
    
    def create_buttons(self):
        button_frame = ttk.Frame(self.window, style='Settings.TFrame')
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def save_preferences():
            try:
                # Collect all settings
                preferences = {
                    'ip_list_file': self.ip_list_file_var.get(),
                    'tile_server': self.tile_server_var.get(),
                    'geo_mode': self.geo_mode_var.get(),
                    'online_color': self.color_options.get(self.online_color_var.get(), '#00ff00'),
                    'offline_color': self.color_options.get(self.offline_color_var.get(), '#ff0000'),
                    'favorites_file': self.favorites_file_var.get()
                }
                
                # Save preferences
                if self.save_preferences(preferences):
                    # Update settings module with new preferences
                    for key, value in preferences.items():
                        setattr(settings, key, value)
                    
                    messagebox.showinfo("Success", "Preferences saved successfully")
                    self.window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to save preferences")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save preferences: {str(e)}")
        
        def reset_preferences():
            if messagebox.askyesno("Reset Preferences", "Are you sure you want to reset all preferences to default values?"):
                self.preferences = DEFAULT_PREFERENCES.copy()
                self.window.destroy()
                SettingsWindow(self.parent)
        
        def cancel_preferences():
            self.window.destroy()
    
        ttk.Button(button_frame, text="Reset to Defaults", command=reset_preferences).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Save", command=save_preferences).pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=cancel_preferences).pack(side='right') 