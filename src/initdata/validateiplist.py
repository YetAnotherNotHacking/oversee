#!/usr/bin/env python3
"""
IP Camera Tester Script
Tests IP addresses from a file using capture_single_frame function
and updates the file with only working IPs.
"""

import os
import sys
import logging
from typing import List, Set
from backend.cameradown import capture_single_frame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def read_ips_from_file(filename: str) -> List[str]:
    """Read IP addresses from file, one per line."""
    try:
        with open(filename, 'r') as f:
            ips = [line.strip() for line in f if line.strip()]
        logging.info(f"Read {len(ips)} IPs from {filename}")
        return ips
    except FileNotFoundError:
        logging.error(f"File {filename} not found")
        return []
    except Exception as e:
        logging.error(f"Error reading file {filename}: {e}")
        return []

def test_camera_ip(ip: str, timeout: int = 5) -> bool:
    """Test if a camera IP is responding by capturing a frame."""
    try:
        # Assume standard camera URL format - adjust as needed
        camera_url = f"http://{ip}/video"  # Modify this based on your camera URL format
        
        logging.info(f"Testing {ip}...")
        frame = capture_single_frame(camera_url, timeout)
        
        if frame is not None:
            logging.info(f"✓ {ip} is working")
            return True
        else:
            logging.warning(f"✗ {ip} failed to capture frame")
            return False
            
    except Exception as e:
        logging.error(f"✗ {ip} error: {e}")
        return False

def write_ips_to_file(filename: str, working_ips: List[str]) -> None:
    """Write working IP addresses to file, one per line."""
    try:
        with open(filename, 'w') as f:
            for ip in working_ips:
                f.write(f"{ip}\n")
        logging.info(f"Written {len(working_ips)} working IPs to {filename}")
    except Exception as e:
        logging.error(f"Error writing to file {filename}: {e}")

def test_and_update_ips(filename: str, timeout: int = 5) -> None:
    """Main function to test IPs and update the file with working ones."""
    if not os.path.exists(filename):
        logging.error(f"IP file {filename} does not exist")
        return
    
    # Read IPs from file
    all_ips = read_ips_from_file(filename)
    
    if not all_ips:
        logging.warning("No IPs found to test")
        return
    
    working_ips = []
    total_ips = len(all_ips)
    
    logging.info(f"Starting to test {total_ips} IP addresses...")
    
    # Test each IP
    for i, ip in enumerate(all_ips, 1):
        logging.info(f"Progress: {i}/{total_ips}")
        
        if test_camera_ip(ip, timeout):
            working_ips.append(ip)
    
    # Summary
    working_count = len(working_ips)
    failed_count = total_ips - working_count
    
    logging.info(f"\n=== Test Summary ===")
    logging.info(f"Total IPs tested: {total_ips}")
    logging.info(f"Working IPs: {working_count}")
    logging.info(f"Failed IPs: {failed_count}")
    logging.info(f"Success rate: {(working_count/total_ips)*100:.1f}%")
    
    # Update file with working IPs only
    write_ips_to_file(filename, working_ips)
    
    if working_ips:
        logging.info(f"\nWorking IPs:")
        for ip in working_ips:
            logging.info(f"  {ip}")
    else:
        logging.warning("No working IPs found!")

def validate_file_address_reachable(filename, timeout):
    logging.info(f"Testing cameras from file: {filename}")
    logging.info(f"Timeout per camera: {timeout} seconds")
    test_and_update_ips(filename, timeout)

if __name__ == "__main__":
    main()