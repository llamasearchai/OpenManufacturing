# macOS Deployment Guide

This guide provides instructions for installing and deploying the OpenManufacturing platform on macOS.

## Prerequisites

Before installation, ensure you have the following prerequisites:

1. **macOS 10.15 Catalina or later**
2. **Homebrew** - Package manager for macOS
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. **Python 3.10+**
   ```bash
   brew install python@3.10
   ```
4. **Poetry** - Python dependency management
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
5. **Rust** (for Tauri UI)
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```
6. **Node.js** (for Tauri UI)
   ```bash
   brew install node
   ```
7. **PostgreSQL**
   ```bash
   brew install postgresql@14
   brew services start postgresql@14
   ```
8. **C++ Build Tools**
   ```bash
   brew install cmake boost
   ```

## Installation

Follow these steps to install the OpenManufacturing platform:

1. **Clone the repository**
   ```bash
   git clone https://github.com/openmanufacturing/optical-packaging-platform.git
   cd optical-packaging-platform
   ```

2. **Install Python dependencies**
   ```bash
   poetry install
   ```

3. **Build C++ components**
   ```bash
   mkdir -p build
   cd build
   cmake ..
   make -j$(sysctl -n hw.ncpu)
   cd ..
   ```

4. **Initialize database**
   ```bash
   createdb openmfg
   poetry run alembic upgrade head
   ```

5. **Build Tauri UI**
   ```bash
   cd src/ui
   npm install
   npm run tauri build
   cd ../..
   ```

## Configuration

Configure the platform for macOS:

1. **Create configuration file**
   ```bash
   cp config.example.toml config.toml
   ```

2. **Edit configuration**
   ```bash
   # Set database connection
   DATABASE_URL=postgresql://localhost/openmfg
   
   # Set hardware simulation mode to true for development
   HARDWARE_SIMULATION=true
   
   # Set log level
   LOG_LEVEL=info
   ```

## Running the Platform

There are two ways to run the platform:

### 1. As separate services (recommended for development)

**Start the API server**
```bash
poetry run uvicorn src.api.main:app --reload --port 8000
```

**Start the UI application**
```bash
cd src/ui
npm run tauri dev
```

### 2. As a standalone application

**Run the packaged application**
```bash
open src/ui/target/release/bundle/macos/OpenManufacturing.app
```

## Connecting to Hardware

When connecting to real hardware on macOS, consider:

1. **USB Device Permissions**
   
   For USB motion controllers or cameras, you may need to approve permissions in System Preferences > Security & Privacy > Privacy > Files and Folders.

2. **Serial Port Access**
   
   For serial devices, install the appropriate drivers and ensure your user has permission to access the device:
   ```bash
   ls -l /dev/tty.*
   sudo chown youruser:yourgroup /dev/tty.usbserial-*
   ```

3. **Firewire Cameras**
   
   For Firewire cameras, install the appropriate drivers. Note that newer Macs may require a Thunderbolt to FireWire adapter.

## Troubleshooting

Common issues and solutions:

### Python Path Issues

If you encounter Python import errors:
```bash
export PYTHONPATH=$(pwd):$PYTHONPATH
```

### PostgreSQL Connection Issues

If you encounter database connection errors:
```bash
# Check if PostgreSQL is running
brew services list
# Restart if needed
brew services restart postgresql@14
```

### Library Loading Issues

If C++ libraries fail to load:
```bash
# Set dynamic library path
export DYLD_LIBRARY_PATH=$(pwd)/build/lib:$DYLD_LIBRARY_PATH
```

## Get Help

If you encounter issues specific to macOS deployment:

1. Check the [macOS Issues](https://github.com/openmanufacturing/optical-packaging-platform/labels/platform-macos) on GitHub
2. Post in the [Community Forums](https://community.openmanufacturing.org/c/platform/macos)
3. Review system logs using Console.app for detailed error information
```

## Step 22: Implementation Strategy Summary

