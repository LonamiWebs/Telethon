"""
Simple module to allow fetching unicode.org emoji lists and printing a
Python-like tuple out of them.

May not be accurate 100%, and is definitely not as efficient as it could be,
but it should only be ran whenever the Unicode consortium decides to add
new emojies to the list.
"""
import os
import sys
import re
import urllib.error
import urllib.request


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get(url, enc='utf-8'):
    try:
        with urllib.request.urlopen(url) as f:
            return f.read().decode(enc, errors='replace')
    except urllib.error.HTTPError as e:
        eprint('Caught', e, 'for', url, '; returning empty')
        return ''


PREFIX_URL = 'http://unicode.org/Public/emoji/'
SUFFIX_URL = '/emoji-data.txt', '/emoji-sequences.txt'
VERSION_RE = re.compile(r'>(\d+.\d+)/<')
OUTPUT_TXT = 'emojies.txt'
CODEPOINT_RE = re.compile(r'([\da-fA-F]{3,}(?:[\s.]+[\da-fA-F]{3,}))')
EMOJI_START = 0x20e3  # emoji data has many more ranges, falling outside this
EMOJI_END = 200000  # from some tests those outside the range aren't emojies


versions = VERSION_RE.findall(get(PREFIX_URL))
lines = []
if not os.path.isfile(OUTPUT_TXT):
    with open(OUTPUT_TXT, 'w') as f:
        for version in versions:
            for s in SUFFIX_URL:
                url = PREFIX_URL + version + s
                for line in get(url).split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    m = CODEPOINT_RE.search(line)
                    if m and m.start() == 0:
                        f.write(m.group(1) + '\n')


points = set()
with open(OUTPUT_TXT) as f:
    for line in f:
        line = line.strip()
        if ' ' in line:
            for p in line.split():
                i = int(p, 16)
                if i > 255:
                    points.add(i)
        elif '.' in line:
            s, e = line.split('..')
            for i in range(int(s, 16), int(e, 16) + 1):
                if i > 255:
                    points.add(i)
        else:
            i = int(line, 16)
            if i > 255:
                points.add(int(line, 16))


ranges = []
points = tuple(sorted(points))
start = points[0]
last = start
for point in points:
    if point - last > 1:
        if start == last or not (EMOJI_START < start < EMOJI_END):
            eprint(
                'Dropping', last - start + 1,
                'character(s) from', hex(start), ':', chr(start)
            )
        else:
            ranges.append((start, last))
        start = point

    last = point


if start == last or not (EMOJI_START < start < EMOJI_END):
    eprint(
        'Dropping', last - start + 1,
        'character(s) from', hex(start), ':', chr(start)
    )
else:
    ranges.append((start, last))


print('EMOJI_RANGES = ({})'.format(', '.join(repr(r) for r in ranges)))
