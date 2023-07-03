import sys
from pathlib import Path

from .._impl.codegen import FakeFs, generate, load_tl_file

HELP = f"""
USAGE:
    python -m {__package__} <TL_FILE> <OUT_DIR>

ARGS:
    <TL_FILE>
            The path to the `.tl' file to generate Python code from.

    <OUT_DIR>
            The directory where the generated code will be written to.
""".strip()


def main() -> None:
    if len(sys.argv) != 3:
        print(HELP)
        sys.exit(1)

    tl, out = sys.argv[1:]
    fs = FakeFs()
    generate(fs, load_tl_file(tl))
    fs.materialize(Path(out))


if __name__ == "__main__":
    main()
