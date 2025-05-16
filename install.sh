#!/bin/bash

set -e

echo "Beginning to install the program..."

# Check dependencies
for cmd in wget curl pip3; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Create a temporary working directory
TMPDIR=$(mktemp -d -t oversee-install-XXXXXXXXXX)

echo "Using temp directory: $TMPDIR"

# Download requirements.txt
REQ_URL="https://raw.githubusercontent.com/YetAnotherNotHacking/oversee/main/requirements.txt"
echo "Downloading requirements.txt..."
if ! wget -q "$REQ_URL" -O "$TMPDIR/requirements.txt"; then
    echo "Failed to download requirements.txt"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
if ! pip3 install -r "$TMPDIR/requirements.txt"; then
    echo "pip3 failed to install requirements"
    exit 1
fi

# Get latest release binary URL containing the word "funny"
echo "Fetching latest release binary..."
BIN_URL=$(curl -s https://api.github.com/repos/YetAnotherNotHacking/oversee/releases/latest \
    | grep "browser_download_url" \
    | grep "funny" \
    | cut -d : -f 2- \
    | tr -d ' "')

if [ -z "$BIN_URL" ]; then
    echo "Could not find a suitable binary URL with 'funny' in its name"
    exit 1
fi

echo "Downloading binary from: $BIN_URL"
if ! wget -q "$BIN_URL" -O "$TMPDIR/funny"; then
    echo "Failed to download the binary"
    exit 1
fi

# Ensure the binary is executable
chmod +x "$TMPDIR/funny"

# Move to /usr/bin/oversee with sudo
echo "Installing binary to /usr/bin/oversee..."
if ! sudo cp "$TMPDIR/funny" /usr/bin/oversee; then
    echo "Failed to copy binary to /usr/bin"
    exit 1
fi

echo "Installation complete. You can now run 'oversee'."
