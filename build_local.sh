#!/bin/bash

# Local build script for SilverFlag OVERSEE
# This script helps test the PyInstaller build locally

set -e

echo "Building SilverFlag OVERSEE locally..."

# Check if we're on macOS, Windows (Git Bash/WSL), or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    PLATFORM="Windows"
else
    PLATFORM="Linux"
fi

echo "Detected platform: $PLATFORM"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.spec

# Install PyInstaller if not present
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Build based on platform
if [[ "$PLATFORM" == "macOS" ]]; then
    echo "Building for macOS..."
    
    # Create icon if assets exist
    if [ -f "assets/logo.png" ]; then
        echo "Converting icon for macOS..."
        mkdir -p SilverFlagOVERSEE.iconset
        sips -z 16 16 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_16x16.png
        sips -z 32 32 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_16x16@2x.png
        sips -z 32 32 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_32x32.png
        sips -z 64 64 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_32x32@2x.png
        sips -z 128 128 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_128x128.png
        sips -z 256 256 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_128x128@2x.png
        sips -z 256 256 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_256x256.png
        sips -z 512 512 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_256x256@2x.png
        sips -z 512 512 assets/logo.png --out SilverFlagOVERSEE.iconset/icon_512x512.png
        cp assets/logo.png SilverFlagOVERSEE.iconset/icon_512x512@2x.png
        iconutil -c icns SilverFlagOVERSEE.iconset
        echo "Icon created: SilverFlagOVERSEE.icns"
    fi
    
    # Use spec file
    echo "Building using spec file..."
    pyinstaller SilverFlagOVERSEE.spec --distpath dist
    
elif [[ "$PLATFORM" == "Windows" ]]; then
    echo "Building for Windows..."
    
    # Create icon if assets exist
    if [ -f "assets/logo.png" ]; then
        echo "Converting icon for Windows..."
        python -c "
from PIL import Image
import sys
try:
    img = Image.open('assets/logo.png')
    img.save('logo.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print('Icon converted successfully')
except Exception as e:
    print(f'Icon conversion failed: {e}')
"
    fi
    
    # Build with explicit settings
    if [ -f "logo.ico" ]; then
        pyinstaller --onefile --windowed --icon=logo.ico src/main.py --name SilverFlagOVERSEE --distpath dist --add-data "src/data;src/data" --hidden-import settings --paths src
    else
        pyinstaller --onefile --windowed src/main.py --name SilverFlagOVERSEE --distpath dist --add-data "src/data;src/data" --hidden-import settings --paths src
    fi
    
else
    echo "Building for Linux..."
    pyinstaller --onefile --windowed src/main.py --name SilverFlagOVERSEE --distpath dist --add-data "src/data:src/data" --hidden-import settings --paths src
fi

echo "Build complete!"
echo "Output location: dist/"

# List what was created
echo "Created files:"
ls -la dist/ 