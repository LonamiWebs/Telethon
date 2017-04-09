import sys
import logging


for arg in sys.argv:
    if arg.startswith('--telethon-log='):
        level = getattr(logging, arg.split('=')[1], None)
        if not isinstance(level, int):
            raise ValueError('Invalid log level: %s' % level)
        print('Using log level', level, 'which is', arg.split('=')[1])
        logging.basicConfig(level=level)


class Logger:
    def __init__(self):
        setattr(self, 'd', logging.debug)
        setattr(self, 'i', logging.info)
        setattr(self, 'w', logging.warning)
        setattr(self, 'e', logging.error)

Log = Logger()
