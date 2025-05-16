#!/bin/bash

# This is a conceptual install script for the openmanufacturing package.
# Actual installation should typically be handled by Poetry or pip.

echo "Installing the OpenManufacturing package..."

# Ensure Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "Poetry could not be found. Please install Poetry first."
    echo "See https://python-poetry.org/docs/#installation"
    exit 1
fi

# Navigate to the package root (assuming this script is in openmanufacturing/scripts/)
cd "$(dirname "$0")/.." || exit

echo "Current directory: $(pwd)"

# Install dependencies using Poetry
if [ -f "pyproject.toml" ] && [ -f "poetry.lock" ]; then
    echo "Found pyproject.toml and poetry.lock. Installing using Poetry..."
    poetry install --no-dev  # Use --no-dev for a production-like install, or remove for dev install
    
    if [ $? -eq 0 ]; then
        echo "OpenManufacturing package dependencies installed successfully via Poetry."
    else
        echo "Poetry installation failed."
        exit 1
    fi
else
    echo "pyproject.toml or poetry.lock not found. Cannot install using Poetry from this script."
    echo "Please ensure you are in the 'openmanufacturing' package directory that contains these files."
    exit 1
fi

echo "Installation script finished."
