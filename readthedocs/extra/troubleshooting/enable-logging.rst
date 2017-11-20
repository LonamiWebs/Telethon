================
Enable Logging
================

Telethon makes use of the `logging`__ module, and you can enable it as follows:

    .. code-block:: python

        import logging
        logging.basicConfig(level=logging.DEBUG)

You can also use it in your own project very easily:

    .. code-block:: python

        import logging
        logger = logging.getLogger(__name__)

        logger.debug('Debug messages')
        logger.info('Useful information')
        logger.warning('This is a warning!')


__ https://docs.python.org/3/library/logging.html