#!/bin/bash
# Script to install all dependencies

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing the package in development mode..."
pip install -e .

echo "Creating necessary directories..."
mkdir -p config

echo "All dependencies installed successfully!"
echo "Run the application with: python run.py" 