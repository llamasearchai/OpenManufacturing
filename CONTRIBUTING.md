# Contributing to OpenManufacturing

We welcome contributions to the OpenManufacturing platform! Thank you for your interest and support.

Please follow these guidelines to help us manage the contribution process.

## Code of Conduct

This project and everyone participating in it is governed by a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. (Note: `CODE_OF_CONDUCT.md` needs to be created).

## Development Workflow

1.  **Fork the Repository**: Start by forking the main OpenManufacturing repository to your GitHub account.
2.  **Clone Your Fork**: Clone your forked repository to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/OpenManufacturing.git
    cd OpenManufacturing
    ```
3.  **Create a Branch**: Create a new branch for your feature or bug fix.
    ```bash
    git checkout -b feature/your-feature-name
    # or
    git checkout -b fix/your-bug-fix
    ```
4.  **Set Up Environment**: Follow the installation and setup instructions in the main `README.md` to get your development environment ready. Ensure you can run the project and its tests.
5.  **Make Changes**: Implement your feature or bug fix. Adhere to the coding standards outlined below.
6.  **Test Your Changes**: 
    *   Write new unit tests for any new functionality.
    *   Ensure all existing and new tests pass.
    *   Run linters and formatters (`black`, `isort`, etc. as configured in `pyproject.toml`).
7.  **Commit Your Changes**: Commit your changes with clear and descriptive commit messages.
    ```bash
    git add .
    git commit -m "feat: Implement X feature" 
    # or 
    git commit -m "fix: Resolve Y bug in Z component"
    ```
    (Consider using [Conventional Commits](https://www.conventionalcommits.org/) format.)
8.  **Push to Your Fork**: Push your changes to your forked repository.
    ```bash
    git push origin feature/your-feature-name
    ```
9.  **Open a Pull Request (PR)**: 
    *   Navigate to the original OpenManufacturing repository and open a new Pull Request from your forked branch.
    *   Provide a clear title and description for your PR, explaining the changes and referencing any related issues.
    *   Ensure your PR passes all automated checks (CI pipeline).
10. **Code Review**: Your PR will be reviewed by maintainers. Be prepared to discuss your changes and make further adjustments if requested.

## Coding Standards

*   **Python**: 
    *   Follow PEP 8 guidelines.
    *   Use `black` for code formatting and `isort` for import sorting. Configuration is in `openmanufacturing/pyproject.toml`.
    *   Write type hints for all function signatures and variables. Use `mypy` for static type checking.
*   **C++**: 
    *   Follow established C++ coding conventions (e.g., Google C++ Style Guide or similar, to be decided and documented).
    *   Use `clang-format` if adopted for formatting.
*   **General**: 
    *   Write clear and concise code.
    *   Comment complex or non-obvious parts of the code.
    *   Ensure code is well-documented, both in-code and in the `/docs` directory where appropriate.

## Testing Requirements

*   All new features must include corresponding unit tests.
*   Bug fixes should include regression tests to prevent the issue from recurring.
*   Integration tests should be added for interactions between components.
*   Aim for high test coverage. Current coverage can be checked via CI reports.

## Documentation Standards

*   Update existing documentation or add new documentation as needed for your changes.
*   This includes README files, API documentation (e.g., via Sphinx for Python), and user guides in the `/docs` directory.

## Issue Tracker

*   Use the GitHub issue tracker to report bugs, suggest features, or discuss improvements.
*   Before opening a new issue, please check if a similar one already exists.

Thank you for contributing! 