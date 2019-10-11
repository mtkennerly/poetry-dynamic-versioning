## Development
This project is managed using [Poetry](https://poetry.eustace.io).
Development requires Python 3.6+ because of [Black](https://github.com/ambv/black).

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
  poetry run pytest --cov
  poetry run tox
  ```
* Run integration tests:
  ```
  ./tests/integration.sh
  ```
  [Git Bash](https://git-scm.com) is recommended for Windows.
