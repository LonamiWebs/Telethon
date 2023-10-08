.. |svglogo| image:: ../../logo.svg
    :width: 24pt
    :height: 24pt

.. only:: html

    .. highlights:: |svglogo| **Welcome to Telethon's documentation!**

.. only:: not html

    .. highlights:: **Welcome to Telethon's documentation!**

.. code-block:: python

    import asyncio
    from telethon import Client, events
    from telethon.events import filters

    async def main():
        async with Client('name', api_id, api_hash) as client:
            me = await client.interactive_login()
            await client.send_message(me, f'Hello, {me.full_name}!')

            @client.on(events.NewMessage, filters.Text(r'(?i)hello'))
            async def handler(event):
                await event.reply('Hey!')

            await client.run_until_disconnected()

    asyncio.run(main())

* Are you new here? Jump straight into :doc:`basic/installation`!
* Looking for the Client API reference? See :doc:`modules/client`.
* Did you upgrade the library? Please read :doc:`developing/changelog`.
* Coming from Bot API or want to create new bots? See :doc:`concepts/botapi-vs-mtproto`.
* Used Telethon before v2.0? See :doc:`developing/migration-guide`.
* Want to hack away with the raw API? Search in `Telethon Raw API <https://tl.telethon.dev/>`_.


Preface
=======

.. rubric:: What is this?

Telegram is a popular messaging application.
This library is meant to make it easy for you to write Python programs that can interact with Telegram.
Think of it as a wrapper that has already done the hard work for you, so you can focus on developing an application.


.. rubric:: How should I use the documentation?

This documentation is divided in multiple sections. The first few sections are a guide, while others contain the API reference or a glossary of terms.
The documentation assumes some familiarity with Python.

If you are getting started with the library, you should follow the documentation in order by pressing the "Next" button at the bottom-right of every page.

You can also use the menu on the left to quickly skip over sections if you're looking for something in particular or want to continue where you left off.


First steps
===========

In this section you will learn how to install the library and login to your Telegram account.

:doc:`‣ Start reading Installation <basic/installation>`

.. toctree::
    :hidden:
    :caption: First steps

    basic/installation
    basic/signing-in
    basic/next-steps


API reference
=============

This section contains all the functions and types offered by the library.

:doc:`‣ Start reading Client API <modules/client>`

.. toctree::
    :hidden:
    :caption: API reference

    modules/client
    modules/events
    modules/types
    modules/sessions

Concepts
========

A more in-depth explanation of some of the concepts and words used in Telethon.

:doc:`‣ Start reading Chat concept <concepts/chats>`

.. toctree::
    :hidden:
    :caption: Concepts

    concepts/chats
    concepts/updates
    concepts/messages
    concepts/sessions
    concepts/errors
    concepts/botapi-vs-mtproto
    concepts/full-api
    concepts/glossary

Development resources
=====================

Tips and tricks to develop both with the library and for the library.

:doc:`‣ Start reading Changelog <developing/changelog>`

.. toctree::
    :hidden:
    :caption: Development resources

    developing/changelog
    developing/migration-guide
    developing/faq
    developing/contributing
