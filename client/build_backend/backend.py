import sys
from pathlib import Path
from typing import Any, Optional

from setuptools import build_meta as _orig
from setuptools.build_meta import *  # noqa: F403 # pyright: ignore [reportWildcardImportFromLibrary]


def gen_types_if_needed() -> None:
    tl_root = Path("src/telethon/_impl/tl")
    layer_py = tl_root / "layer.py"
    mtproto_root = tl_root / "mtproto"

    generator_path = "../generator/src"
    api_tl = Path("../generator/tl/api.tl")
    mtproto_tl = Path("../generator/tl/mtproto.tl")

    if not layer_py.exists():
        print(layer_py, "is missing; attempting to generate types", file=sys.stderr)

        # Import generator and clean-up path
        sys.path.append(generator_path)
        import telethon_generator as gen

        sys.path.remove(generator_path)

        # api.tl
        fs = gen.codegen.FakeFs()
        gen.codegen.generate(fs, gen.tl_parser.load_tl_file(api_tl))
        fs.materialize(tl_root)
        print("written api.tl files:", tl_root, file=sys.stderr)

        # mtproto.tl
        fs = gen.codegen.FakeFs()
        gen.codegen.generate(fs, gen.tl_parser.load_tl_file(mtproto_tl))
        fs.materialize(mtproto_root)
        print("written mtproto.tl files:", mtproto_root, file=sys.stderr)


def build_wheel(  # type: ignore [no-redef]
    wheel_directory: str,
    config_settings: Optional[dict[Any, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str:
    gen_types_if_needed()
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(  # type: ignore [no-redef]
    sdist_directory: str, config_settings: Optional[dict[Any, Any]] = None
) -> str:
    gen_types_if_needed()
    return _orig.build_sdist(sdist_directory, config_settings)


def build_editable(  # type: ignore [no-redef]
    wheel_directory: str,
    config_settings: Optional[dict[Any, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str:
    gen_types_if_needed()
    return _orig.build_editable(wheel_directory, config_settings, metadata_directory)
