#!/bin/bash
# Script to switch between original and new Docker configurations

# Check if we need to switch to new or original config
if [ "$1" == "new" ]; then
  echo "Switching to new Docker configuration..."
  cp Dockerfile.new Dockerfile
  cp docker-compose.yml.new docker-compose.yml
  echo "Done! New Docker configuration is now active."
elif [ "$1" == "original" ]; then
  echo "Switching to original Docker configuration..."
  cp Dockerfile.original Dockerfile
  cp docker-compose.yml.original docker-compose.yml
  echo "Done! Original Docker configuration is now active."
else
  echo "Usage: $0 [new|original]"
  echo "  new      - Use the new Docker configuration"
  echo "  original - Use the original Docker configuration"
  exit 1
fi 