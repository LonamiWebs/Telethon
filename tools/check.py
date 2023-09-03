"""
Sort imports, format code, type-check and run offline tests.
"""
import subprocess
import sys


def run(*args: str) -> int:
    return subprocess.run((sys.executable, "-m", *args)).returncode


def main() -> None:
    exit(
        run("isort", ".", "--profile", "black", "--gitignore")
        or run("black", ".", "--extend-exclude", r"tl/(abcs|functions|types)/\w+.py")
        or run("mypy", "--strict", ".")
        or run("pytest", ".", "-m", "not net")
    )


if __name__ == "__main__":
    main()
