#!/usr/bin/env python3
"""
Threaded IP Camera Tester Script
Tests IP addresses from a file using capture_single_frame function
and updates the file with only working IPs using concurrent threading.
"""

import os
import sys
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set, Tuple
from backend.cameradown import capture_single_frame
import settings

# Configure logging with thread-safe formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)-10s - %(levelname)s - %(message)s'
)

# Thread-safe logging lock
log_lock = threading.Lock()

def thread_safe_log(level, message):
    """Thread-safe logging function."""
    with log_lock:
        if level == 'info':
            logging.info(message)
        elif level == 'warning':
            logging.warning(message)
        elif level == 'error':
            logging.error(message)

def read_ips_from_file(filename: str) -> List[str]:
    """Read IP addresses from file, one per line."""
    try:
        with open(filename, 'r') as f:
            ips = [line.strip() for line in f if line.strip()]
        thread_safe_log('info', f"Read {len(ips)} IPs from {filename}")
        return ips
    except FileNotFoundError:
        thread_safe_log('error', f"File {filename} not found")
        return []
    except Exception as e:
        thread_safe_log('error', f"Error reading file {filename}: {e}")
        return []

def test_camera_ip(ip: str, timeout: int = 5) -> Tuple[str, bool]:
    """Test if a camera IP is responding by capturing a frame."""
    try:
        # Assume standard camera URL format - adjust as needed
        camera_url = f"http://{ip}/video"  # Modify this based on your camera URL format
        
        thread_safe_log('info', f"Testing {ip}...")
        frame = capture_single_frame(camera_url, timeout)
        
        if frame is not None:
            thread_safe_log('info', f"✓ {ip} is working")
            return ip, True
        else:
            thread_safe_log('warning', f"✗ {ip} failed to capture frame")
            return ip, False
            
    except Exception as e:
        thread_safe_log('error', f"✗ {ip} error: {e}")
        return ip, False

def write_ips_to_file(filename: str, working_ips: List[str]) -> None:
    """Write working IP addresses to file, one per line."""
    try:
        with open(filename, 'w') as f:
            for ip in working_ips:
                f.write(f"{ip}\n")
        thread_safe_log('info', f"Written {len(working_ips)} working IPs to {filename}")
    except Exception as e:
        thread_safe_log('error', f"Error writing to file {filename}: {e}")

def test_and_update_ips_threaded(filename: str, timeout: int = 5, max_workers: int = 10) -> None:
    """Main function to test IPs concurrently and update the file with working ones."""
    if not os.path.exists(filename):
        thread_safe_log('error', f"IP file {filename} does not exist")
        return
    
    # Read IPs from file
    all_ips = read_ips_from_file(filename)
    
    if not all_ips:
        thread_safe_log('warning', "No IPs found to test")
        return
    
    working_ips = []
    total_ips = len(all_ips)
    completed_count = 0
    
    thread_safe_log('info', f"Starting to test {total_ips} IP addresses with {max_workers} concurrent threads...")
    
    # Use ThreadPoolExecutor for concurrent testing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all IP tests to the thread pool
        future_to_ip = {
            executor.submit(test_camera_ip, ip, timeout): ip 
            for ip in all_ips
        }
        
        # Process completed tests as they finish
        for future in as_completed(future_to_ip):
            completed_count += 1
            original_ip = future_to_ip[future]
            
            try:
                ip, is_working = future.result()
                if is_working:
                    working_ips.append(ip)
                
                # Progress update
                progress_percent = (completed_count / total_ips) * 100
                thread_safe_log('info', f"Progress: {completed_count}/{total_ips} ({progress_percent:.1f}%)")
                
            except Exception as e:
                thread_safe_log('error', f"Exception testing {original_ip}: {e}")
    
    # Summary
    working_count = len(working_ips)
    failed_count = total_ips - working_count
    
    thread_safe_log('info', f"\n=== Test Summary ===")
    thread_safe_log('info', f"Total IPs tested: {total_ips}")
    thread_safe_log('info', f"Working IPs: {working_count}")
    thread_safe_log('info', f"Failed IPs: {failed_count}")
    thread_safe_log('info', f"Success rate: {(working_count/total_ips)*100:.1f}%")
    
    # Sort working IPs to maintain consistent output
    working_ips.sort()
    
    # Update file with working IPs only
    write_ips_to_file(filename, working_ips)
    
    if working_ips:
        thread_safe_log('info', f"\nWorking IPs:")
        for ip in working_ips:
            thread_safe_log('info', f"  {ip}")
    else:
        thread_safe_log('warning', "No working IPs found!")

def validate_file_address_reachable(max_workers: int = 10):
    """
    Main entry point for threaded IP validation.
    
    Args:
        max_workers: Maximum number of concurrent threads (default: 10)
                    Adjust based on your system capabilities and network limits
    """
    filename = settings.ip_list_file
    timeout = 10
    
    thread_safe_log('info', f"Testing cameras from file: {filename}")
    thread_safe_log('info', f"Timeout per camera: {timeout} seconds")
    thread_safe_log('info', f"Max concurrent threads: {max_workers}")
    
    test_and_update_ips_threaded(filename, timeout, max_workers)

# Alternative function names for backward compatibility
def test_and_update_ips(filename: str, timeout: int = 5) -> None:
    """Backward compatible function - now uses threading by default."""
    test_and_update_ips_threaded(filename, timeout, max_workers=10)

if __name__ == "__main__":
    validate_file_address_reachable(max_workers=10)