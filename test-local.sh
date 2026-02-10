#!/bin/bash

echo "Testing OSS Contributions Generator"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3."
    exit 1
fi

echo "Python 3 found"

# Install dependencies
echo "Installing dependencies..."
pip install -q requests

# Set username
if [ -z "$GITHUB_USERNAME" ]; then
    echo ""
    echo "Enter GitHub username:"
    read GITHUB_USERNAME
    export GITHUB_USERNAME
fi

echo ""
echo "Fetching contributions for: $GITHUB_USERNAME"
echo ""

# Run script
python3 update_readme.py

echo ""
echo "Test complete! Check README.md to see contributions."
