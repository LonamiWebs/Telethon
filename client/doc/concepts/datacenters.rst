Data centers
============

.. currentmodule:: telethon

Telegram has multiple servers, known as *data centers* or MTProto servers, all over the globe.
This makes it possible to have reasonably low latency when sending messages.

When an account is created, Telegram chooses the most appropriated data center for you.
This means you *cannot* change what your "home data center" is.
However, `Telegram may change it after prolongued use from other locations <https://core.telegram.org/api/datacenter>`_.


Connecting behind a proxy
-------------------------

You can change the way Telethon opens a connection to Telegram's data center by setting a different :class:`~telethon._impl.mtsender.sender.Connector`.

A connector is a function returning an asynchronous reader-writer pair.
The default connector is :func:`asyncio.open_connection`, defined as:

.. code-block:: python

    def default_connector(ip: str, port: int):
        return asyncio.open_connection(ip, port)

While proxies are not directly supported in Telethon, you can change the connector to use a proxy.
Any proxy library that supports :mod:`asyncio`, such as `python-socks[asyncio] <https://pypi.org/project/python-socks/>`_, can be used:

.. code-block:: python

    import asyncio
    from functools import partial
    from python_socks.async_.asyncio import Proxy
    from telethon import Client

    async def my_proxy_connector(ip, port, *, proxy_url):
        # Refer to python-socks for an up-to-date way to define and use proxies.
        # This is just an example of a custom connector.
        proxy = Proxy.from_url(proxy_url)
        sock = await proxy.connect(dest_host='example.com', dest_port=443)
        return await asyncio.open_connection(
            host=ip,
            port=port,
            sock=sock,
            ssl=ssl.create_default_context(),
            server_hostname='example.com',
        )

    client = Client(..., connector=partial(
        my_proxy_connector,
        proxy_url='socks5://user:password@127.0.0.1:1080'
    ))

.. important::

    Proxies can be used with Telethon, but they are not directly supported.
    Any connection errors you encounter while using a proxy are therefore very unlikely to be errors in Telethon.
    Connection errors when using custom connectors will *not* be considered bugs in the Telethon.

.. note::

    Some proxies only support HTTP traffic.
    Telethon by default does not transmit HTTP-encoded packets.
    This means some HTTP-only proxies may not work.


Test servers
------------

While you cannot change the production data center assigned to your account, you can tell Telethon to connect to a different server.

This is most useful to connect to the official Telegram test servers or `even your own <https://github.com/DavideGalilei/piltover>`_.

You need to import and define the :class:`session.DataCenter` to connect to when creating the :class:`Client`:

.. code-block:: python

    from telethon import Client
    from telethon.session import DataCenter

    client = Client(..., datacenter=DataCenter(id=2, ipv4_addr='149.154.167.40:443'))

This will override the value coming from the :class:`~session.Session`.
You can get the test address for your account from `My Telegram <https://my.telegram.org>`_.

.. note::

    Make sure the :doc:`sessions` you use for this client had not been created for the production servers before.
    The library will attempt to use the existing authorization key saved based on the data center identifier.
    This will most likely fail if you mix production and test servers.


There are public phone numbers anyone can use, with the following format:

.. code-block::
    :caption: 99966XYYYY test phone number, X being the datacenter identifier and YYYY random digits

    99966  X  YYYY
    \___/ \_/ \__/
      |     |   `- random number
      |     `- datacenter identifier
      `- fixed digits

For example, the test phone number 1234 for the datacenter 2 would be 9996621234.

The confirmation code to complete the login is the datacenter identifier repeated five times, in this case, 22222.

Therefore, it is possible to automate the login procedure, assuming the account exists and there is no 2-factor authentication:

.. code-block:: python

    from random import randrange
    from telethon import Client
    from telethon.session import DataCenter

    datacenter = DataCenter(id=2, ipv4_addr='149.154.167.40:443')
    phone = f'{randrange(1, 9999):04}'
    login_code = str(datacenter.id) * 5
    client = Client(..., datacenter=datacenter)

    async with client:
        if not await client.is_authorized():
            login_token = await client.request_login_code(phone_or_token)
            await client.sign_in(login_token, login_code)
