==========
API Status
==========


In an attempt to help everyone who works with the Telegram API, the
library will by default report all *Remote Procedure Call* errors to
`RPC PWRTelegram <https://rpc.pwrtelegram.xyz/>`__, a public database
anyone can query, made by `Daniil <https://github.com/danog>`__. All the
information sent is a ``GET`` request with the error code, error message
and method used.

If you still would like to opt out, simply set
``client.session.report_errors = False`` to disable this feature, or
pass ``report_errors=False`` as a named parameter when creating a
``TelegramClient`` instance. However Daniil would really thank you if
you helped him (and everyone) by keeping it on!

Querying the API status
***********************

The API is accessed through ``GET`` requests, which can be made for
instance through ``curl``. A JSON response will be returned.

**All known errors and their description**:

.. code:: bash

    curl https://rpc.pwrtelegram.xyz/?all

**Error codes for a specific request**:

.. code:: bash

    curl https://rpc.pwrtelegram.xyz/?for=messages.sendMessage

**Number of** ``RPC_CALL_FAIL``:

.. code:: bash

    curl https://rpc.pwrtelegram.xyz/?rip  # last hour
    curl https://rpc.pwrtelegram.xyz/?rip=$(time()-60)  # last minute

**Description of errors**:

.. code:: bash

    curl https://rpc.pwrtelegram.xyz/?description_for=SESSION_REVOKED

**Code of a specific error**:

.. code:: bash

    curl https://rpc.pwrtelegram.xyz/?code_for=STICKERSET_INVALID
