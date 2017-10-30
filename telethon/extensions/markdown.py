"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
from enum import Enum

from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl
)


class Mode(Enum):
    """Different modes supported by Telegram's Markdown"""
    NONE = 0
    BOLD = 1
    ITALIC = 2
    CODE = 3
    PRE = 4
    URL = 5


# TODO Special cases, these aren't count as emojies. Alternatives?
# These were determined by generating all emojies with EMOJI_RANGES,
# sending the message through an official application, and cherry-picking
# which ones weren't rendered as emojies (from the beginning one). I am
# not responsible for dropping those characters that did not render with
# my font.
NOT_EMOJIES = {
    9733, 9735, 9736, 9737, 9738, 9739, 9740, 9741, 9743, 9744, 9746, 9750,
    9751, 9754, 9755, 9756, 9758, 9759, 9761, 9764, 9765, 9767, 9768, 9769,
    9771, 9772, 9773, 9776, 9777, 9778, 9779, 9780, 9781, 9782, 9783, 9787,
    9788, 9789, 9790, 9791, 9792, 9793, 9794, 9795, 9796, 9797, 9798, 9799,
    9812, 9813, 9814, 9815, 9816, 9817, 9818, 9819, 9820, 9821, 9822, 9823,
    9825, 9826, 9828, 9831, 9833, 9834, 9835, 9836, 9837, 9838, 9839, 9840,
    9841, 9842, 9843, 9844, 9845, 9846, 9847, 9848, 9849, 9850, 9852, 9853,
    9854, 9856, 9857, 9858, 9859, 9860, 9861, 9862, 9863, 9864, 9865, 9866,
    9867, 9868, 9869, 9870, 9871, 9872, 9873, 9877, 9880, 9882, 9886, 9887,
    9890, 9891, 9892, 9893, 9894, 9895, 9896, 9897, 9900, 9901, 9902, 9903,
    9907, 9908, 9909, 9910, 9911, 9912, 9920, 9921, 9922, 9923, 9985, 9987,
    9988, 9998, 10000, 10001, 10085, 10086, 10087, 127027, 127028, 127029,
    127030, 127031, 127032, 127033, 127034, 127035, 127036, 127037, 127038,
    127039, 127040, 127041, 127042, 127043, 127044, 127045, 127046, 127047,
    127048, 127049, 127050, 127051, 127052, 127053, 127054, 127055, 127056,
    127057, 127058, 127059, 127060, 127061, 127062, 127063, 127064, 127065,
    127066, 127067, 127068, 127069, 127070, 127071, 127072, 127073, 127074,
    127075, 127076, 127077, 127078, 127079, 127080, 127081, 127082, 127083,
    127084, 127085, 127086, 127087, 127088, 127089, 127090, 127091, 127092,
    127093, 127094, 127095, 127096, 127097, 127098, 127099, 127100, 127101,
    127102, 127103, 127104, 127105, 127106, 127107, 127108, 127109, 127110,
    127111, 127112, 127113, 127114, 127115, 127116, 127117, 127118, 127119,
    127120, 127121, 127122, 127123
}
# using telethon_generator/emoji_ranges.py
EMOJI_RANGES = (
    (8596, 8601), (8617, 8618), (8986, 8987), (9193, 9203), (9208, 9210),
    (9642, 9643), (9723, 9726), (9728, 9733), (9735, 9746), (9748, 9751),
    (9754, 9884), (9886, 9905), (9907, 9953), (9956, 9983), (9985, 9988),
    (9992, 10002), (10035, 10036), (10067, 10069), (10083, 10087),
    (10133, 10135), (10548, 10549), (11013, 11015), (11035, 11036),
    (126976, 127166), (127169, 127183), (127185, 127231), (127245, 127247),
    (127340, 127345), (127358, 127359), (127377, 127386), (127405, 127487),
    (127489, 127503), (127538, 127546), (127548, 127551), (127561, 128419),
    (128421, 128591), (128640, 128767), (128884, 128895), (128981, 129023),
    (129036, 129039), (129096, 129103), (129114, 129119), (129160, 129167),
    (129198, 129338), (129340, 129342), (129344, 129349), (129351, 129355),
    (129357, 129471), (129473, 131069)
)


DEFAULT_DELIMITERS = {
    '**': Mode.BOLD,
    '__': Mode.ITALIC,
    '`': Mode.CODE,
    '```': Mode.PRE
}

DEFAULT_URL_RE = re.compile(r'\[(.+?)\]\((.+?)\)')


def is_emoji(char):
    """Returns True if 'char' looks like an emoji"""
    char = ord(char)
    for start, end in EMOJI_RANGES:
        if start <= char <= end:
            return char not in NOT_EMOJIES
    return False


def emojiness(char):
    """
    Returns 2 if the character is an emoji, or 1 otherwise.
    This seems to be the length Telegram uses for offsets and lengths.
    """
    return 2 if is_emoji(char) else 1


def parse(message, delimiters=None, url_re=None):
    """
    Parses the given message and returns the stripped message and a list
    of tuples containing (start, end, mode) using the specified delimiters
    dictionary (or default if None).

    The url_re(gex) must contain two matching groups: the text to be
    clickable and the URL itself.
    """
    if url_re is None:
        url_re = DEFAULT_URL_RE
    elif url_re:
        if isinstance(url_re, str):
            url_re = re.compile(url_re)

    if not delimiters:
        if delimiters is not None:
            return message, []
        delimiters = DEFAULT_DELIMITERS

    result = []
    current = Mode.NONE
    offset = 0
    i = 0
    while i < len(message):
        url_match = None
        if url_re and current == Mode.NONE:
            url_match = url_re.match(message, pos=i)
            if url_match:
                message = ''.join((
                    message[:url_match.start()],
                    url_match.group(1),
                    message[url_match.end():]
                ))
                emoji_len = sum(emojiness(c) for c in url_match.group(1))
                result.append((
                    offset,
                    offset + emoji_len,
                    (Mode.URL, url_match.group(2))
                ))
                i += len(url_match.group(1))
        if not url_match:
            for d, m in delimiters.items():
                if message[i:i + len(d)] == d and current in (Mode.NONE, m):
                    if message[i + len(d):i + 2 * len(d)] == d:
                        continue  # ignore two consecutive delimiters

                    message = message[:i] + message[i + len(d):]
                    if current == Mode.NONE:
                        result.append(offset)
                        current = m
                    else:
                        result[-1] = (result[-1], offset, current)
                        current = Mode.NONE
                    break

        if i < len(message):
            offset += emojiness(message[i])
            i += 1

    if result and not isinstance(result[-1], tuple):
        result.pop()
    return message, result


def parse_tg(message, delimiters=None):
    """Similar to parse(), but returns a list of MessageEntity's"""
    message, tuples = parse(message, delimiters=delimiters)
    result = []
    for start, end, mode in tuples:
        extra = None
        if isinstance(mode, tuple):
            mode, extra = mode

        if mode == Mode.BOLD:
            result.append(MessageEntityBold(start, end - start))
        elif mode == Mode.ITALIC:
            result.append(MessageEntityItalic(start, end - start))
        elif mode == Mode.CODE:
            result.append(MessageEntityCode(start, end - start))
        elif mode == Mode.PRE:
            result.append(MessageEntityPre(start, end - start, ''))
        elif mode == Mode.URL:
            result.append(MessageEntityTextUrl(start, end - start, extra))
    return message, result
