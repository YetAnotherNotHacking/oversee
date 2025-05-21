#!/usr/bin/env python3
import sys, re, os
def clean_python_code(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'"""[\s\S]*?"""', '', content)
        content = re.sub(r"'''[\s\S]*?'''", '', content)
        lines = content.split('\n')
        processed_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            line = re.sub(r'#.*', '', line).rstrip()
            if not line.strip():
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            indentation = line[:indent]
            is_block = re.match(r'^\s*(def\s+|class\s+|if\s+|elif\s+|else:|try:|except|finally:|for\s+|while\s+|with\s+)', line.strip())
            in_container = False
            check_line = line.strip()
            if ('{' in check_line and '}' not in check_line) or \
               ('[' in check_line and ']' not in check_line) or \
               ('(' in check_line and ')' not in check_line) or \
               (check_line.endswith((',', ':', '='))):
                in_container = True
            if is_block or in_container:
                processed_lines.append(line)
                i += 1
            else:
                unsafe_to_combine = False
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
                    while j < len(lines):
                        next_line = lines[j]
                        next_line_clean = re.sub(r'#.*', '', next_line).rstrip()
                        if not next_line_clean.strip():
                            j += 1
                            continue
                        next_indent = len(next_line_clean) - len(next_line_clean.lstrip())
                        next_is_block = re.match(r'^\s*(def\s+|class\s+|if\s+|elif\s+|else:|try:|except|finally:|for\s+|while\s+|with\s+)', next_line_clean.strip())
                        next_in_container = ('{' in next_line_clean.strip() and '}' not in next_line_clean.strip()) or \
                                           ('[' in next_line_clean.strip() and ']' not in next_line_clean.strip()) or \
                                           ('(' in next_line_clean.strip() and ')' not in next_line_clean.strip()) or \
                                           next_line_clean.strip().endswith((',', ':', '='))
                        if next_indent != indent or next_is_block or next_in_container:
                            break
                        if current_line.strip().endswith((',', ':', '=', '\\')) or \
                           current_line.strip().startswith(('import ', 'from ')):
                            break
                        if next_line_clean.strip().startswith(('import ', 'from ')):
                            break
                        current_line = current_line + "; " + next_line_clean.strip()
                        j += 1
                    processed_lines.append(current_line)
                    i = j if j > i + 1 else i + 1
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
        