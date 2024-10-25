import inspect
from unittest import mock
from unittest.mock import MagicMock

import pytest

from telethon import TelegramClient
from telethon.client import MessageMethods
from telethon.tl.types import PeerChat, MessageMediaDocument, Message, MessageEntityBold


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


class TestMessageMethods:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'formatting_entities',
        ([MessageEntityBold(offset=0, length=0)], None)
    )
    async def test_send_msg_and_file(self, formatting_entities):
        async def async_func(result): # AsyncMock was added only in 3.8
            return result
        msg_methods = MessageMethods()
        expected_result = Message(
            id=0, peer_id=PeerChat(chat_id=0), message='', date=None,
        )
        entity = 'test_entity'
        message = Message(
            id=1, peer_id=PeerChat(chat_id=0), message='expected_caption', date=None,
            entities=[MessageEntityBold(offset=9, length=9)],
        )
        media_file = MessageMediaDocument()

        with mock.patch.object(
            target=MessageMethods, attribute='send_file',
            new=MagicMock(return_value=async_func(expected_result)), create=True,
        ) as mock_obj:
            result = await msg_methods.send_message(
                entity=entity, message=message, file=media_file,
                formatting_entities=formatting_entities,
            )
            mock_obj.assert_called_once_with(
                entity, media_file, caption=message.message,
                formatting_entities=formatting_entities or message.entities,
                reply_to=None, silent=None, attributes=None, parse_mode=(),
                force_document=False, thumb=None, buttons=None,
                clear_draft=False, schedule=None, supports_streaming=False,
                comment_to=None, background=None, nosound_video=None,
            )
            assert result == expected_result
