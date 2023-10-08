Contributing
============

Telethon welcomes all new contributions, whether it's reporting bugs or sending code patches.

Please keep both the philosophy and coding style below in mind.

Be mindful when adding new features.
Every new feature must be understood by the maintainer, or otherwise it will probably rot.
The *usefulness : maintenance-cost* ratio must be high enough to warrant being built-in.
Consider whether your new features could be a separate add-on project entirely.


Philosophy
----------

* Dependencies should only be added when absolutely necessary.
* Dependencies written in anything other than Python cannot be mandatory.
* The library must work correctly with no system dependencies other than Python 3.
* Strict type-checking is required to pass everywhere in the library to make upgrades easier.
* The code structure must make use of hard and clear boundaries to keep the different parts decoupled.
* The API should cover only the most commonly used features to avoid bloat and reduce maintenance costs.
* Documentation must be a pleasure to use and contain plenty of code examples.


Coding style
------------

Knowledge of Python is a obviously a must to develop a Python library.
A good online resource is `Dive Into Python 3 <http://www.diveintopython3.net/>`_.

Telethon uses multiple tools to automatically format the code and check for linting rules.
This means you can simply ignore formatting and let the tools handle it for you.
You can find these tools under the ``tools/`` folder.
See :ref:`tools` below for an explanation.

The documentation is written with mostly a newline after every period.
This is not a hard rule.
Lines can be cut earlier if they become too long to be comfortable.

Commit messages should be short and descriptive.
They should start with an action in the present ("Fix" and not "Fixed").
This saves a few characters and represents what the commit will "do" after applied.


Project structure
-----------------

.. currentmodule:: telethon

The repository contains several folders, each with their own "package".


benches/
^^^^^^^^

This folder contains different benchmarks.
Pretty straightforward.


stubs/
^^^^^^

If a dependency doesn't support typing, files here must work around that.

.. _tools:

tools/
^^^^^^

Various utility scripts.
Each script should have a "comment" at the top explaining what they are for.

Code generation
"""""""""""""""

This will take ``api.tl`` and ``mtproto.tl`` files and generate ``client/_impl/tl``.

.. code-block:: sh

    pip install -e generator/
    python tools/codegen.py

Linting
"""""""

This includes format checks, type-checking and testing.

.. code-block:: sh

    pip install -e client/[dev]
    python tools/check.py

Documentation
"""""""""""""

Requires `sphinx <https://www.sphinx-doc.org>`_ and `graphviz <https://www.graphviz.org>`_'s ``dot``.

.. code-block:: sh

    pip install -e client/[doc]
    python tools/docgen.py

Note that multiple optional dependency sets can be specified by separating them with a comma (``[dev,doc]``).

.. _tl-brief:

generator/
^^^^^^^^^^

A package that should not be published and is only used when developing the library.
The implementation is private and exists under the ``src/*/_impl/`` folder.
Only select parts are exported under public modules.
Tests live under ``tests/``.

The implementation consists of a parser and a code generator.

The parser is able to read parse ``.tl`` files (:term:`Type Language` definition files).
It doesn't do anything with the files other than to represent the content as Python objects.

.. admonition:: Type Language brief

    TL-definitions are statements terminated with a semicolon ``;`` and often defined in a single line:

    .. code-block::

        geoPointEmpty#1117dd5f = GeoPoint;
        geoPoint#b2a2f663 flags:# long:double lat:double access_hash:long accuracy_radius:flags.0?int = GeoPoint;

    The first word is the name, optionally followed by the hash sign ``#`` and an hexadecimal number.
    Every definition can have a constructor identifier inferred based on its own text representation.
    The hexadecimal number will override the constructor identifier used for the definition.

    What follows up to the equals-sign ``=`` are the fields of the definition.
    They have a name and a type, separated by the colon ``:``.

    The type ``#`` represents a bitflag.
    Other fields can be conditionally serialized by prefixing the type with ``flag_name.bit_index?``.

    After the equal-sign comes the name for the "base class".
    This representation is known as "boxed", and it contains the constructor identifier to discriminate a definition.
    If the definition name appears on its own, it will be "bare" and will not have the constructor identifier prefix.


The code generator uses the parsed definitions to generate Python code.
Most of the code to serialize and deserialize objects lives under ``serde/``.

An in-memory "filesystem" structure is kept before writing all files to disk.
This makes it possible to execute most of the process in a sans-io manner.
Once the code generation finishes, all files are written to disk at once.

See :ref:`tools` above to learn how to generate code.


client/
^^^^^^^

The Telethon client library and documentation lives here.
This is the package that gets published.
The implementation is private and exists under the ``src/*/_impl/`` folder.
Only select parts are exported under public modules.
Tests live under ``tests/``.

The client implementation consists of several subpackages.

The ``tl`` package sits at the bottom.
It is where the generated code is placed.
It also contains some of the definitions needed for the generated code to work.
Even though all the :term:`RPC` live here, this package can't do anything by itself.

The ``crypto`` package implements all the encryption and decryption rules used by Telegram.
Details concerning the :term:`MTProto` are mostly avoided, so the package can be generally useful.

The ``mtproto`` package implements the logic required to talk to Telegram.
It is implemented in a sans-io manner.
This package is responsible for generating an authorization key and serializing packets.
It also contains some optimizations which are not strictly necessary when implementing the library.

The ``mtsender`` package simply adds IO to ``mtproto``.
It is responsible for driving the network, enqueuing requests, and waiting for results.

The ``session`` crate implements what's needed to manage the :term:`session` state.
The logic to handle and correctly order updates also lives here, in a sans-io manner.

The ``client`` ties everything together.
This is what defines the Pythonic API to interact with Telegram.
Custom object and event types also live here.

Even though only common methods are implemented, the code is still huge.
For this reason, the :class:`Client` implementation is separated from the class definition.
The class definition only contains documentation and calls functions defined in other files.
A tool under ``tools/`` exists to make it easy to keep these two in sync.

If you plan to port the library to a different language, good luck!
You will need a code generator, the ``crypto``, ``mtproto`` and ``mtsender`` packages to have an initial working version.
The tests are your friend, write them too!
