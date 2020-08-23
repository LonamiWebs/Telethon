import pytest

from telethon import TelegramClient, events, types, utils


def get_client():
    return TelegramClient(None, 1, '1')


def get_user_456():
    return types.User(
        id=456,
        access_hash=789,
        first_name='User 123'
    )


@pytest.mark.asyncio
async def test_get_input_users_no_action_message_no_entities():
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())

    assert await event.get_input_users() == []


@pytest.mark.asyncio
async def test_get_input_users_no_action_message():
    user = get_user_456()
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())
    event._entities[user.id] = user

    assert await event.get_input_users() == [utils.get_input_peer(user)]


@pytest.mark.asyncio
async def test_get_users_no_action_message_no_entities():
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())

    assert await event.get_users() == []


@pytest.mark.asyncio
async def test_get_users_no_action_message():
    user = get_user_456()
    event = events.ChatAction.build(types.UpdateChatParticipantDelete(
        chat_id=123,
        user_id=456,
        version=1
    ))
    event._set_client(get_client())
    event._entities[user.id] = user

    assert await event.get_users() == [user]
