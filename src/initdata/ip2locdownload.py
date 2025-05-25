import requests
import zipfile
import os
import sys
from pathlib import Path

def download_database(DB_URL, DB_ZIP, DB_CSV, progress_callback=None):
    """Download the IP2LOC database"""
    try:
        # Create data directory if it doesn't exist
        data_dir = Path(__file__).parent.parent / 'data'
        data_dir.mkdir(exist_ok=True)
        
        db_zip_path = data_dir / DB_ZIP
        db_csv_path = data_dir / DB_CSV
        
        # Check if we already have the CSV file
        if db_csv_path.exists():
            if progress_callback:
                progress_callback("IP2LOC database already exists", 100.0)
            return True
            
        # Download if ZIP doesn't exist
        if not db_zip_path.exists():
            if progress_callback:
                progress_callback("Downloading IP2LOC database...", 0.0)
            
            response = requests.get(DB_URL, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            with open(db_zip_path, 'wb') as f:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    f.write(data)
                    if total_size > 0 and progress_callback:
                        progress = (downloaded / total_size) * 50.0  # First 50% for download
                        progress_callback(f"Downloading IP2LOC database... {progress:.1f}%", progress)
            
            if progress_callback:
                progress_callback("Download complete, extracting...", 50.0)
        
        # Extract the ZIP file
        if not db_csv_path.exists():
            with zipfile.ZipFile(db_zip_path, 'r') as zip_ref:
                zip_ref.extractall(data_dir)
            
            if progress_callback:
                progress_callback("IP2LOC database ready", 100.0)
        
        return True
        
    except Exception as e:
        print(f"Error downloading/extracting IP2LOC database: {e}", file=sys.stderr)
        if progress_callback:
            progress_callback(f"Error: {str(e)}", 0.0)
        return False

def extract_database(DB_CSV, DB_ZIP):
    """Legacy function for backward compatibility"""
    data_dir = Path(__file__).parent.parent / 'data'
    db_zip_path = data_dir / DB_ZIP
    db_csv_path = data_dir / DB_CSV
    
    if not db_csv_path.exists() and db_zip_path.exists():
        with zipfile.ZipFile(db_zip_path, 'r') as zip_ref:
            zip_ref.extractall(data_dir)