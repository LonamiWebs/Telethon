You should be able to run these files with python3 filename.py after
installing Telethon (`pip3 install .` on the root of the project if you
haven't installed it yet and you downloaded the repository).

Most of these examples assume you have the following variables defined
in your environment:

    TG_API_ID, this is the api ID of your Telegram application.
    TG_API_HASH, similarly, this is the api hash.
    TG_TOKEN, for bot examples, this should be the bot token.
    TG_SESSION, this is the session file name to be (re)used.

See https://superuser.com/q/284342 to learn how to define them.
It's more convenient to define them, but if you forget to do so,
the scripts will ask you to enter the variables when ran.
