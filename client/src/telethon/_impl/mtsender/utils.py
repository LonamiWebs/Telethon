import asyncio
from asyncio import Task
from typing import Set

_background_tasks: Set[Task] = set()


def store_task(task: Task) -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def cancel_tasks() -> None:
    for task in _background_tasks:
        task.cancel()
    await asyncio.wait(_background_tasks)
