"""
Run `sphinx-build` to create HTML documentation and detect errors.
"""
import subprocess
import sys


def run(*args: str) -> int:
    return subprocess.run((sys.executable, "-m", *args)).returncode


def main() -> None:
    exit(run("sphinx", "-n", "client/doc", "dist-doc"))


if __name__ == "__main__":
    main()
