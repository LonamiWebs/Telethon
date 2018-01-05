============
Test Servers
============


To run Telethon on a test server, use the following code:

    .. code-block:: python

        client = TelegramClient(None, api_id, api_hash)
        client.session.server_address = '149.154.167.40'
        client.connect()

You can check your ``'test ip'`` on https://my.telegram.org.

You should set ``None`` session so to ensure you're generating a new
authorization key for it (it would fail if you used a session where you
had previously connected to another data center).

Once you're connected, you'll likely need to ``.sign_up()``. Remember
`anyone can access the phone you
choose <https://core.telegram.org/api/datacenter#testing-redirects>`__,
so don't store sensitive data here:

    .. code-block:: python

        from random import randint

        dc_id = '2'  # Change this to the DC id of the test server you chose
        phone = '99966' + dc_id + str(randint(9999)).zfill(4)
        client.send_code_request(phone)
        client.sign_up(dc_id * 5, 'Some', 'Name')
