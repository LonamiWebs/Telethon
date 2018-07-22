import abc
from ..tlobject import TLObject

# TODO Figure out a way to have the generator error on missing fields
# Maybe parsing the init function alone if that's possible.
class MessageBase(abc.ABC, TLObject):
    """
    This custom class aggregates both :tl:`Message` and
    :tl:`MessageService` to ease accessing their members.

    Members:
        id (`int`):
            The ID of this message. This field is *always* present.
            Any other member is optional and may be ``None``.

        out (`bool`):
            Whether the message is outgoing (i.e. you sent it from
            another session) or incoming (i.e. someone else sent it).

            Note that messages in your own chat are always incoming,
            but this member will be ``True`` if you send a message
            to your own chat. Messages you forward to your chat are
            *not* considered outgoing, just like official clients
            display them.

        mentioned (`bool`):
            Whether you were mentioned in this message or not.
            Note that replies to your own messages also count
            as mentions.

        media_unread (`bool`):
            Whether you have read the media in this message
            or not, e.g. listened to the voice note media.

        silent (`bool`):
            Whether this message should notify or not,
            used in channels.

        post (`bool`):
            Whether this message is a post in a broadcast
            channel or not.

        to_id (:tl:`Peer`):
            The peer to which this message was sent, which is either
            :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`. This
            will always be present except for empty messages.

        date (`datetime`):
            The UTC+0 `datetime` object indicating when this message
            was sent. This will always be present except for empty
            messages.

        message (`str`):
            The string text of the message for :tl:`Message` instances,
            which will be ``None`` for other types of messages.

        action (:tl:`MessageAction`):
            The message action object of the message for :tl:`MessageService`
            instances, which will be ``None`` for other types of messages.

        from_id (`int`):
            The ID of the user who sent this message. This will be
            ``None`` if the message was sent in a broadcast channel.

        reply_to_msg_id (`int`):
            The ID to which this message is replying to, if any.

        fwd_from (:tl:`MessageFwdHeader`):
            The original forward header if this message is a forward.
            You should probably use the `forward` property instead.

        via_bot_id (`int`):
            The ID of the bot used to send this message
            through its inline mode (e.g. "via @like").

        media (:tl:`MessageMedia`):
            The media sent with this message if any (such as
            photos, videos, documents, gifs, stickers, etc.).

            You may want to access the `photo`, `document`
            etc. properties instead.

        reply_markup (:tl:`ReplyMarkup`):
            The reply markup for this message (which was sent
            either via a bot or by a bot). You probably want
            to access `buttons` instead.

        entities (List[:tl:`MessageEntity`]):
            The list of markup entities in this message,
            such as bold, italics, code, hyperlinks, etc.

        views (`int`):
            The number of views this message from a broadcast
            channel has. This is also present in forwards.

        edit_date (`datetime`):
            The date when this message was last edited.

        post_author (`str`):
            The display name of the message sender to
            show in messages sent to broadcast channels.

        grouped_id (`int`):
            If this message belongs to a group of messages
            (photo albums or video albums), all of them will
            have the same value here.
    """
    def __init__(
            # Common to all
            self, id,

            # Common to Message and MessageService (mandatory)
            to_id=None, date=None,

            # Common to Message and MessageService (flags)
            out=None, mentioned=None, media_unread=None, silent=None,
            post=None, from_id=None, reply_to_msg_id=None,

            # For Message (mandatory)
            message=None,

            # For Message (flags)
            fwd_from=None, via_bot_id=None, media=None, reply_markup=None,
            entities=None, views=None, edit_date=None, post_author=None,
            grouped_id=None,

            # For MessageAction (mandatory)
            action=None):
        self.id = id
        self.to_id = to_id
        self.date = date
        self.out = out
        self.mentioned = mentioned
        self.media_unread = media_unread
        self.silent = silent
        self.post = post
        self.from_id = from_id
        self.reply_to_msg_id = reply_to_msg_id
        self.message = message
        self.fwd_from = fwd_from
        self.via_bot_id = via_bot_id
        self.media = media
        self.reply_markup = reply_markup
        self.entities = entities
        self.views = views
        self.edit_date = edit_date
        self.post_author = post_author
        self.grouped_id = grouped_id
        self.action = action
