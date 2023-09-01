isort . --profile black --gitignore
black . --extend-exclude "tl/(abcs|functions|types)/\w+.py"
mypy --strict .
pytest . -m "not net"
