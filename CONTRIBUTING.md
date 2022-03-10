## Development
This project is managed using [Poetry](https://poetry.eustace.io).

* If you want to take advantage of the default VSCode integration, then first
  configure Poetry to make its virtual environment in the repository:
  ```
  poetry config settings.virtualenvs.in-project true
  ```
* After cloning the repository, activate the tooling:
  ```
  poetry install
  poetry run pre-commit install
  ```
* Run unit tests:
  ```
  poetry run pytest
  ```
* Run integration tests:
  ```
  ./tests/integration.sh
  ```
  [Git Bash](https://git-scm.com) is recommended for Windows.
