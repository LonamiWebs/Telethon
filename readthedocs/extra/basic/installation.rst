.. _installation:

============
Installation
============

.. contents::


Automatic Installation
**********************

To install Telethon, simply do:

.. code-block:: sh

    pip3 install telethon

Needless to say, you must have Python 3 and PyPi installed in your system.
See https://python.org and https://pypi.python.org/pypi/pip for more.

If you already have the library installed, upgrade with:

.. code-block:: sh

    pip3 install --upgrade telethon

You can also install the library directly from GitHub or a fork:

.. code-block:: sh

    # pip3 install git+https://github.com/LonamiWebs/Telethon.git
    or
    $ git clone https://github.com/LonamiWebs/Telethon.git
    $ cd Telethon/
    # pip install -Ue .

If you don't have root access, simply pass the ``--user`` flag to the pip
command. If you want to install a specific branch, append ``@branch`` to
the end of the first install command.

By default the library will use a pure Python implementation for encryption,
which can be really slow when uploading or downloading files. If you don't
mind using a C extension, install `cryptg <https://github.com/Lonami/cryptg>`__
via ``pip`` or as an extra:

.. code-block:: sh

    pip3 install telethon[cryptg]


Manual Installation
*******************

1. Install the required ``pyaes`` (`GitHub`__ | `PyPi`__) and
   ``rsa`` (`GitHub`__ | `PyPi`__) modules:

   .. code-block:: sh

       pip3 install pyaes rsa

2. Clone Telethon's GitHub repository:

   .. code-block:: sh

       git clone https://github.com/LonamiWebs/Telethon.git

3. Enter the cloned repository:

   .. code-block:: sh

       cd Telethon

4. Run the code generator:

   .. code-block:: sh

       python3 setup.py gen

5. Done!

To generate the `method documentation`__, ``python3 setup.py gen docs``.


Optional dependencies
*********************

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

If cryptg_ is installed, encryption and decryption will be made in C instead
of Python which will be a lot faster. If your code deals with a lot of
updates or you are downloading/uploading a lot of files, you will notice
a considerable speed-up (from a hundred kilobytes per second to several
megabytes per second, if your connection allows it). If it's not installed,
pyaes_ will be used (which is pure Python, so it's much slower).


__ https://github.com/ricmoo/pyaes
__ https://pypi.python.org/pypi/pyaes
__ https://github.com/sybrenstuvel/python-rsa
__ https://pypi.python.org/pypi/rsa/3.4.2
__ https://lonamiwebs.github.io/Telethon

.. _pillow: https://python-pillow.org
.. _aiohttp: https://docs.aiohttp.org
.. _hachoir: https://hachoir.readthedocs.io
.. _cryptg: https://github.com/Lonami/cryptg
.. _pyaes: https://github.com/ricmoo/pyaes
