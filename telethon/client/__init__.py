"""
This package defines clients as subclasses of others, and then a single
`telethon.client.telegramclient.TelegramClient` which is subclass of them
all to provide the final unified interface while the methods can live in
different subclasses to be more maintainable.

The ABC is `telethon.client.telegrambaseclient.TelegramBaseClient` and the
first implementor is `telethon.client.users.UserMethods`, since calling
requests require them to be resolved first, and that requires accessing
entities (users).
"""
