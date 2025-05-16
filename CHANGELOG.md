# Changelog

All notable changes to the OpenManufacturing project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and foundational components for optical packaging automation.
- Core Python package `openmanufacturing` setup with Poetry.
- Root `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`.
- C++ alignment module structure with `CMakeLists.txt`.
- Docker configuration (`Dockerfile`, `docker-compose.yml`).
- GitHub Actions CI workflow (`.github/workflows/ci.yml`).
- Basic Tauri UI setup.

### Changed
- Reorganized Python package structure to `openmanufacturing/src/openmanufacturing` for proper namespacing.

### Fixed
- Placeholder for future fixes.

## [0.1.0] - YYYY-MM-DD
*(Placeholder for the first conceptual release based on current implemented features)*

### Added
- Detailed project `README.md` outlining architecture, components, and setup.
- MIT `LICENSE` for the project.
- `CONTRIBUTING.md` with development workflow and coding standards.
- Initial `CHANGELOG.md` for tracking project versions.
- `openmanufacturing` Python package with `pyproject.toml` including:
    - FastAPI for API layer.
    - SQLAlchemy for database interaction.
    - Pydantic for data validation.
    - Core modules for alignment, process management, vision, hardware, database.
- C++ `fast_alignment` library with `CMakeLists.txt` for build.
    - `fast_align.h` and `fast_align.cpp` implementing gradient descent and spiral search.
- Docker support:
    - `Dockerfile` for building the application image.
    - `docker-compose.yml` for multi-service local deployment (API, DB, Redis, Prometheus, Grafana).
- GitHub Actions CI (`ci.yml`):
    - Python linting, type checking, formatting checks.
    - Pytest execution with coverage reporting.
    - Docker image build and push (conditional on main branch).
- Tauri UI structure with `tauri.conf.json` and example `AlignmentDashboard.tsx` component.
- Example unit tests for `AlignmentEngine`.
- Initial documentation structure in `docs/` and example content in `openmanufacturing/docs/index.md`.


</rewritten_file> 