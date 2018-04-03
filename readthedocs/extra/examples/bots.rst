====
Bots
====


.. note::

    These examples assume you have read :ref:`accessing-the-full-api`.


Talking to Inline Bots
**********************

You can query an inline bot, such as `@VoteBot`__ (note, *query*,
not *interact* with a voting message), by making use of the
`GetInlineBotResultsRequest`__ request:

    .. code-block:: python

        from telethon.tl.functions.messages import GetInlineBotResultsRequest

        bot_results = client(GetInlineBotResultsRequest(
            bot, user_or_chat, 'query', ''
        ))

And you can select any of their results by using
`SendInlineBotResultRequest`__:

    .. code-block:: python

        from telethon.tl.functions.messages import SendInlineBotResultRequest

        client(SendInlineBotResultRequest(
            get_input_peer(user_or_chat),
            obtained_query_id,
            obtained_str_id
        ))


Talking to Bots with special reply markup
*****************************************

To interact with a message that has a special reply markup, such as
`@VoteBot`__ polls, you would use `GetBotCallbackAnswerRequest`__:

    .. code-block:: python

        from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

        client(GetBotCallbackAnswerRequest(
            user_or_chat,
            msg.id,
            data=msg.reply_markup.rows[wanted_row].buttons[wanted_button].data
        ))

It's a bit verbose, but it has all the information you would need to
show it visually (button rows, and buttons within each row, each with
its own data).

__ https://t.me/vote
__ https://lonamiwebs.github.io/Telethon/methods/messages/get_inline_bot_results.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/send_inline_bot_result.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/get_bot_callback_answer.html
__ https://t.me/vote
