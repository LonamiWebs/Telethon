"""
Run `telethon_generator.codegen` on both `api.tl` and `mtproto.tl` to output
corresponding Python code in the default directories under the `client/`.
"""
import subprocess
import sys

GENERATOR = "telethon_generator.codegen"
ROOT = "client/src/telethon/_impl"


def run(*args: str) -> int:
    return subprocess.run((sys.executable, "-m", *args)).returncode


def main() -> None:
    exit(
        run(GENERATOR, "api.tl", f"{ROOT}/tl")
        or run(GENERATOR, "mtproto.tl", f"{ROOT}/tl/mtproto")
    )


if __name__ == "__main__":
    main()
