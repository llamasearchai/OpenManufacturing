#!/bin/bash

# Docker Hub Credentials
DOCKER_USERNAME="your_username" # Replace with your Docker Hub username
DOCKER_PASSWORD="your_password" # Replace with your Docker Hub password or API token

# Log in to Docker Hub
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

if [ $? -eq 0 ]; then
  echo "Docker login successful."
else
  echo "Docker login failed."
  exit 1
fi 