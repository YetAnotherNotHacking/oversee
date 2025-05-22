import logging
import socket
import struct

# Cache for geolocation data
geolocation_data = {}

# This would be loaded from your IP database file
ip_database = []

def ip_to_int(ip_address):
    """Convert IP address string to integer."""
    try:
        return struct.unpack("!I", socket.inet_aton(ip_address))[0]
    except socket.error:
        return 0

def get_geolocation(ip_address):
    """Get geolocation information for an IP address."""
    if not ip_address or ip_address == "Unknown":
        return "Unknown Location"
        
    # Check cache first
    if ip_address in geolocation_data:
        return geolocation_data[ip_address]

    try:
        # Extract just the IP if it contains a port
        if ":" in ip_address:
            ip_address = ip_address.split(":")[0]
            
        # Convert to integer for lookup
        ip_int = ip_to_int(ip_address)
        if ip_int == 0:
            return "Unknown Location"
            
        # Search through the database
        for ip_from, ip_to, country in ip_database:
            if ip_from <= ip_int <= ip_to:
                geolocation_data[ip_address] = country
                return country
    except Exception as e:
        logging.error(f"Geolocation lookup error for {ip_address}: {e}")

    geolocation_data[ip_address] = "Unknown Location"
    return "Unknown Location"

def get_ip_range(filename, start, end):
    """Get a range of IP addresses from the file, with bounds checking."""
    try:
        with open(filename) as f:
            lines = [line.strip() for line in f if line.strip()]
        
        # Ensure start and end are valid
        start = max(1, start)  # Ensure start is at least 1
        end = min(len(lines) + 1, end)  # Ensure end doesn't exceed file length
        
        # Check for potential bounds errors
        if start > len(lines) or start > end:
            return []
        
        # Adjust for 1-based indexing to 0-based
        return lines[start - 1:end - 1]
    except Exception as e:
        logging.error(f"Error in get_ip_range: {e}")
        return []

def count_ips_in_file(filename):
    """Count total number of IPs in a file."""
    try:
        with open(filename) as f:
            return sum(1 for line in f if line.strip())
    except Exception as e:
        logging.error(f"Error counting IPs in file: {e}")
        return 0

def load_ip_database(database_file):
    """Load IP geolocation database from file."""
    global ip_database
    try:
        with open(database_file, 'r') as f:
            ip_database = []
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    ip_from = int(parts[0])
                    ip_to = int(parts[1])
                    country = parts[2]
                    ip_database.append((ip_from, ip_to, country))
        logging.info(f"Loaded {len(ip_database)} IP ranges from database")
    except Exception as e:
        logging.error(f"Error loading IP database: {e}")
        ip_database = []