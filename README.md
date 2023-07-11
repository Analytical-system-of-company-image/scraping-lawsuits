# scraping lawsuits
Subsystem for parsing lawsuits
## Project structure

## How to dev
```
poetry shell
poetry install
```

***
```
├── debug.py
├── parsing_lawsuits
│   └── python_callables.py - core functions for Airflow
├── poetry.lock
├── pyproject.toml
└── README.md

```

## How to public to Pypi
First you need create api on pypi

```bash
poetry config pypi-token.pypi $(cat .token)
poetry publish --build
```
