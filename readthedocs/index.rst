========================
Telethon's Documentation
========================

.. code-block:: python

   from telethon.sync import TelegramClient, events

   with TelegramClient('name', api_id, api_hash) as client:
      client.send_message('me', 'Hello, myself!')
      print(client.download_profile_photo('me'))

      @client.on(events.NewMessage(pattern='(?i).*Hello'))
      async def handler(event):
         await event.reply('Hey!')

      client.run_until_disconnected()


* Are you new here? Jump straight into :ref:`installation`!
* Looking for the method reference? See :ref:`client-ref`.
* Did you upgrade the library? Please read :ref:`changelog`.
* Used Telethon before v1.0? See :ref:`compatibility-and-convenience`.
* Coming from Bot API or want to create new bots? See :ref:`botapi`.
* Need the full API reference? https://tl.telethon.dev/.


What is this?
-------------

Telegram is a popular messaging application. This library is meant
to make it easy for you to write Python programs that can interact
with Telegram. Think of it as a wrapper that has already done the
heavy job for you, so you can focus on developing an application.


How should I use the documentation?
-----------------------------------

If you are getting started with the library, you should follow the
documentation in order by pressing the "Next" button at the bottom-right
of every page.

You can also use the menu on the left to quickly skip over sections.

.. toctree::
    :hidden:
    :caption: First Steps

    basic/installation
    basic/signing-in
    basic/quick-start
    basic/updates
    basic/next-steps

.. toctree::
    :hidden:
    :caption: Quick References

    quick-references/faq
    quick-references/client-reference
    quick-references/events-reference
    quick-references/objects-reference

.. toctree::
    :hidden:
    :caption: Concepts

    concepts/strings
    concepts/entities
    concepts/chats-vs-channels
    concepts/updates
    concepts/sessions
    concepts/full-api
    concepts/errors
    concepts/botapi-vs-mtproto
    concepts/asyncio

.. toctree::
    :hidden:
    :caption: Full API Examples

    examples/word-of-warning
    examples/chats-and-channels
    examples/users
    examples/working-with-messages

.. toctree::
    :hidden:
    :caption: Developing

    developing/philosophy.rst
    developing/test-servers.rst
    developing/project-structure.rst
    developing/coding-style.rst
    developing/testing.rst
    developing/understanding-the-type-language.rst
    developing/tips-for-porting-the-project.rst
    developing/telegram-api-in-other-languages.rst

.. toctree::
    :hidden:
    :caption: Miscellaneous

    misc/changelog
    misc/compatibility-and-convenience

.. toctree::
    :hidden:
    :caption: Telethon Modules

    modules/client
    modules/events
    modules/custom
    modules/utils
    modules/errors
    modules/sessions
    modules/network
    modules/helpers
