import datetime
import io
import struct
import timeit
from collections.abc import Iterator
from typing import Any

from .data_codegen import DATA, Obj

ITERATIONS = 50000


def serialize_builtin(value: Any) -> bytes:
    if value is None:
        return b""
    elif isinstance(value, bytes):
        return value
    elif isinstance(value, str):
        return value.encode("utf-8")
    elif isinstance(value, int):
        return struct.pack("<i" if value < 2**32 else "<q", value)
    elif isinstance(value, datetime.datetime):
        return struct.pack("<i", int(value.timestamp()))
    else:
        raise RuntimeError(f"not a builtin type: {type(value)}")


def overhead(obj: Obj) -> None:
    x: Any
    for v in obj.__dict__.values():
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, Obj):
                overhead(x)
            else:
                serialize_builtin(x)


def strategy_concat(obj: Obj) -> bytes:
    x: Any
    res = b""
    for v in obj.__dict__.values():
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, Obj):
                res += strategy_concat(x)
            else:
                res += serialize_builtin(x)
    return res


def strategy_append(obj: Obj) -> bytes:
    x: Any
    res = bytearray()
    for v in obj.__dict__.values():
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, Obj):
                res += strategy_append(x)
            else:
                res += serialize_builtin(x)
    return bytes(res)


def strategy_append_reuse(obj: Obj) -> bytes:
    def do_append(o: Obj, res: bytearray) -> None:
        x: Any
        for v in o.__dict__.values():
            for x in v if isinstance(v, list) else [v]:
                if isinstance(x, Obj):
                    do_append(x, res)
                else:
                    res += serialize_builtin(x)

    buffer = bytearray()
    do_append(obj, buffer)
    return bytes(buffer)


def strategy_join(obj: Obj) -> bytes:
    def iterator() -> Iterator[bytes]:
        x: Any
        for v in obj.__dict__.values():
            for x in v if isinstance(v, list) else [v]:
                yield strategy_join(x) if isinstance(x, Obj) else serialize_builtin(x)

    return b"".join(iterator())


def strategy_join_flat(obj: Obj) -> bytes:
    def flatten(o: Obj) -> Iterator[bytes]:
        x: Any
        for v in o.__dict__.values():
            for x in v if isinstance(v, list) else [v]:
                if isinstance(x, Obj):
                    yield from flatten(x)
                else:
                    yield serialize_builtin(x)

    return b"".join(flatten(obj))


def strategy_write(obj: Obj) -> bytes:
    def do_write(o: Obj, buffer: io.BytesIO) -> None:
        x: Any
        for v in o.__dict__.values():
            for x in v if isinstance(v, list) else [v]:
                if isinstance(x, Obj):
                    do_write(x, buffer)
                else:
                    buffer.write(serialize_builtin(x))

    buffer = io.BytesIO()
    do_write(obj, buffer)
    return buffer.getvalue()


def main() -> None:
    strategies = [
        v
        for _, v in sorted(
            ((k, v) for k, v in globals().items() if k.startswith("strategy_")),
            key=lambda t: t[0],
        )
    ]
    for a, b in zip(strategies[:-1], strategies[1:]):
        if a(DATA) != b(DATA):
            raise ValueError("strategies produce different output")

    print("measuring overhead...", end="", flush=True)
    overhead_duration = timeit.timeit(
        "strategy(DATA)",
        number=ITERATIONS,
        globals={"strategy": overhead, "DATA": DATA},
    )
    print(f" {overhead_duration:.04f}s")

    for strategy in strategies:
        duration = timeit.timeit(
            "strategy(DATA)",
            number=ITERATIONS,
            globals={"strategy": strategy, "DATA": DATA},
        )
        print(f"{strategy.__name__:.>30} took {duration - overhead_duration:.04f}s")


if __name__ == "__main__":
    main()
