#!/usr/bin/env python3
import sys, re, os

def clean_python_code(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Remove docstrings and multi-line comments
        content = re.sub(r'"""[\s\S]*?"""', '', content)
        content = re.sub(r"'''[\s\S]*?'''", '', content)
        
        # Process the file line by line to handle comments and preserve indentation
        lines = content.split('\n')
        processed_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Remove inline comments
            line = re.sub(r'#.*', '', line).rstrip()
            
            # Skip empty lines
            if not line.strip():
                i += 1
                continue
                
            # Get the indentation level
            indent = len(line) - len(line.lstrip())
            indentation = line[:indent]
            
            # Check if this is a block statement (needs to keep its newline)
            is_block = re.match(r'^\s*(def\s+|class\s+|if\s+|elif\s+|else:|try:|except|finally:|for\s+|while\s+|with\s+)', line.strip())
            
            # Check if we're inside a container (dict, list, tuple, etc.) or complex structure
            in_container = False
            check_line = line.strip()
            if ('{' in check_line and '}' not in check_line) or \
               ('[' in check_line and ']' not in check_line) or \
               ('(' in check_line and ')' not in check_line) or \
               (check_line.endswith((',', ':', '='))):
                in_container = True
                
            if is_block or in_container:
                # For block statements or container elements, keep them as is
                processed_lines.append(line)
                i += 1
            else:
                # For non-block, non-container statements, try to combine with similar indented lines
                # But first check if this line is safe to combine
                unsafe_to_combine = False
                
                # Check if we're continuing a multi-line statement or dictionary/list/tuple definition
                if i > 0 and processed_lines:
                    prev_line = processed_lines[-1].strip()
                    if prev_line.endswith((',', ':', '=')) or \
                       ('{' in prev_line and '}' not in prev_line) or \
                       ('[' in prev_line and ']' not in prev_line) or \
                       ('(' in prev_line and ')' not in prev_line):
                        unsafe_to_combine = True
                
                if unsafe_to_combine:
                    processed_lines.append(line)
                    i += 1
                else:
                    current_line = line
                    j = i + 1
                    
                    # Look ahead to see if we can combine lines with the same indentation
                    while j < len(lines):
                        next_line = lines[j]
                        next_line_clean = re.sub(r'#.*', '', next_line).rstrip()
                        if not next_line_clean.strip():
                            j += 1
                            continue
                            
                        next_indent = len(next_line_clean) - len(next_line_clean.lstrip())
                        
                        # Check if the next line should not be combined
                        next_is_block = re.match(r'^\s*(def\s+|class\s+|if\s+|elif\s+|else:|try:|except|finally:|for\s+|while\s+|with\s+)', next_line_clean.strip())
                        next_in_container = ('{' in next_line_clean.strip() and '}' not in next_line_clean.strip()) or \
                                           ('[' in next_line_clean.strip() and ']' not in next_line_clean.strip()) or \
                                           ('(' in next_line_clean.strip() and ')' not in next_line_clean.strip()) or \
                                           next_line_clean.strip().endswith((',', ':', '='))
                                           
                        # Stop if we hit a line with different indentation, a block statement, or a container
                        if next_indent != indent or next_is_block or next_in_container:
                            break
                        
                        # Don't combine if current line ends with characters that would make semicolon invalid
                        if current_line.strip().endswith((',', ':', '=', '\\')) or \
                           current_line.strip().startswith(('import ', 'from ')):
                            break
                            
                        # Don't combine if next line is an import statement
                        if next_line_clean.strip().startswith(('import ', 'from ')):
                            break
                        
                        # Combine with the current line
                        current_line = current_line + "; " + next_line_clean.strip()
                        j += 1
                    
                    processed_lines.append(current_line)
                    i = j if j > i + 1 else i + 1
        
        # Join the processed lines
        output = '\n'.join(processed_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
            
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input_file output_file")
        sys.exit(1)
    
    input_file, output_file = sys.argv[1], sys.argv[2]
    
    if not os.path.isfile(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        sys.exit(1)
    
    if clean_python_code(input_file, output_file):
        print(f"Code cleaned successfully. Output written to '{output_file}'.")
        sys.exit(0)
    else:
        print("Failed to clean the code.")
        sys.exit(1)
