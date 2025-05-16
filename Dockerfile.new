FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY src/ /app/src/
COPY run.py /app/
COPY setup.py /app/

# Install the package in development mode
RUN pip install -e .

# Set Python path to include the project root
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the API server
CMD ["python", "run.py"] 