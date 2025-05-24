def get_ip_range(filename, start, end):
    """Get a range of IP addresses from the file, with bounds checking."""
    try:
        print(f"Opening file: {filename}")
        with open(filename) as f:
            lines = [line.strip() for line in f if line.strip()]
        print(f"Read {len(lines)} lines from file")
        
        # Ensure start and end are within valid bounds
        start = max(1, min(start, len(lines)))  # Ensure start is at least 1 and not beyond file length
        end = max(1, min(end, len(lines)))      # Ensure end is at least 1 and not beyond file length
        
        # Swap start and end if start is greater than end
        if start > end:
            start, end = end, start
            
        print(f"Range: start={start}, end={end}, total lines={len(lines)}")
        
        if start > len(lines):
            print("Start position beyond file length")
            return []
            
        result = lines[start - 1:end]
        print(f"Returning {len(result)} IPs")
        return result
    except Exception as e:
        print(f"Error reading IP list file: {e}")
        return []