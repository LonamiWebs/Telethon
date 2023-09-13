"""
Sort imports and format code.
"""
import subprocess
import sys

BLACK_IGNORE = r"tl/(abcs|functions|types)/\w+.py"


def run(*args: str) -> int:
    return subprocess.run((sys.executable, "-m", *args)).returncode


def main() -> None:
    exit(
        run("isort", ".", "--profile", "black", "--gitignore")
        or run("black", ".", "--extend-exclude", BLACK_IGNORE)
    )


if __name__ == "__main__":
    main()
