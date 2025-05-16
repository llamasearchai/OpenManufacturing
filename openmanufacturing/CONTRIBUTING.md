# Contributing to the OpenManufacturing Package

Thank you for considering contributing to the `openmanufacturing` package! 

Please refer to the main `CONTRIBUTING.md` file at the root of the repository for general guidelines on how to contribute to the OpenManufacturing project.

## Package-Specific Development

- **Code Style**: Follow PEP 8 guidelines. We use `black` for formatting and `isort` for import sorting. Configuration is in `pyproject.toml`.
- **Type Hinting**: Use type hints for all function signatures and variables where appropriate. We use `mypy` for static type checking.
- **Testing**: Write unit tests for new functionality under the `tests/` directory. Ensure all tests pass before submitting a pull request.
- **Dependencies**: Manage dependencies using Poetry. Add any new dependencies to `pyproject.toml`.

## Issues and Pull Requests

- If you find a bug or have a feature request specific to this package, please open an issue on the main project's issue tracker, clearly indicating that it relates to the `openmanufacturing` Python package.
- For pull requests, ensure your changes are well-tested and adhere to the coding standards.
