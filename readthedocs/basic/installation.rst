.. _installation:

============
Installation
============

Telethon is a Python library, which means you need to download and install
Python from https://www.python.org/downloads/ if you haven't already. Once
you have Python installed, `upgrade pip`__ and run:

.. code-block:: sh

    python3 -m pip install --upgrade pip
    python3 -m pip install --upgrade telethon

…to install or upgrade the library to the latest version.

.. __: https://pythonspeed.com/articles/upgrade-pip/

Installing Development Versions
===============================

If you want the *latest* unreleased changes,
you can run the following command instead:

.. code-block:: sh

    python3 -m pip install --upgrade https://github.com/LonamiWebs/Telethon/archive/v1.zip

.. note::

    The development version may have bugs and is not recommended for production
    use. However, when you are `reporting a library bug`__, you should try if the
    bug still occurs in this version.

.. __: https://github.com/LonamiWebs/Telethon/issues/


Verification
============

To verify that the library is installed correctly, run the following command:

.. code-block:: sh

    python3 -c "import telethon; print(telethon.__version__)"

The version number of the library should show in the output.


Optional Dependencies
=====================

If cryptg_ is installed, **the library will work a lot faster**, since
encryption and decryption will be made in C instead of Python. If your
code deals with a lot of updates or you are downloading/uploading a lot
of files, you will notice a considerable speed-up (from a hundred kilobytes
per second to several megabytes per second, if your connection allows it).
If it's not installed, pyaes_ will be used (which is pure Python, so it's
much slower).

If pillow_ is installed, large images will be automatically resized when
sending photos to prevent Telegram from failing with "invalid image".
Official clients also do this.

If aiohttp_ is installed, the library will be able to download
:tl:`WebDocument` media files (otherwise you will get an error).

If hachoir_ is installed, it will be used to extract metadata from files
when sending documents. Telegram uses this information to show the song's
performer, artist, title, duration, and for videos too (including size).
Otherwise, they will default to empty values, and you can set the attributes
manually.

.. note::

    Some of the modules may require additional dependencies before being
    installed through ``pip``. If you have an ``apt``-based system, consider
    installing the most commonly missing dependencies (with the right ``pip``):

    .. code-block:: sh

        apt update
        apt install clang lib{jpeg-turbo,webp}-dev python{,-dev} zlib-dev
        pip install -U --user setuptools
        pip install -U --user telethon cryptg pillow

    Thanks to `@bb010g`_ for writing down this nice list.


.. _cryptg: https://github.com/cher-nov/cryptg
.. _pyaes: https://github.com/ricmoo/pyaes
.. _pillow: https://python-pillow.org
.. _aiohttp: https://docs.aiohttp.org
.. _hachoir: https://hachoir.readthedocs.io
.. _@bb010g: https://static.bb010g.com
