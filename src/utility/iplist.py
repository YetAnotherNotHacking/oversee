import logging


# Read from the files
def get_ip_range(filename, start, end):
    """Get a range of IP addresses from the file, with bounds checking."""
    try:
        with open(filename) as f:
            lines = [line.strip() for line in f if line.strip()]
        start = max(1, start)  # Ensure start is at least 1
        end = min(len(lines) + 1, end)  # Ensure end doesn't exceed file length
        if start > len(lines) or start > end:
            return []
        return lines[start - 1:end - 1]
    except Exception as e:
        return []