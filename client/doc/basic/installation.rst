Installation
============

Telethon is a Python 3 library, which means you need to download and install Python to use it.
Installing Python, using virtual environments, and the basics of the language, are outside of the scope of this guide.

You can find the official resources to `download Python <https://www.python.org/downloads/>`_,
learn about the `Python Setup and Usage <https://docs.python.org/3/using/index.html>`_ for different platforms,
or follow the `The Python Tutorial <https://docs.python.org/3/tutorial/index.html>`_ to learn the basics.
These are not necessarily the best resources to learn, but they are official.
Be sure to search online if you prefer learning in video form or otherwise.

You can confirm that you have Python installed with:

.. code-block:: shell

    python --version

Which should print something similar to ``Python 3.11.5`` (or newer).
Be sure to run the command in a terminal such as PowerShell or Terminal.
The above won't work inside a Python shell!
If you had the terminal open before installing Python, you will probably need to open a new one.


Installing the latest stable version
------------------------------------

Once you have a working Python 3 installation, you can install or upgrade the ``telethon`` package with ``pip``:

.. code-block:: shell

    python -m pip install --upgrade "telethon~=2.0"

Be sure to use lock-files if your project!
The above is just a quick way to get started and install a `v2-compatible <https://peps.python.org/pep-0440/#compatible-release>`_ Telethon globally.


Installing development versions
-------------------------------

If you want the *latest* unreleased changes, you can run the following command instead:

.. code-block:: shell

    python -m pip install --upgrade https://github.com/LonamiWebs/Telethon/archive/v2.zip#subdirectory=client

.. note::

    The development version may have bugs and is not recommended for production use.
    However, when you are `reporting a library bug <https://github.com/LonamiWebs/Telethon/issues/>`_,
    you must reproduce the issue in this version before reporting the problem.


Verifying the installation
--------------------------

To verify that the library is installed correctly, run the following command:

.. code-block:: shell

    python -c "import telethon; print(telethon.__version__)"

The version number of the library should show in the output.
