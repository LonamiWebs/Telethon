=====
Users
=====


.. note::

    These examples assume you have read :ref:`full-api`.

.. contents::


Retrieving full information
===========================

If you need to retrieve the bio, biography or about information for a user
you should use :tl:`GetFullUser`:


.. code-block:: python

    from telethon.tl.functions.users import GetFullUserRequest

    full = await client(GetFullUserRequest(user))
    # or even
    full = await client(GetFullUserRequest('username'))

    bio = full.about


See :tl:`UserFull` to know what other fields you can access.


Updating your name and/or bio
=============================

The first name, last name and bio (about) can all be changed with the same
request. Omitted fields won't change after invoking :tl:`UpdateProfile`:

.. code-block:: python

    from telethon.tl.functions.account import UpdateProfileRequest

    await client(UpdateProfileRequest(
        about='This is a test from Telethon'
    ))


Updating your username
======================

You need to use :tl:`account.UpdateUsername`:

.. code-block:: python

    from telethon.tl.functions.account import UpdateUsernameRequest

    await client(UpdateUsernameRequest('new_username'))


Updating your profile photo
===========================

The easiest way is to upload a new file and use that as the profile photo
through :tl:`UploadProfilePhoto`:


.. code-block:: python

    from telethon.tl.functions.photos import UploadProfilePhotoRequest

    await client(UploadProfilePhotoRequest(
        await client.upload_file('/path/to/some/file')
    ))
