Messages
========

.. currentmodule:: telethon

.. role:: underline
    :class: underline

.. role:: strikethrough
    :class: strikethrough

.. role:: spoiler
    :class: spoiler

Messages are at the heart of a messaging platform.
In Telethon, you will be using the :class:`~types.Message` class to interact with them.

.. _formatting:

Formatting messages
-------------------

The library supports 3 formatting modes: no formatting, CommonMark, HTML.

Telegram does not natively support markdown or HTML.
Clients such as Telethon parse the text into a list of formatting :tl:`MessageEntity` at different offsets.

Note that `CommonMark's markdown <https://commonmark.org/>`_ is not fully compatible with :term:`HTTP Bot API`'s
`MarkdownV2 style <https://core.telegram.org/bots/api#markdownv2-style>`_, and does not support spoilers::

    *italic* and _italic_
    **bold** and __bold__
    # headings are underlined
    ~~strikethrough~~
    [inline URL](https://www.example.com/)
    [inline mention](tg://user?id=ab1234cd6789)
    custom emoji image with ![👍](tg://emoji?id=1234567890)
    `inline code`
    ```python
    multiline pre-formatted
    block with optional language
    ```

HTML is also not fully compatible with :term:`HTTP Bot API`'s
`MarkdownV2 style <https://core.telegram.org/bots/api#markdownv2-style>`_,
and instead favours more standard `HTML elements <https://developer.mozilla.org/en-US/docs/Web/HTML/Element>`_:

* ``strong`` and ``b`` for **bold**.
* ``em`` and ``i`` for *italics*.
* ``u`` for :underline:`underlined text`.
* ``del`` and ``s`` for :strikethrough:`strikethrough`.
* ``blockquote`` for quotes.
* ``details`` for :spoiler:`hidden text` (spoiler).
* ``code`` for ``inline code``
* ``pre`` for multiple lines of code.
* ``a`` for links.
* ``img`` for inline images (only custom emoji).

Both markdown and HTML recognise the following special URLs using the ``tg:`` protocol:

* ``tg://user?id=ab1234cd6789`` for inline mentions.
  To make sure the mention works, use :attr:`types.PackedChat.hex`.
  You can also use :attr:`types.User.id`, but the mention will fail if the user is not in cache.
* ``tg://emoji?id=1234567890`` for custom emoji.
  You must use the document identifier as the value.
  The alt-text of the image **must** be a emoji such as 👍.


To obtain a message's text formatted, use :attr:`types.Message.text_markdown` or :attr:`types.Message.text_html`.

To send a message with formatted text, use the ``markdown`` or ``html`` parameters in :meth:`Client.send_message`.

When sending files, the format is appended to the name of the ``caption`` parameter, either ``caption_markdown`` or ``caption_html``.


Message identifiers
-------------------

This is an in-depth explanation for how the :attr:`types.Message.id` works.

.. note::

    You can safely skip this section if you're not interested.

Every account, whether it's an user account or bot account, has its own message counter.
This counter starts at 1, and is incremented by 1 every time a new message is received.
In private conversations or small groups, each account will receive a copy each message.
The message identifier will be based on the message counter of the receiving account.

In megagroups and broadcast channels, the message counter instead belongs to the channel itself.
It also starts at 1 and is incremented by 1 for every message sent to the group or channel.
This means every account will see the same message identifier for a given mesasge in a group or channel.

This design has the following implications:

* The message identifier alone is enough to uniquely identify a message only if it's not from a megagroup or channel.
  This is why :class:`events.MessageDeleted` does not need to (and doesn't always) include chat information.
* Messages cannot be deleted for one-side only in megagroups or channels.
  Because every account shares the same identifier for the message, it cannot be deleted only for some.
* Links to messages only work for everyone inside megagroups or channels.
  In private conversations and small groups, each account will have their own counter, and the identifiers won't match.

Let's look at a concrete example.

* You are logged in as User-A.
* Both User-B and User-C are your mutual contacts.
* You have share a small group called Group-S with User-B.
* You also share a megagroup called Group-M with User-C.

.. graphviz::
    :caption: Demo scenario

    digraph scenario {
        "User A" [shape=trapezium];
        "User B" [shape=box];
        "User C" [shape=box];

        "User A" -> "User B";
        "User A" -> "User C";

        "Group-S" -> "User A";
        "Group-S" -> "User B";

        "Group-M" -> "User A";
        "Group-M" -> "User C";
    }

Every account and channel has just been created.
This means everyone has a message counter of one.

First, User-A will sent a welcome message to both User-B and User-C::

    User-A → User-B: Hey, welcome!
    User-A → User-C: ¡Bienvenido!

* For User-A, "Hey, welcome!" will have the message identifier 1. The message with "¡Bienvenido!" will have an ID of 2.
* For User-B, "Hey, welcome" will have ID 1.
* For User-B, "¡Bienvenido!" will have ID 1.

.. csv-table:: Message identifiers
   :header: "Message", "User-A", "User-B", "User-C", "Group-S", "Group-M"

   "Hey, welcome!", 1, 1, "", "", ""
   "¡Bienvenido!", 2, "", 1, "", ""

Next, User-B and User-C will respond to User-A::

    User-B → User-A: Thanks!
    User-C → User-A: Gracias :)

.. csv-table:: Message identifiers
   :header: "Message", "User-A", "User-B", "User-C", "Group-S", "Group-M"

   "Hey, welcome!", 1, 1, "", "", ""
   "¡Bienvenido!", 2, "", 1, "", ""
   "Thanks!", 3, 2, "", "", ""
   "Gracias :)", 4, "", 2, "", ""

Notice how for each message, the counter goes up by one, and they are independent.

Let's see what happens when User-B sends a message to Group-S::

    User-B → Group-S: Nice group

.. csv-table:: Message identifiers
   :header: "Message", "User-A", "User-B", "User-C", "Group-S", "Group-M"

   "Hey, welcome!", 1, 1, "", "", ""
   "¡Bienvenido!", 2, "", 1, "", ""
   "Thanks!", 3, 2, "", "", ""
   "Gracias :)", 4, "", 2, "", ""
   "Nice group", 5, 3, "", "", ""

While the message was sent to a different chat, the group itself doesn't have a counter.
The message identifiers are still unique for each account.
The chat where the message was sent can be completely ignored.

Megagroups behave differently::

    User-C → Group-M: Buen grupo

.. csv-table:: Message identifiers
   :header: "Message", "User-A", "User-B", "User-C", "Group-S", "Group-M"

   "Hey, welcome!", 1, 1, "", "", ""
   "¡Bienvenido!", 2, "", 1, "", ""
   "Thanks!", 3, 2, "", "", ""
   "Gracias :)", 4, "", 2, "", ""
   "Nice group", 5, 3, "", "", ""
   "Buen grupo", "", "", "", "", 1

The group has its own message counter.
Each user won't get a copy of the message with their own identifier, but rather everyone sees the same message.
