## Development
This project is managed using [Poetry](https://poetry.eustace.io).

* If you want to take advantage of the default VSCode integration, then first
  configure Poetry to make its virtual environment in the repository:
  ```
  poetry config virtualenvs.in-project true
  ```
* After cloning the repository, activate the tooling:
  ```
  pipx install invoke
  poetry install --extras plugin
  poetry run pre-commit install
  ```

Commands defined in `tasks.py`:

* Load the main `poetry-dynamic-versioning` package:
  ```
  invoke patch
  ```
* Load the deprecated `poetry-dynamic-versioning-plugin` package:
  ```
  invoke plugin
  ```
* Build the currently loaded package:
  ```
  invoke build
  ```
* Run tests for the currently loaded package:
  ```
  invoke test
  ```
  [Git Bash](https://git-scm.com) is recommended for Windows.
