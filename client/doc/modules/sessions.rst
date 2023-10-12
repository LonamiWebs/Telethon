Sessions
========

Classes related to session data and session storages.

.. note::

    This module is mostly of interest if you plan to write a custom session storage.
    You should not need to interact with these types directly under normal use.

.. seealso::

    The :doc:`/concepts/sessions` concept for more details.

.. module:: telethon.session

Storages
--------

.. autoclass:: Storage
.. autoclass:: SqliteSession
.. autoclass:: MemorySession

Types
-----

.. autoclass:: Session
.. autoclass:: DataCenter
.. autoclass:: User
.. autoclass:: UpdateState
.. autoclass:: ChannelState
