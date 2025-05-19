import re
import argparse
import sys
pattern = re.compile(r'(?:https?://)?(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?(/[^?]*)?')
def extract_and_format(text):
    matches = pattern.findall(text)
    formatted_urls = []
    for m in matches:
        ip = m[0]
        port = f":{m[1]}" if m[1] else ""; path = m[2] if m[2] else ""; formatted_urls.append(f'{ip}{port}{path}')
    return formatted_urls
def process_file(input_file, output_file):
    try:
        with open(input_file, 'r') as f:
            lines = f.readlines()
        formatted_urls = []
        for line in lines:
            line = line.strip()
            if line:
                formatted = extract_and_format(line)
                formatted_urls.extend(formatted)
        with open(output_file, 'w') as f:
            for url in formatted_urls:
                f.write(f"{url}\n")
        return len(formatted_urls)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 0
def format_file(input_file, output_file):
    print(f"Starting to process {input_file}")
    count = process_file(input_file, output_file); print(f"Processed {count} links to the correct format and wrote the output to {output_file}")