```markdown:docs/getting_started/implementation_strategy.md
# Implementation Strategy

This document outlines a recommended approach for implementing the OpenManufacturing platform in your organization.

## Phase 1: Planning & Setup (1-2 weeks)

### 1. Requirement Analysis
- [ ] Identify specific use cases and alignment requirements
- [ ] Document hardware specifications and integration points
- [ ] Define success criteria and performance metrics
- [ ] Assess security and compliance requirements

### 2. Environment Setup
- [ ] Set up development environment with simulation mode
- [ ] Set up continuous integration pipeline
- [ ] Establish Git workflow and branching strategy
- [ ] Create test datasets for development

### 3. Team Onboarding
- [ ] Familiarize team with platform architecture
- [ ] Assign roles and responsibilities
- [ ] Set up communication channels
- [ ] Schedule regular progress reviews

## Phase 2: Core Implementation (3-4 weeks)

### 1. Hardware Abstraction Layer
- [ ] Implement hardware interfaces for your specific equipment
- [ ] Develop and test motion controller drivers
- [ ] Implement optical power measurement integration
- [ ] Create a hardware calibration utility

### 2. Vision System Integration
- [ ] Configure and calibrate cameras
- [ ] Implement fiber-to-chip detection algorithms
- [ ] Optimize image processing for your specific components
- [ ] Create visualization tools for alignment monitoring

### 3. Alignment Engine Customization
- [ ] Fine-tune alignment parameters for your devices
- [ ] Implement custom alignment strategies if needed
- [ ] Validate alignment performance with test fixtures
- [ ] Optimize for speed and reliability

## Phase 3: Process Implementation (3-4 weeks)

### 1. Workflow Definition
- [ ] Define standard alignment workflows
- [ ] Create custom workflow templates for your products
- [ ] Implement error handling and recovery procedures
- [ ] Document process flows and decision points

### 2. Data Management
- [ ] Set up database schema for your tracking requirements
- [ ] Implement data backup and retention policies
- [ ] Create data visualization and reporting tools
- [ ] Implement process metrics collection

### 3. Integration with Existing Systems
- [ ] Connect to ERP/MES systems if applicable
- [ ] Implement inventory tracking integration
- [ ] Set up user authentication and authorization
- [ ] Create APIs for external system access

## Phase 4: Testing & Validation (2-3 weeks)

### 1. Unit Testing
- [ ] Develop comprehensive test suite for all components
- [ ] Automate tests in CI/CD pipeline
- [ ] Document test coverage and results
- [ ] Address any identified issues

### 2. Integration Testing
- [ ] Test end-to-end workflows
- [ ] Validate hardware integration
- [ ] Stress test with realistic workloads
- [ ] Document system performance metrics

### 3. User Acceptance Testing
- [ ] Train operators on system usage
- [ ] Conduct supervised test runs
- [ ] Collect feedback and implement improvements
- [ ] Validate against success criteria

## Phase 5: Deployment & Monitoring (1-2 weeks)

### 1. Production Deployment
- [ ] Set up production environment
- [ ] Migrate configuration and data
- [ ] Deploy to target systems
- [ ] Conduct final validation

### 2. Documentation & Training
- [ ] Complete user documentation
- [ ] Conduct operator training sessions
- [ ] Create troubleshooting guides
- [ ] Document maintenance procedures

### 3. Monitoring & Support
- [ ] Implement system monitoring
- [ ] Set up alerting for critical issues
- [ ] Establish support procedures
- [ ] Schedule regular system reviews

## Key Considerations for MacOS Deployment

When deploying on MacOS, pay special attention to:

1. **Hardware Compatibility**
   - Ensure all hardware has MacOS-compatible drivers
   - Test USB/serial communications thoroughly
   - Consider virtualization for Windows-only hardware components

2. **Performance Optimization**
   - Optimize C++ code for Apple Silicon if applicable
   - Monitor memory usage closely
   - Adjust thread management for MacOS scheduler

3. **UI Integration**
   - Follow MacOS UI guidelines for native feel
   - Test across multiple MacOS versions
   - Implement proper permission handling for hardware access

4. **Deployment Strategy**
   - Consider using signed packages for distribution
   - Implement auto-updates via Sparkle framework
   - Document MacOS-specific installation requirements

## Timeline and Resources

A typical implementation with one full-time engineer and one part-time domain expert:

| Phase | Duration | Primary Activities |
|-------|----------|-------------------|
| Planning & Setup | 1-2 weeks | Requirements, environment setup |
| Core Implementation | 3-4 weeks | Hardware integration, alignment engine |
| Process Implementation | 3-4 weeks | Workflows, data management