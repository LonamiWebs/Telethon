.. _ref-summary:

=================
Reference Summary
=================

This page contains a summary of all the important methods and properties that
you may need when using Telethon. They are sorted by relevance and are not in
alphabetical order.

The way you should use this page is by looking up the type you need in the
table of contents (method index below) and searching for the method or
property that you are interested in.

.. contents:: Method Index

TelegramClient
==============

This is a summary of the methods you will find at :ref:`telethon-client`.

Auth
----

.. currentmodule:: telethon.client.auth.AuthMethods

.. autosummary::
    :nosignatures:

    start
    send_code_request
    sign_in
    sign_up
    log_out
    edit_2fa

Base
----

.. py:currentmodule:: telethon.client.telegrambaseclient.TelegramBaseClient

.. autosummary::
    :nosignatures:

    connect
    disconnect
    is_connected
    disconnected
    loop

Messages
--------

.. py:currentmodule:: telethon.client.messages.MessageMethods

.. autosummary::
    :nosignatures:

    send_message
    edit_message
    delete_messages
    forward_messages
    iter_messages
    get_messages
    send_read_acknowledge

Uploads
-------

.. py:currentmodule:: telethon.client.uploads.UploadMethods

.. autosummary::
    :nosignatures:

    send_file
    upload_file

Downloads
---------

.. currentmodule:: telethon.client.downloads.DownloadMethods

.. autosummary::
    :nosignatures:

    download_media
    download_profile_photo
    download_file

Dialogs
-------

.. py:currentmodule:: telethon.client.dialogs.DialogMethods

.. autosummary::
    :nosignatures:

    iter_dialogs
    get_dialogs
    iter_drafts
    get_drafts
    conversation

Users
-----

.. py:currentmodule:: telethon.client.users.UserMethods

.. autosummary::
    :nosignatures:

    get_me
    is_bot
    is_user_authorized
    get_entity
    get_input_entity
    get_peer_id

Chats
-----

.. currentmodule:: telethon.client.chats.ChatMethods

.. autosummary::
    :nosignatures:

    iter_participants
    get_participants
    iter_admin_log
    get_admin_log
    action

Parse Mode
----------

.. py:currentmodule:: telethon.client.messageparse.MessageParseMethods

.. autosummary::
    :nosignatures:

    parse_mode

Updates
-------

.. py:currentmodule:: telethon.client.updates.UpdateMethods

.. autosummary::
    :nosignatures:

    on
    run_until_disconnected
    add_event_handler
    remove_event_handler
    list_event_handlers
    catch_up

Bots
----

.. currentmodule:: telethon.client.bots.BotMethods

.. autosummary::
    :nosignatures:

    inline_query

Buttons
-------

.. currentmodule:: telethon.client.buttons.ButtonMethods

.. autosummary::
    :nosignatures:

    build_reply_markup

Account
-------

.. currentmodule:: telethon.client.account.AccountMethods

.. autosummary::
    :nosignatures:

    takeout
    end_takeout
