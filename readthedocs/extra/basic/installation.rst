.. _installation:

============
Installation
============


Automatic Installation
**********************

To install Telethon, simply do:

    ``pip3 install telethon``

Needless to say, you must have Python 3 and PyPi installed in your system.
See https://python.org and https://pypi.python.org/pypi/pip for more.

If you already have the library installed, upgrade with:

    ``pip3 install --upgrade telethon``

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

    ``pip3 install telethon[cryptg]``


Manual Installation
*******************

1. Install the required ``pyaes`` (`GitHub`__ | `PyPi`__) and
   ``rsa`` (`GitHub`__ | `PyPi`__) modules:

    ``sudo -H pip3 install pyaes rsa``

2. Clone Telethon's GitHub repository:
   ``git clone https://github.com/LonamiWebs/Telethon.git``

3. Enter the cloned repository: ``cd Telethon``

4. Run the code generator: ``python3 setup.py gen_tl``

5. Done!

To generate the `method documentation`__, ``cd docs`` and then
``python3 generate.py`` (if some pages render bad do it twice).


Optional dependencies
*********************

If ``libssl`` is available on your system, it will be used wherever encryption
is needed, but otherwise it will fall back to pure Python implementation so it
will also work without it.


__ https://github.com/ricmoo/pyaes
__ https://pypi.python.org/pypi/pyaes
__ https://github.com/sybrenstuvel/python-rsa
__ https://pypi.python.org/pypi/rsa/3.4.2
__ https://lonamiwebs.github.io/Telethon
