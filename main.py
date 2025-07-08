import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / 'src'))

if __name__ == "__main__":
    # Import and run the main initialization from src/main.py
    from main import init
    init() 