"""
Run `telethon_generator.codegen` on both `api.tl` and `mtproto.tl` to output
corresponding Python code in the default directories under the `client/`.
"""
import subprocess
import sys

GENERATOR = "telethon_generator.codegen"
GEN_ROOT = "client/src/telethon/_impl"
TL_ROOT = "generator/tl"


def run(*args: str) -> int:
    return subprocess.run((sys.executable, "-m", *args)).returncode


def main() -> None:
    exit(
        run(GENERATOR, f"{TL_ROOT}/api.tl", f"{GEN_ROOT}/tl")
        or run(GENERATOR, f"{TL_ROOT}/mtproto.tl", f"{GEN_ROOT}/tl/mtproto")
    )


if __name__ == "__main__":
    main()
