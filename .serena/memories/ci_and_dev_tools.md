

### CI and Development Tools

- **GitHub Actions Workflow**: Added a CI workflow to run `black`, `ruff`, `pyright`, and `pytest` on every push and pull request to the `main` branch.
- **Pre-commit Hooks**: Added a `.pre-commit-config.yaml` file to run `black`, `ruff`, and `pyright` before each commit.
- **Development Dependencies**: Updated `pyproject.toml` to include `pytest`, `pytest-asyncio`, `black`, `ruff`, and `pyright` as development dependencies.
- **Basic Test**: Added a basic test file for the `ScryfallClient` to ensure the CI workflow has something to run.

### Commands for CI and Development Tools

- **Install Pre-commit**:
  ```bash
  uv pip install pre-commit
  ```

- **Set Up the Hooks**:
  ```bash
  pre-commit install
  ```

- **Run the Hooks Manually**:
  ```bash
  pre-commit run --all-files
  ```

- **Run Tests**:
  ```bash
  pytest
  ```

- **Run Black**:
  ```bash
  black .
  ```

- **Run Ruff**:
  ```bash
  ruff .
  ```

- **Run Pyright**:
  ```bash
  pyright
  ```

