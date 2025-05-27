import os
import platform
import appdirs
import shutil
from pathlib import Path

def get_app_data_dir():
    """
    Get the appropriate data directory for the application based on the platform.
    Creates the directory if it doesn't exist.
    """
    # Get the appropriate base directory for the platform
    if platform.system() == "Darwin":  # macOS
        base_dir = os.path.expanduser("~/Library/Application Support/Oversee")
    elif platform.system() == "Windows":
        base_dir = os.path.join(os.environ.get('APPDATA', ''), 'Oversee')
    else:  # Linux and others
        base_dir = os.path.expanduser("~/.oversee")

    # Create the directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def get_data_subdir(subdir):
    """
    Get a subdirectory within the app data directory.
    Creates the subdirectory if it doesn't exist.
    """
    path = os.path.join(get_app_data_dir(), subdir)
    os.makedirs(path, exist_ok=True)
    return path

def get_camera_data_dir():
    """Get the directory for camera-related data"""
    return get_data_subdir('cameras')

def get_logs_dir():
    """Get the directory for application logs"""
    return get_data_subdir('logs')

def get_cache_dir():
    """Get the directory for application cache"""
    return get_data_subdir('cache')

def get_config_dir():
    """Get the directory for application configuration"""
    return get_data_subdir('config')

def ensure_data_directories():
    """Ensure all required data directories exist"""
    directories = [
        get_camera_data_dir(),
        get_logs_dir(),
        get_cache_dir(),
        get_config_dir()
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def get_database_path(db_name):
    """Get the full path for a database file"""
    return os.path.join(get_camera_data_dir(), db_name)

def get_log_file_path(log_name):
    """Get the full path for a log file"""
    return os.path.join(get_logs_dir(), log_name)

def get_cache_file_path(cache_name):
    """Get the full path for a cache file"""
    return os.path.join(get_cache_dir(), cache_name)

def get_config_file_path(config_name):
    """Get the full path for a configuration file"""
    return os.path.join(get_config_dir(), config_name)

def cleanup_old_data():
    """Clean up old data files if needed"""
    cache_dir = get_cache_dir()
    for item in os.listdir(cache_dir):
        item_path = os.path.join(cache_dir, item)
        try:
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"Error cleaning up {item_path}: {e}")

def is_writable(path):
    """Check if a path is writable"""
    try:
        test_file = os.path.join(path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.unlink(test_file)
        return True
    except:
        return False

def verify_data_access():
    """Verify that the application can write to all required directories"""
    directories = [
        get_camera_data_dir(),
        get_logs_dir(),
        get_cache_dir(),
        get_config_dir()
    ]
    
    for directory in directories:
        if not is_writable(directory):
            raise PermissionError(f"Cannot write to directory: {directory}") 