from telethon.events.common import EventCommon
from telethon.tl.custom import Message


class NewMessage:
    class Event(EventCommon, Message): ...
