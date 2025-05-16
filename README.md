# OpenManufacturing Platform

Advanced optical packaging and assembly platform for manufacturing automation.

## Features

- Complete workflow engine for manufacturing processes
- Optical alignment and calibration
- Hardware device management and control
- Computer vision integration for quality assurance
- Modern React/Tauri desktop application UI
- Full REST API for integrations
- Monitoring with Prometheus and Grafana
- Docker-based deployment

## Installation

### Method 1: Using pip

```bash
# Clone the repository
git clone https://github.com/llamasearchai/OpenManufacturing.git
cd OpenManufacturing

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .

# Run the server
python run.py
```

### Method 2: Using conda

```bash
# Clone the repository
git clone https://github.com/llamasearchai/OpenManufacturing.git
cd OpenManufacturing

# Create and activate conda environment
conda env create -f environment.yml
conda activate openmanufacturing

# Install the package in development mode
pip install -e .

# Run the server
python run.py
```

### Method 3: Using Docker

We provide Docker configurations for containerized deployment.

#### Building and running locally

```bash
# Clone the repository
git clone https://github.com/llamasearchai/OpenManufacturing.git
cd OpenManufacturing

# Build the Docker image
docker build -t openmanufacturing -f Dockerfile.new .

# Run the container
docker run -p 8000:8000 openmanufacturing
```

#### Using Docker Compose

```bash
# Start all services (API, PostgreSQL, Redis, Prometheus, Grafana)
docker-compose -f docker-compose.yml.new up -d

# View logs
docker-compose -f docker-compose.yml.new logs -f api

# Stop all services
docker-compose -f docker-compose.yml.new down
```

#### Using pre-built images

Pre-built Docker images are available on Docker Hub:

```bash
# Pull the latest image
docker pull llamasearch/openmanufacturing:latest

# Run the container
docker run -p 8000:8000 llamasearch/openmanufacturing:latest
```

## Project Structure

```
OpenManufacturing/
├── src/                    # Source code
│   ├── api/                # REST API implementation
│   │   ├── routes/         # API endpoints
│   ├── core/               # Core business logic
│   │   ├── alignment/      # Optical alignment algorithms
│   │   ├── database/       # Database models and sessions
│   │   ├── hardware/       # Hardware control interfaces
│   │   ├── process/        # Process management
│   │   └── vision/         # Computer vision modules
│   ├── integrations/       # External integrations
│   └── ui/                 # User interface (React/Tauri)
├── tests/                  # Test suite
│   ├── integration/        # Integration tests
│   └── unit/               # Unit tests
├── docs/                   # Documentation
├── monitoring/             # Prometheus and Grafana configs
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose configuration
├── requirements.txt        # Python dependencies
└── environment.yml         # Conda environment
```

## API Endpoints

The OpenManufacturing platform exposes the following REST API endpoints:

- `/api/auth` - Authentication and user management
- `/api/process` - Process instance management
- `/api/workflow` - Workflow template management
- `/api/alignment` - Alignment services
- `/api/devices` - Device management

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/api/routes/test_process.py

# Run with coverage
pytest --cov=src
```

### Building the UI

```bash
cd src/ui
npm install
npm run build
```

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- This project builds on the work of many open source libraries and tools.
- Special thanks to the optical manufacturing community for feedback and testing.
