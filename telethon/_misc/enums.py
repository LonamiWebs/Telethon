from enum import Enum


def _impl_op(which):
    def op(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        return getattr(self._val(), which)(other._val())

    return op


class ConnectionMode(Enum):
    FULL = 'full'
    INTERMEDIATE = 'intermediate'
    ABRIDGED = 'abridged'


class Participant(Enum):
    ADMIN = 'admin'
    BOT = 'bot'
    KICKED = 'kicked'
    BANNED = 'banned'
    CONTACT = 'contact'


class Action(Enum):
    TYPING = 'typing'
    CONTACT = 'contact'
    GAME = 'game'
    LOCATION = 'location'
    STICKER = 'sticker'
    RECORD_AUDIO = 'record-audio'
    RECORD_VOICE = RECORD_AUDIO
    RECORD_ROUND = 'record-round'
    RECORD_VIDEO = 'record-video'
    AUDIO = 'audio'
    VOICE = AUDIO
    SONG = AUDIO
    ROUND = 'round'
    VIDEO = 'video'
    PHOTO = 'photo'
    DOCUMENT = 'document'
    FILE = DOCUMENT
    CANCEL = 'cancel'


class Size(Enum):
    """
    See https://core.telegram.org/api/files#image-thumbnail-types.

    * ``'s'``. The image fits within a box of 100x100.
    * ``'m'``. The image fits within a box of 320x320.
    * ``'x'``. The image fits within a box of 800x800.
    * ``'y'``. The image fits within a box of 1280x1280.
    * ``'w'``. The image fits within a box of 2560x2560.
    * ``'a'``. The image was cropped to be at most 160x160.
    * ``'b'``. The image was cropped to be at most 320x320.
    * ``'c'``. The image was cropped to be at most 640x640.
    * ``'d'``. The image was cropped to be at most 1280x1280.
    * ``'i'``. The image comes inline (no need to download anything).
    * ``'j'``. Only the image outline is present (for stickers).
    * ``'u'``. The image is actually a short MPEG4 animated video.
    * ``'v'``. The image is actually a short MPEG4 video preview.

    The sorting order is first dimensions, then ``cropped < boxed < video < other``.
    """
    SMALL = 's'
    MEDIUM = 'm'
    LARGE = 'x'
    EXTRA_LARGE = 'y'
    ORIGINAL = 'w'
    CROPPED_SMALL = 'a'
    CROPPED_MEDIUM = 'b'
    CROPPED_LARGE = 'c'
    CROPPED_EXTRA_LARGE = 'd'
    INLINE = 'i'
    OUTLINE = 'j'
    ANIMATED = 'u'
    VIDEO = 'v'

    def __hash__(self):
        return object.__hash__(self)

    __sub__ = _impl_op('__sub__')
    __lt__ = _impl_op('__lt__')
    __le__ = _impl_op('__le__')
    __eq__ = _impl_op('__eq__')
    __ne__ = _impl_op('__ne__')
    __gt__ = _impl_op('__gt__')
    __ge__ = _impl_op('__ge__')

    def _val(self):
        return self._category() * 100 + self._size()

    def _category(self):
        return {
            Size.SMALL: 2,
            Size.MEDIUM: 2,
            Size.LARGE: 2,
            Size.EXTRA_LARGE: 2,
            Size.ORIGINAL: 2,
            Size.CROPPED_SMALL: 1,
            Size.CROPPED_MEDIUM: 1,
            Size.CROPPED_LARGE: 1,
            Size.CROPPED_EXTRA_LARGE: 1,
            Size.INLINE: 4,
            Size.OUTLINE: 5,
            Size.ANIMATED: 3,
            Size.VIDEO: 3,
        }[self]

    def _size(self):
        return {
            Size.SMALL: 1,
            Size.MEDIUM: 3,
            Size.LARGE: 5,
            Size.EXTRA_LARGE: 6,
            Size.ORIGINAL: 7,
            Size.CROPPED_SMALL: 2,
            Size.CROPPED_MEDIUM: 3,
            Size.CROPPED_LARGE: 4,
            Size.CROPPED_EXTRA_LARGE: 6,
            # 0, since they're not the original photo at all
            Size.INLINE: 0,
            Size.OUTLINE: 0,
            # same size as original or extra large (videos are large)
            Size.ANIMATED: 7,
            Size.VIDEO: 6,
        }[self]
