============
Test Servers
============


To run Telethon on a test server, use the following code:

.. code-block:: python

    client = TelegramClient(None, api_id, api_hash)
    client.session.set_dc(dc_id, '149.154.167.40', 80)

You can check your ``'test ip'`` on https://my.telegram.org.

You should set `None` session so to ensure you're generating a new
authorization key for it (it would fail if you used a session where you
had previously connected to another data center).

Note that port 443 might not work, so you can try with 80 instead.

Once you're connected, you'll likely be asked to either sign in or sign up.
Remember `anyone can access the phone you
choose <https://core.telegram.org/api/datacenter#testing-redirects>`__,
so don't store sensitive data here.

Valid phone numbers are ``99966XYYYY``, where ``X`` is the ``dc_id`` and
``YYYY`` is any number you want, for example, ``1234`` in ``dc_id = 2`` would
be ``9996621234``. The code sent by Telegram will be ``dc_id`` repeated five
times, in this case, ``22222`` so we can hardcode that:

.. code-block:: python

    client = TelegramClient(None, api_id, api_hash)
    client.session.set_dc(2, '149.154.167.40', 80)
    client.start(
        phone='9996621234', code_callback=lambda: '22222'
    )

Note that Telegram has changed the length of login codes multiple times in the
past, so if ``dc_id`` repeated five times does not work, try repeating it six
times.
