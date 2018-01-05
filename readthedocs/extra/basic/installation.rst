.. _installation:

============
Installation
============


Automatic Installation
**********************

To install Telethon, simply do:

    ``pip install telethon``

If you get something like ``"SyntaxError: invalid syntax"`` or any other
error while installing/importing the library, it's probably because ``pip``
defaults to Python 2, which is not supported. Use ``pip3`` instead.

If you already have the library installed, upgrade with:

    ``pip install --upgrade telethon``

You can also install the library directly from GitHub or a fork:

   .. code-block:: sh

        # pip install git+https://github.com/LonamiWebs/Telethon.git
        or
        $ git clone https://github.com/LonamiWebs/Telethon.git
        $ cd Telethon/
        # pip install -Ue .

If you don't have root access, simply pass the ``--user`` flag to the pip command.


Manual Installation
*******************

1. Install the required ``pyaes`` (`GitHub`__ | `PyPi`__) and
   ``rsa`` (`GitHub`__ | `PyPi`__) modules:

    ``sudo -H pip install pyaes rsa``

2. Clone Telethon's GitHub repository:
   ``git clone https://github.com/LonamiWebs/Telethon.git``

3. Enter the cloned repository: ``cd Telethon``

4. Run the code generator: ``python3 setup.py gen_tl``

5. Done!

To generate the documentation, ``cd docs`` and then ``python3 generate.py``.


Optional dependencies
*********************

If ``libssl`` is available on your system, it will be used wherever encryption
is needed, but otherwise it will fall back to pure Python implementation so it
will also work without it.


__ https://github.com/ricmoo/pyaes
__ https://pypi.python.org/pypi/pyaes
__ https://github.com/sybrenstuvel/python-rsa/
__ https://pypi.python.org/pypi/rsa/3.4.2
