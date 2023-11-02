Updates
=======

.. currentmodule:: telethon

Updates are an important topic in a messaging platform like Telegram.
After all, you want to be notified as soon as certain events happen, such as new message arrives.

Telethon abstracts away Telegram updates with :mod:`~telethon.events`.

.. important::

    It is strongly advised to configure logging when working with events:

    .. code-block:: python

        import logging
        logging.basicConfig(
            format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
            level=logging.WARNING
        )

    With the above, you will see all warnings and errors and when they happened.


Listening to updates
--------------------

You can define and register your own functions to be called when certain :mod:`telethon.events` occur.

The most common way is using the :meth:`Client.on` decorator to register your callback functions, often referred to as *handlers*:

.. code-block:: python

    from telethon import Client, events
    from telethon.events import filters

    bot = Client(...)

    @bot.on(events.NewMessage, filters.Command('/start') | filters.Command('/help'))
    async def handler(event: events.NewMessage):
        await event.respond('Beep boop!')

The first parameter is the :class:`type` of one of the :mod:`telethon.events`, not an instance, so make sure you don't write parenthesis after it.

The second parameter is optional.
If provided, it must be a callable function that returns :data:`True` if the handler should run.
Built-in filter functions are available in the :mod:`~telethon.events.filters` module.
In this example, :class:`~events.filters.Command` means the handler will be called when the user sends */start* or */help* to the bot.

Built-in filter functions are also :class:`~telethon._impl.client.events.filters.combinators.Combinable`.
This means you can use ``|``, ``&`` and the unary ``~`` to combine filters with *or*, *and*, and negate them, respectively.
These operators correspond to :class:`events.filters.Any`, :class:`events.filters.All` and :class:`events.filters.Not`.

When your ``handler`` function is called, it will receive a single parameter, the event.
The event type is the same as the one you defined in the decorator when registering your handler.
You don't need to explicitly set the type hint, but you can do so if you want your IDE to assist in autocompletion.

If you cannot use decorators, you can use the :meth:`Client.add_event_handler` method instead.
The above code is equivalent to the following:

.. code-block:: python

    from telethon import Client, events
    from telethon.events import filters

    async def handler(event: events.NewMessage):
        await event.respond('Beep boop!')

    bot = Client(...)
    bot.add_event_handler(handler, events.NewMessage, filters.Command('/start'))


Note how the above lets you defined the :class:`Client` instance *after* your handlers.
In other words, you can define your handlers without the :class:`Client` instance.
This may make it easier to place them in a separate file.


Filtering events
----------------

There is no way to tell Telegram to only send certain updates.
Telegram sends all updates to connected active clients as they occur.
Telethon must be received and process all updates to ensure correct ordering.

Filters are not magic.
They work all the same as ``if`` conditions inside your event handlers.
However, they offer a more convenient and consistent way to check for certain conditions.

All built-in filters can be found in :mod:`telethon.events.filters`.

When registering an event handler, you can optionally define the filter to use.
You can retrieve a handler's filter with :meth:`~Client.get_handler_filter`.
You can set (and overwrite) a handler's filter with :meth:`~Client.set_handler_filter`.

Filters are meant to be fast and never raise exceptions.
For this reason, filters cannot be asynchronous.
This reduces the chance a filter will do slow IO and potentially fail.

A filter is simply a callable function that takes an event as input and returns a boolean.
If the filter returns :data:`True`, the handler will be called.
Using this knowledge, you can create custom filters too.
If you need state, you can use a class with a ``__call__`` method defined:

.. code-block:: python

    # Anonymous filter which only handles messages with ID = 1000
    client.add_event_handler(handler, events.NewMessage, lambda e: e.id == 1000)
    #                      this parameter is the filter  ^--------------------^

    # ...

    def only_odd_messages(event):
        "A filter that only handles messages when their ID is divisible by 2"
        return event.id % 2 == 0

    client.add_event_handler(handler, events.NewMessage, only_odd_messages)

    # ...

    class OnlyDivisibleMessages:
        "A filter that only handles messages when their ID is divisible by some amount"
        def __init__(self, divisible_by):
            self.divisible_by = divisible_by

        def __call__(self, event):
            return event.id % self.divisible_by == 0

    client.add_event_handler(handler, events.NewMessage, OnlyDivisibleMessages(7))

Custom filters should accept any :class:`~events.Event`.
You can use :func:`isinstance` if your filter can only deal with certain types of events.

If you need to perform asynchronous operations, you can't use a filter.
Instead, manually check for those conditions inside your handler.

The filters work all the same when using :meth:`Client.on`.
This makes it very convenient to write custom filters using the :keyword:`lambda` syntax:

.. code-block:: python

    @client.on(events.NewMessage, lambda e: e.id == 1000)
    async def handler(event):
        ...


Setting priority on handlers
----------------------------

There is no explicit way to define a different priority for different handlers.

Instead, the library will call all your handlers in the order you added them.
This means that, if you want a "catch-all" handler, it should be registered last.

By default, the library will stop calling the rest of handlers after one is called:

.. code-block:: python

    @client.on(events.NewMessage)
    async def first(event):
        print('This is always called on new messages!')

    @client.on(events.NewMessage)
    async def second(event):
        print('This will never be called, because "first" already ran.')

This is often the desired behaviour if you're using filters.

If you have more complicated filters executed *inside* the handler,
Telethon believes your handler completed and will stop calling the rest.
If that's the case, you can :keyword:`return` :class:`events.Continue`:

.. code-block:: python

    @client.on(events.NewMessage)
    async def first(event):
        print('This is always called on new messages!')
        return events.Continue

    @client.on(events.NewMessage)
    async def second(event):
        print('Now this one runs as well!')

Alternatively, if this is *always* the behaviour you want, you can configure it in the :class:`Client`:

.. code-block:: python

    client = Client(..., check_all_handlers=True)
    #                    ^^^^^^^^^^^^^^^^^^^^^^^
    # Now the code above will call both handlers, even without returning events.Continue

If you need a more complicated setup, consider sorting all your handlers beforehand.
Then, use :meth:`Client.add_event_handler` on all of them to ensure the correct order.
