import tkinter as tk
from tkinter import ttk, scrolledtext
import re

def show_markdown_docs(markdown_text, title="Documentation", width=800, height=600):
    """
    Display markdown text in a nicely formatted tkinter window with scrolling.
    
    Args:
        markdown_text (str): The markdown content to display
        title (str): Window title (default: "Documentation")
        width (int): Window width in pixels (default: 800)
        height (int): Window height in pixels (default: 600)
    """
    
    def get_syntax_highlighting_tags(code, language=None):
        """Apply basic syntax highlighting to code"""
        if not language:
            language = "python"  # default
        
        # Python syntax highlighting
        if language.lower() in ['python', 'py']:
            keywords = ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 
                       'import', 'from', 'return', 'True', 'False', 'None', 'and', 'or', 'not',
                       'in', 'is', 'with', 'as', 'pass', 'break', 'continue', 'lambda', 'yield']
            
            # Split into tokens while preserving positions
            tokens = []
            current_pos = 0
            
            # Find strings first (to avoid highlighting keywords inside strings)
            string_pattern = r'(["\'])((?:\\.|(?!\1).)*?)\1'
            for match in re.finditer(string_pattern, code):
                # Add text before string
                if match.start() > current_pos:
                    tokens.append((code[current_pos:match.start()], None))
                # Add string
                tokens.append((match.group(), "string"))
                current_pos = match.end()
            
            # Add remaining text
            if current_pos < len(code):
                remaining_text = code[current_pos:]
                
                # Highlight keywords in remaining text
                for keyword in keywords:
                    remaining_text = re.sub(
                        r'\b' + re.escape(keyword) + r'\b',
                        f'KEYWORD_START{keyword}KEYWORD_END',
                        remaining_text
                    )
                
                # Highlight comments
                remaining_text = re.sub(r'(#.*?)(\n|$)', r'COMMENT_START\1COMMENT_END\2', remaining_text)
                
                # Parse the marked text
                parts = re.split(r'(KEYWORD_START.*?KEYWORD_END|COMMENT_START.*?COMMENT_END)', remaining_text)
                for part in parts:
                    if part.startswith('KEYWORD_START'):
                        tokens.append((part[13:-11], "keyword"))  # Remove markers
                    elif part.startswith('COMMENT_START'):
                        tokens.append((part[13:-11], "comment"))  # Remove markers
                    elif part:
                        tokens.append((part, None))
            
            return tokens
        
        # Default: no highlighting
        return [(code, None)]
    
    def parse_markdown_to_text_widget(text_widget, markdown):
        """Parse markdown and insert formatted text into the widget"""
        
        # Configure text tags for different markdown elements with dark theme colors
        text_widget.tag_configure("h1", font=("Segoe UI", 20, "bold"), foreground="#e1e1e1", spacing1=12, spacing3=6)
        text_widget.tag_configure("h2", font=("Segoe UI", 17, "bold"), foreground="#d4d4d4", spacing1=10, spacing3=5)
        text_widget.tag_configure("h3", font=("Segoe UI", 15, "bold"), foreground="#cccccc", spacing1=8, spacing3=4)
        text_widget.tag_configure("h4", font=("Segoe UI", 13, "bold"), foreground="#c0c0c0", spacing1=6, spacing3=3)
        text_widget.tag_configure("bold", font=("Segoe UI", 11, "bold"), foreground="#ffffff")
        text_widget.tag_configure("italic", font=("Segoe UI", 11, "italic"), foreground="#e0e0e0")
        text_widget.tag_configure("code", font=("Cascadia Code", 10), background="#3c3c3c", foreground="#9cdcfe", 
                                relief="solid", borderwidth=1)
        text_widget.tag_configure("code_block", font=("Cascadia Code", 10), background="#1e1e1e", foreground="#d4d4d4",
                                relief="solid", borderwidth=1, lmargin1=15, lmargin2=15, rmargin=15,
                                spacing1=8, spacing3=8)
        
        # Syntax highlighting tags
        text_widget.tag_configure("keyword", font=("Cascadia Code", 10), background="#1e1e1e", foreground="#569cd6")
        text_widget.tag_configure("string", font=("Cascadia Code", 10), background="#1e1e1e", foreground="#ce9178")
        text_widget.tag_configure("comment", font=("Cascadia Code", 10), background="#1e1e1e", foreground="#6a9955")
        
        text_widget.tag_configure("bullet", lmargin1=25, lmargin2=35, foreground="#e0e0e0")
        text_widget.tag_configure("link", foreground="#569cd6", underline=True)
        
        lines = markdown.split('\n')
        in_code_block = False
        code_block_content = []
        code_language = None
        
        for line in lines:
            # Handle code blocks
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of code block - process with syntax highlighting
                    if code_block_content:
                        full_code = '\n'.join(code_block_content)
                        highlighted_tokens = get_syntax_highlighting_tags(full_code, code_language)
                        
                        for token_text, token_type in highlighted_tokens:
                            if token_type:
                                text_widget.insert(tk.END, token_text, token_type)
                            else:
                                text_widget.insert(tk.END, token_text, "code_block")
                        text_widget.insert(tk.END, '\n')
                    
                    code_block_content = []
                    in_code_block = False
                    code_language = None
                else:
                    # Start of code block
                    in_code_block = True
                    # Extract language if specified
                    lang_match = re.match(r'```(\w+)', line.strip())
                    if lang_match:
                        code_language = lang_match.group(1)
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            # Handle headers
            if line.startswith('# '):
                text_widget.insert(tk.END, line[2:] + '\n', "h1")
            elif line.startswith('## '):
                text_widget.insert(tk.END, line[3:] + '\n', "h2")
            elif line.startswith('### '):
                text_widget.insert(tk.END, line[4:] + '\n', "h3")
            elif line.startswith('#### '):
                text_widget.insert(tk.END, line[5:] + '\n', "h4")
            # Handle bullet points
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                bullet_text = '• ' + line.strip()[2:]
                formatted_parts = parse_inline_markdown(bullet_text)
                insert_formatted_text(text_widget, formatted_parts, "bullet")
                text_widget.insert(tk.END, '\n')
            # Handle numbered lists
            elif re.match(r'^\d+\. ', line.strip()):
                formatted_parts = parse_inline_markdown(line.strip())
                insert_formatted_text(text_widget, formatted_parts, "bullet")
                text_widget.insert(tk.END, '\n')
            else:
                # Handle inline formatting for regular text
                if line.strip():
                    formatted_parts = parse_inline_markdown(line)
                    insert_formatted_text(text_widget, formatted_parts)
                text_widget.insert(tk.END, '\n')
    
    def parse_inline_markdown(text):
        """Parse inline markdown with improved logic"""
        if not text.strip():
            return [(text, None)]
        
        result = []
        i = 0
        
        while i < len(text):
            # Look for backticks (inline code) - highest priority
            if text[i] == '`':
                end = text.find('`', i + 1)
                if end != -1:
                    result.append((text[i+1:end], 'code'))
                    i = end + 1
                    continue
            
            # Look for bold **text**
            if i < len(text) - 1 and text[i:i+2] == '**':
                end = text.find('**', i + 2)
                if end != -1:
                    result.append((text[i+2:end], 'bold'))
                    i = end + 2
                    continue
            
            # Look for italic *text* (but not **)
            if text[i] == '*' and (i == 0 or text[i-1] != '*') and (i == len(text)-1 or text[i+1] != '*'):
                end = text.find('*', i + 1)
                if end != -1 and (end == len(text)-1 or text[end+1] != '*'):
                    result.append((text[i+1:end], 'italic'))
                    i = end + 1
                    continue
            
            # Regular character - find next special character
            start = i
            while i < len(text) and text[i] not in ['*', '`']:
                i += 1
            
            if i > start:
                result.append((text[start:i], None))
        
        return result
    
    def insert_formatted_text(text_widget, formatted_parts, base_tag=None):
        """Insert formatted text parts into the widget"""
        for text, tag in formatted_parts:
            if tag:
                text_widget.insert(tk.END, text, tag)
            elif base_tag:
                text_widget.insert(tk.END, text, base_tag)
            else:
                text_widget.insert(tk.END, text)
    
    # Create the main window
    root = tk.Tk()
    root.title(title)
    root.geometry(f"{width}x{height}")
    root.configure(bg="#2d2d2d")
    
    # Configure the window to be resizable
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    
    # Configure dark theme style
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('Dark.TFrame', background='#2d2d2d')
    style.configure('Dark.TButton', 
                   background='#404040', 
                   foreground='#ffffff',
                   focuscolor='none',
                   borderwidth=1,
                   relief='flat')
    style.map('Dark.TButton',
              background=[('active', '#505050'),
                         ('pressed', '#353535')])
    style.configure('Dark.Vertical.TScrollbar',
                   background='#404040',
                   troughcolor='#2d2d2d',
                   borderwidth=0,
                   arrowcolor='#ffffff',
                   darkcolor='#404040',
                   lightcolor='#404040')
    
    # Create a frame for the text widget and scrollbar
    main_frame = ttk.Frame(root, style='Dark.TFrame')
    main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    
    # Create the text widget with scrollbar
    text_widget = tk.Text(main_frame, wrap=tk.WORD, font=("Segoe UI", 11), 
                         bg="#1e1e1e", fg="#d4d4d4", padx=20, pady=15,
                         insertbackground="#ffffff", selectbackground="#264f78",
                         selectforeground="#ffffff", borderwidth=0, highlightthickness=0)
    
    # Create scrollbar
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=text_widget.yview, 
                             style='Dark.Vertical.TScrollbar')
    text_widget.configure(yscrollcommand=scrollbar.set)
    
    # Grid the text widget and scrollbar
    text_widget.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    
    # Parse and insert the markdown content
    parse_markdown_to_text_widget(text_widget, markdown_text)
    
    # Enable text selection while preventing editing
    def on_key_press(event):
        # Allow navigation and selection keys
        allowed_keys = ['Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Prior', 'Next', 'Control_L', 'Control_R']
        if event.keysym in allowed_keys or (event.state & 0x4):  # Ctrl key combinations
            return
        return "break"
    
    text_widget.bind("<KeyPress>", on_key_press)
    
    # Add a close button at the bottom
    button_frame = ttk.Frame(root, style='Dark.TFrame')
    button_frame.grid(row=1, column=0, pady=(5, 8))
    
    close_button = ttk.Button(button_frame, text="✕ Close", command=root.destroy, style='Dark.TButton')
    close_button.pack()
    
    # Center the window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    # Start the GUI event loop
    root.mainloop()