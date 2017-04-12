import sys
import logging


# Find the logging level
level = logging.NOTSET
for arg in sys.argv:
    if arg.startswith('--telethon-log='):
        level = getattr(logging, arg.split('=')[1], logging.NOTSET)
        break

# "[Time/Thread] Level: Messages"
formatter = logging.Formatter(
    fmt='[%(asctime)s.%(msecs)03d/%(threadName)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S')

# Create our logger
Log = logging.getLogger('TelethonLogger')
Log.setLevel(level)

console = logging.StreamHandler()
console.setFormatter(formatter)

Log.addHandler(console)

# Use shorter function names
Log.__dict__['d'] = Log.debug
Log.__dict__['i'] = Log.info
Log.__dict__['w'] = Log.warning
Log.__dict__['e'] = Log.error
