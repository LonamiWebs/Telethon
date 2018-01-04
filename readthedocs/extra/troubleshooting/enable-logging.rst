================
Enabling Logging
================

Telethon makes use of the `logging`__ module, and you can enable it as follows:

.. code:: python

    import logging
    logging.basicConfig(level=logging.DEBUG)

The library has the `NullHandler`__ added by default so that no log calls
will be printed unless you explicitly enable it.

You can also `use the module`__ on your own project very easily:

    .. code-block:: python

        import logging
        logger = logging.getLogger(__name__)

        logger.debug('Debug messages')
        logger.info('Useful information')
        logger.warning('This is a warning!')


If you want to enable ``logging`` for your project *but* use a different
log level for the library:

    .. code-block:: python

        import logging
        logging.basicConfig(level=logging.DEBUG)
        # For instance, show only warnings and above
        logging.getLogger('telethon').setLevel(level=logging.WARNING)


__ https://docs.python.org/3/library/logging.html
__ https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
__ https://docs.python.org/3/howto/logging.html
