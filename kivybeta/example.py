# main.py - Basic Kivy GUI Example
# This example demonstrates common Kivy widgets and layout patterns
# This is claude generated, only used for a reffernce for how to do things using kivy.

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock


class MainWidget(BoxLayout):
    """Main widget containing all UI elements"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Set main layout orientation to vertical
        self.orientation = 'vertical'
        self.padding = 20
        self.spacing = 10
        
        # Create and add widgets
        self.create_title()
        self.create_input_section()
        self.create_controls_section()
        self.create_progress_section()
        self.create_buttons_section()
    
    def create_title(self):
        """Create title label"""
        title = Label(
            text='Kivy GUI Example App',
            size_hint_y=None,
            height='50dp',
            font_size='20sp',
            bold=True
        )
        self.add_widget(title)
    
    def create_input_section(self):
        """Create text input section"""
        # Container for input elements
        input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='40dp')
        
        # Text input field
        self.text_input = TextInput(
            hint_text='Enter some text here...',
            multiline=False,
            size_hint_x=0.7
        )
        
        # Button to process text input
        process_btn = Button(
            text='Process Text',
            size_hint_x=0.3
        )
        process_btn.bind(on_press=self.process_text)
        
        input_layout.add_widget(self.text_input)
        input_layout.add_widget(process_btn)
        self.add_widget(input_layout)
        
        # Label to display processed text
        self.output_label = Label(
            text='Output will appear here...',
            size_hint_y=None,
            height='40dp',
            text_size=(None, None)
        )
        self.add_widget(self.output_label)
    
    def create_controls_section(self):
        """Create controls section with slider and switch"""
        controls_layout = GridLayout(cols=2, size_hint_y=None, height='100dp', spacing=10)
        
        # Slider control
        slider_layout = BoxLayout(orientation='vertical')
        slider_layout.add_widget(Label(text='Slider Value:', size_hint_y=0.4))
        
        self.slider = Slider(
            min=0,
            max=100,
            value=50,
            step=1
        )
        self.slider.bind(value=self.on_slider_change)
        
        self.slider_label = Label(text='50', size_hint_y=0.3)
        
        slider_layout.add_widget(self.slider)
        slider_layout.add_widget(self.slider_label)
        
        # Switch control
        switch_layout = BoxLayout(orientation='vertical')
        switch_layout.add_widget(Label(text='Toggle Switch:', size_hint_y=0.4))
        
        self.switch = Switch(active=False)
        self.switch.bind(active=self.on_switch_toggle)
        
        self.switch_label = Label(text='OFF', size_hint_y=0.3)
        
        switch_layout.add_widget(self.switch)
        switch_layout.add_widget(self.switch_label)
        
        controls_layout.add_widget(slider_layout)
        controls_layout.add_widget(switch_layout)
        self.add_widget(controls_layout)
    
    def create_progress_section(self):
        """Create progress bar section"""
        progress_layout = BoxLayout(orientation='vertical', size_hint_y=None, height='80dp')
        
        progress_layout.add_widget(Label(text='Progress Bar:', size_hint_y=0.4))
        
        self.progress_bar = ProgressBar(
            max=100,
            value=0
        )
        progress_layout.add_widget(self.progress_bar)
        
        # Button to simulate progress
        progress_btn = Button(
            text='Start Progress',
            size_hint_y=0.4
        )
        progress_btn.bind(on_press=self.start_progress)
        progress_layout.add_widget(progress_btn)
        
        self.add_widget(progress_layout)
    
    def create_buttons_section(self):
        """Create action buttons section"""
        buttons_layout = GridLayout(cols=2, size_hint_y=None, height='60dp', spacing=10)
        
        # Show popup button
        popup_btn = Button(text='Show Popup')
        popup_btn.bind(on_press=self.show_popup)
        
        # Clear all button
        clear_btn = Button(text='Clear All')
        clear_btn.bind(on_press=self.clear_all)
        
        buttons_layout.add_widget(popup_btn)
        buttons_layout.add_widget(clear_btn)
        self.add_widget(buttons_layout)
    
    # Event handlers
    def process_text(self, instance):
        """Process the text input"""
        input_text = self.text_input.text
        if input_text:
            processed = f"Processed: {input_text.upper()} (Length: {len(input_text)})"
            self.output_label.text = processed
        else:
            self.output_label.text = "No text to process!"
    
    def on_slider_change(self, instance, value):
        """Handle slider value changes"""
        self.slider_label.text = str(int(value))
        # Update progress bar to match slider
        self.progress_bar.value = value
    
    def on_switch_toggle(self, instance, value):
        """Handle switch toggle"""
        self.switch_label.text = 'ON' if value else 'OFF'
    
    def start_progress(self, instance):
        """Simulate progress animation"""
        self.progress_bar.value = 0
        # Schedule progress updates
        Clock.schedule_interval(self.update_progress, 0.1)
    
    def update_progress(self, dt):
        """Update progress bar"""
        self.progress_bar.value += 2
        if self.progress_bar.value >= 100:
            return False  # Stop the scheduled updates
        return True
    
    def show_popup(self, instance):
        """Show a popup dialog"""
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        popup_content.add_widget(Label(text='This is a popup dialog!'))
        
        close_btn = Button(text='Close', size_hint_y=None, height='40dp')
        popup_content.add_widget(close_btn)
        
        popup = Popup(
            title='Example Popup',
            content=popup_content,
            size_hint=(0.8, 0.6)
        )
        
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def clear_all(self, instance):
        """Clear all inputs and reset values"""
        self.text_input.text = ''
        self.output_label.text = 'Output will appear here...'
        self.slider.value = 50
        self.switch.active = False
        self.progress_bar.value = 0


class MyKivyApp(App):
    """Main application class"""
    
    def build(self):
        """Build and return the main widget"""
        # Set window title (for desktop)
        self.title = 'My Kivy App'
        
        # Return the main widget
        return MainWidget()
    
    def on_start(self):
        """Called when the app starts"""
        print("App started successfully!")
    
    def on_stop(self):
        """Called when the app stops"""
        print("App is closing...")


# Entry point for the application
if __name__ == '__main__':
    MyKivyApp().run()