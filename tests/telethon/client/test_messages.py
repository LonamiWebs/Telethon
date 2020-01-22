import inspect

import pytest

from telethon import TelegramClient


@pytest.mark.asyncio
async def test_send_message_with_file_forwards_args():
    arguments = {}
    sentinel = object()

    for value, name in enumerate(inspect.signature(TelegramClient.send_message).parameters):
        if name in {'self', 'entity', 'file'}:
            continue  # positional

        if name in {'message'}:
            continue  # renamed

        if name in {'link_preview'}:
            continue  # make no sense in send_file

        arguments[name] = value

    class MockedClient(TelegramClient):
        # noinspection PyMissingConstructor
        def __init__(self):
            pass

        async def send_file(self, entity, file, **kwargs):
            assert entity == 'a'
            assert file == 'b'
            for k, v in arguments.items():
                assert k in kwargs
                assert kwargs[k] == v

            return sentinel

    client = MockedClient()
    assert (await client.send_message('a', file='b', **arguments)) == sentinel
