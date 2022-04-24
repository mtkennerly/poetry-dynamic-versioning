## Development
This project is managed using [Poetry](https://poetry.eustace.io).

* If you want to take advantage of the default VSCode integration, then first
  configure Poetry to make its virtual environment in the repository:
  ```
  poetry config virtualenvs.in-project true
  ```
* After cloning the repository, activate the tooling:
  ```
  pip install invoke
  poetry install
  poetry run pre-commit install
  ```

Commands defined in `tasks.py`:

* Load the patch-based `poetry-dynamic-versioning` package:
  ```
  invoke patch
  ```
* Load the plugin-based `poetry-dynamic-versioning-plugin` package:
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
