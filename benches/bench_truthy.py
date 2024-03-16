import timeit
from typing import Type

ITERATIONS = 100000000
DATA = 42


def overhead(n: int) -> None:
    n = n


def strategy_bool(n: int) -> bool:
    return bool(n)


def strategy_bool_cache(n: int, _bool: Type[bool] = bool) -> bool:
    return _bool(n)


def strategy_non_zero(n: int) -> bool:
    return n != 0


def strategy_not_not(n: int) -> bool:
    return not not n


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
