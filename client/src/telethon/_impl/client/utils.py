import time

_last_id = 0


def generate_random_id() -> int:
    global _last_id
    if _last_id == 0:
        _last_id = int(time.time() * 1e9)
    _last_id += 1
    return _last_id
