import weakref
from pathlib import Path


class FakeFs:
    def __init__(self) -> None:
        self._files: dict[Path, bytearray] = {}

    def open(self, path: Path) -> "SourceWriter":
        return SourceWriter(self, path)

    def write(self, path: Path, line: str) -> None:
        file = self._files.get(path)
        if file is None:
            self._files[path] = file = bytearray()
        file += line.encode("utf-8")

    def materialize(self, root: Path) -> None:
        for stem, data in self._files.items():
            path = root / stem
            path.parent.mkdir(exist_ok=True)
            with path.open("wb") as fd:
                fd.write(data)

    def __contains__(self, path: Path) -> bool:
        return path in self._files


class SourceWriter:
    def __init__(self, fs: FakeFs, path: Path) -> None:
        self._fs = weakref.ref(fs)
        self._path = path
        self._indent = ""

    def write(self, string: str) -> None:
        if fs := self._fs():
            fs.write(self._path, f"{self._indent}{string}\n")

    def indent(self, n: int = 1) -> None:
        self._indent += "  " * n

    def dedent(self, n: int = 1) -> None:
        self._indent = self._indent[: -2 * n]
