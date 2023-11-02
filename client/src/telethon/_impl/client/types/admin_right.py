from __future__ import annotations

from enum import Enum
from typing import Set

from ...tl import abcs, types


class AdminRight(Enum):
    """
    A right that can be granted to a chat's administrator.

    .. note::

        The specific values of the enumeration are not covered by `semver <https://semver.org/>`_.
        They also may do nothing in future updates if Telegram decides to change them.
    """

    CHANGE_INFO = "change_info"
    """Allows editing the description in a group or channel."""

    POST_MESSAGES = "post_messages"
    """Allows sending messages in a broadcast channel."""

    EDIT_MESSAGES = "edit_messages"
    """Allows editing messages in a group or channel."""

    DELETE_MESSAGES = "delete_messages"
    """Allows deleting messages in a group or channel."""

    BAN_USERS = "ban_users"
    """Allows setting the banned rights of other users in a group or channel."""

    INVITE_USERS = "invite_users"
    """Allows inviting other users to the group or channel."""

    PIN_MESSAGES = "pin_messages"
    """Allows pinning a message to the group or channel."""

    MANAGE_ADMINS = "add_admins"
    """Allows setting the same or less administrator rights to other users in the group or channel."""

    REMAIN_ANONYMOUS = "anonymous"
    """Allows the administrator to remain anonymous."""

    MANAGE_CALLS = "manage_call"
    """Allows managing group or channel calls."""

    OTHER = "other"
    """Unspecified."""

    MANAGE_TOPICS = "manage_topics"
    """Allows managing the topics in a group."""

    POST_STORIES = "post_stories"
    """Allows posting stories in a channel."""

    EDIT_STORIES = "edit_stories"
    """Allows editing stories in a channel."""

    DELETE_STORIES = "delete_stories"
    """Allows deleting stories in a channel."""

    @classmethod
    def _from_raw(cls, rights: abcs.ChatAdminRights) -> Set[AdminRight]:
        assert isinstance(rights, types.ChatAdminRights)
        all_rights = (
            cls.CHANGE_INFO if rights.change_info else None,
            cls.POST_MESSAGES if rights.post_messages else None,
            cls.EDIT_MESSAGES if rights.edit_messages else None,
            cls.DELETE_MESSAGES if rights.delete_messages else None,
            cls.BAN_USERS if rights.ban_users else None,
            cls.INVITE_USERS if rights.invite_users else None,
            cls.PIN_MESSAGES if rights.pin_messages else None,
            cls.MANAGE_ADMINS if rights.add_admins else None,
            cls.REMAIN_ANONYMOUS if rights.anonymous else None,
            cls.MANAGE_CALLS if rights.manage_call else None,
            cls.OTHER if rights.other else None,
            cls.MANAGE_TOPICS if rights.manage_topics else None,
            cls.POST_STORIES if rights.post_stories else None,
            cls.EDIT_STORIES if rights.edit_stories else None,
            cls.DELETE_STORIES if rights.delete_stories else None,
        )
        return set(filter(None, iter(all_rights)))

    @classmethod
    def _chat_rights(cls) -> Set[AdminRight]:
        return {
            cls.CHANGE_INFO,
            cls.POST_MESSAGES,
            cls.EDIT_MESSAGES,
            cls.DELETE_MESSAGES,
            cls.BAN_USERS,
            cls.INVITE_USERS,
            cls.PIN_MESSAGES,
            cls.MANAGE_ADMINS,
            cls.REMAIN_ANONYMOUS,
            cls.MANAGE_CALLS,
            cls.OTHER,
            cls.MANAGE_TOPICS,
            cls.POST_STORIES,
            cls.EDIT_STORIES,
            cls.DELETE_STORIES,
        }

    @classmethod
    def _set_to_raw(cls, all_rights: Set[AdminRight]) -> types.ChatAdminRights:
        return types.ChatAdminRights(
            change_info=cls.CHANGE_INFO in all_rights,
            post_messages=cls.POST_MESSAGES in all_rights,
            edit_messages=cls.EDIT_MESSAGES in all_rights,
            delete_messages=cls.DELETE_MESSAGES in all_rights,
            ban_users=cls.BAN_USERS in all_rights,
            invite_users=cls.INVITE_USERS in all_rights,
            pin_messages=cls.PIN_MESSAGES in all_rights,
            add_admins=cls.MANAGE_ADMINS in all_rights,
            anonymous=cls.REMAIN_ANONYMOUS in all_rights,
            manage_call=cls.MANAGE_CALLS in all_rights,
            other=cls.OTHER in all_rights,
            manage_topics=cls.MANAGE_TOPICS in all_rights,
            post_stories=cls.POST_STORIES in all_rights,
            edit_stories=cls.EDIT_STORIES in all_rights,
            delete_stories=cls.DELETE_STORIES in all_rights,
        )
