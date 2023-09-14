"""
Check formatting, type-check and run offline tests.
"""
import subprocess
import sys
import tempfile

BLACK_IGNORE = r"tl/(abcs|functions|types)/\w+.py"


def run(*args: str) -> int:
    return subprocess.run((sys.executable, "-m", *args)).returncode


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit(
            run("isort", ".", "-c", "--profile", "black", "--gitignore")
            or run("black", ".", "--check", "--extend-exclude", BLACK_IGNORE)
            or run("mypy", "--strict", ".")
            or run("sphinx", "-M", "dummy", "client/doc", tmp_dir, "-n", "-W")
            or run("pytest", ".", "-m", "not net")
        )


if __name__ == "__main__":
    main()
