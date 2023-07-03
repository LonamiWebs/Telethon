import datetime
from typing import Any

EPOCH = datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
BYTES = bytes(range(256))
SINGLE_WORD = "Lorem"
SHORT_TEXT = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Suspendisse purus."
)


class Obj:
    def __init__(self, **kwargs: Any):
        self.__dict__ = kwargs


class Channel(Obj):
    pass


class ChatPhoto(Obj):
    pass


class Document(Obj):
    pass


class DocumentAttributeAnimated(Obj):
    pass


class DocumentAttributeFilename(Obj):
    pass


class DocumentAttributeImageSize(Obj):
    pass


class DocumentAttributeVideo(Obj):
    pass


class Message(Obj):
    pass


class MessageEntityUrl(Obj):
    pass


class MessageMediaWebPage(Obj):
    pass


class Page(Obj):
    pass


class PageBlockAnchor(Obj):
    pass


class PageBlockAuthorDate(Obj):
    pass


class PageBlockBlockquote(Obj):
    pass


class PageBlockChannel(Obj):
    pass


class PageBlockCover(Obj):
    pass


class PageBlockHeader(Obj):
    pass


class PageBlockParagraph(Obj):
    pass


class PageBlockPhoto(Obj):
    pass


class PageBlockRelatedArticles(Obj):
    pass


class PageBlockTitle(Obj):
    pass


class PageBlockVideo(Obj):
    pass


class PageCaption(Obj):
    pass


class PageRelatedArticle(Obj):
    pass


class PeerUser(Obj):
    pass


class Photo(Obj):
    pass


class PhotoSize(Obj):
    pass


class PhotoSizeProgressive(Obj):
    pass


class PhotoStrippedSize(Obj):
    pass


class TextBold(Obj):
    pass


class TextConcat(Obj):
    pass


class TextEmpty(Obj):
    pass


class TextImage(Obj):
    pass


class TextItalic(Obj):
    pass


class TextPlain(Obj):
    pass


class TextUrl(Obj):
    pass


class WebPage(Obj):
    pass


DATA = Message(
    id=123456789,
    peer_id=PeerUser(user_id=123456789),
    date=EPOCH,
    message=SINGLE_WORD,
    out=True,
    mentioned=False,
    media_unread=False,
    silent=False,
    post=False,
    from_scheduled=False,
    legacy=False,
    edit_hide=False,
    pinned=False,
    noforwards=False,
    from_id=None,
    fwd_from=None,
    via_bot_id=None,
    reply_to=None,
    media=MessageMediaWebPage(
        webpage=WebPage(
            id=122333444455555,
            url=SINGLE_WORD,
            display_url=SINGLE_WORD,
            hash=123456789,
            type=SINGLE_WORD,
            site_name=SINGLE_WORD,
            title=SHORT_TEXT,
            description=SHORT_TEXT,
            photo=Photo(
                id=122333444455555,
                access_hash=122333444455555,
                file_reference=BYTES,
                date=EPOCH,
                sizes=[
                    PhotoStrippedSize(
                        type=SINGLE_WORD,
                        bytes=BYTES,
                    ),
                    PhotoSize(
                        type=SINGLE_WORD, w=123456789, h=123456789, size=123456789
                    ),
                    PhotoSizeProgressive(
                        type=SINGLE_WORD,
                        w=123456789,
                        h=123456789,
                        sizes=[
                            123456789,
                            123456789,
                            123456789,
                            123456789,
                            123456789,
                        ],
                    ),
                ],
                dc_id=123456789,
                has_stickers=False,
                video_sizes=[],
            ),
            embed_url=None,
            embed_type=None,
            embed_width=None,
            embed_height=None,
            duration=None,
            author=SINGLE_WORD,
            document=None,
            cached_page=Page(
                url=SINGLE_WORD,
                blocks=[
                    PageBlockCover(
                        cover=PageBlockPhoto(
                            photo_id=122333444455555,
                            caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                            url=None,
                            webpage_id=None,
                        )
                    ),
                    PageBlockChannel(
                        channel=Channel(
                            id=123456789,
                            title=SHORT_TEXT,
                            photo=ChatPhoto(
                                photo_id=122333444455555,
                                dc_id=123456789,
                                has_video=True,
                                stripped_thumb=BYTES,
                            ),
                            date=EPOCH,
                            creator=False,
                            left=False,
                            broadcast=True,
                            verified=True,
                            megagroup=False,
                            restricted=False,
                            signatures=False,
                            min=True,
                            scam=False,
                            has_link=False,
                            has_geo=False,
                            slowmode_enabled=False,
                            call_active=False,
                            call_not_empty=False,
                            fake=False,
                            gigagroup=False,
                            noforwards=False,
                            join_to_send=False,
                            join_request=False,
                            forum=False,
                            access_hash=122333444455555,
                            username=SINGLE_WORD,
                            restriction_reason=[],
                            admin_rights=None,
                            banned_rights=None,
                            default_banned_rights=None,
                            participants_count=None,
                            usernames=[],
                        )
                    ),
                    PageBlockTitle(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockAuthorDate(
                        author=TextPlain(text=SINGLE_WORD),
                        published_date=EPOCH,
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=122333444455555,
                                ),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockVideo(
                        video_id=122333444455555,
                        caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                        autoplay=True,
                        loop=True,
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextItalic(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextItalic(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SINGLE_WORD),
                            ]
                        )
                    ),
                    PageBlockBlockquote(
                        text=TextItalic(
                            text=TextConcat(
                                texts=[
                                    TextPlain(text=SHORT_TEXT),
                                    TextBold(text=TextPlain(text=SHORT_TEXT)),
                                    TextPlain(text=SHORT_TEXT),
                                    TextBold(text=TextPlain(text=SHORT_TEXT)),
                                    TextPlain(text=SINGLE_WORD),
                                ]
                            )
                        ),
                        caption=TextEmpty(),
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockVideo(
                        video_id=122333444455555,
                        caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                        autoplay=True,
                        loop=True,
                    ),
                    PageBlockBlockquote(
                        text=TextItalic(
                            text=TextConcat(
                                texts=[
                                    TextPlain(text=SHORT_TEXT),
                                    TextBold(text=TextPlain(text=SHORT_TEXT)),
                                    TextPlain(text=SHORT_TEXT),
                                    TextItalic(text=TextPlain(text=SHORT_TEXT)),
                                    TextPlain(text=SHORT_TEXT),
                                    TextUrl(
                                        text=TextPlain(text=SHORT_TEXT),
                                        url=SINGLE_WORD,
                                        webpage_id=122333444455555,
                                    ),
                                    TextPlain(text=SHORT_TEXT),
                                ]
                            )
                        ),
                        caption=TextEmpty(),
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockVideo(
                        video_id=122333444455555,
                        caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                        autoplay=True,
                        loop=True,
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockBlockquote(
                        text=TextItalic(
                            text=TextConcat(
                                texts=[
                                    TextPlain(text=SHORT_TEXT),
                                    TextImage(
                                        document_id=122333444455555,
                                        w=123456789,
                                        h=123456789,
                                    ),
                                    TextPlain(text=SINGLE_WORD),
                                    TextItalic(text=TextPlain(text=SHORT_TEXT)),
                                    TextPlain(text=SHORT_TEXT),
                                    TextImage(
                                        document_id=122333444455555,
                                        w=123456789,
                                        h=123456789,
                                    ),
                                    TextPlain(text=SINGLE_WORD),
                                    TextItalic(text=TextPlain(text=SHORT_TEXT)),
                                    TextPlain(text=SHORT_TEXT),
                                ]
                            )
                        ),
                        caption=TextEmpty(),
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=122333444455555,
                                ),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SINGLE_WORD),
                            ]
                        )
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextItalic(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SINGLE_WORD),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                            ]
                        )
                    ),
                    PageBlockVideo(
                        video_id=122333444455555,
                        caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                        autoplay=True,
                        loop=True,
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=122333444455555,
                                ),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockBlockquote(
                        text=TextItalic(
                            text=TextConcat(
                                texts=[
                                    TextPlain(text=SHORT_TEXT),
                                    TextUrl(
                                        text=TextPlain(text=SINGLE_WORD),
                                        url=SINGLE_WORD,
                                        webpage_id=123456789,
                                    ),
                                    TextPlain(text=SHORT_TEXT),
                                ]
                            )
                        ),
                        caption=TextEmpty(),
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextItalic(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SINGLE_WORD),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SINGLE_WORD),
                            ]
                        )
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockVideo(
                        video_id=122333444455555,
                        caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                        autoplay=True,
                        loop=True,
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SHORT_TEXT),
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockAnchor(name=SINGLE_WORD),
                    PageBlockHeader(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextUrl(
                                    text=TextPlain(text=SHORT_TEXT),
                                    url=SINGLE_WORD,
                                    webpage_id=123456789,
                                ),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                            ]
                        )
                    ),
                    PageBlockParagraph(
                        text=TextConcat(
                            texts=[
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SINGLE_WORD)),
                                TextPlain(text=SHORT_TEXT),
                                TextBold(text=TextPlain(text=SHORT_TEXT)),
                                TextPlain(text=SINGLE_WORD),
                            ]
                        )
                    ),
                    PageBlockVideo(
                        video_id=122333444455555,
                        caption=PageCaption(text=TextEmpty(), credit=TextEmpty()),
                        autoplay=True,
                        loop=True,
                    ),
                    PageBlockParagraph(text=TextPlain(text=SHORT_TEXT)),
                    PageBlockParagraph(text=TextPlain(text=SINGLE_WORD)),
                    PageBlockRelatedArticles(
                        title=TextPlain(text=SHORT_TEXT),
                        articles=[
                            PageRelatedArticle(
                                url=SINGLE_WORD,
                                webpage_id=122333444455555,
                                title=SHORT_TEXT,
                                description=SHORT_TEXT,
                                photo_id=122333444455555,
                                author=SINGLE_WORD,
                                published_date=EPOCH,
                            ),
                            PageRelatedArticle(
                                url=SINGLE_WORD,
                                webpage_id=122333444455555,
                                title=SHORT_TEXT,
                                description=SHORT_TEXT,
                                photo_id=122333444455555,
                                author=SINGLE_WORD,
                                published_date=EPOCH,
                            ),
                            PageRelatedArticle(
                                url=SINGLE_WORD,
                                webpage_id=122333444455555,
                                title=SHORT_TEXT,
                                description=SHORT_TEXT,
                                photo_id=122333444455555,
                                author=SINGLE_WORD,
                                published_date=EPOCH,
                            ),
                            PageRelatedArticle(
                                url=SINGLE_WORD,
                                webpage_id=122333444455555,
                                title=SHORT_TEXT,
                                description=SHORT_TEXT,
                                photo_id=122333444455555,
                                author=SINGLE_WORD,
                                published_date=EPOCH,
                            ),
                        ],
                    ),
                ],
                photos=[
                    Photo(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        sizes=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSizeProgressive(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                sizes=[
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                ],
                            ),
                        ],
                        dc_id=123456789,
                        has_stickers=False,
                        video_sizes=[],
                    ),
                    Photo(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        sizes=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSizeProgressive(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                sizes=[
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                ],
                            ),
                        ],
                        dc_id=123456789,
                        has_stickers=False,
                        video_sizes=[],
                    ),
                    Photo(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        sizes=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSizeProgressive(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                sizes=[
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                ],
                            ),
                        ],
                        dc_id=123456789,
                        has_stickers=False,
                        video_sizes=[],
                    ),
                    Photo(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        sizes=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                            PhotoSizeProgressive(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                sizes=[
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                    123456789,
                                ],
                            ),
                        ],
                        dc_id=123456789,
                        has_stickers=False,
                        video_sizes=[],
                    ),
                ],
                documents=[
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeImageSize(w=123456789, h=123456789),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeImageSize(w=123456789, h=123456789),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=123456789,
                                w=123456789,
                                h=123456789,
                                round_message=False,
                                supports_streaming=True,
                            ),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                            DocumentAttributeAnimated(),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=123456789,
                                w=123456789,
                                h=123456789,
                                round_message=False,
                                supports_streaming=True,
                            ),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                            DocumentAttributeAnimated(),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=123456789,
                                w=123456789,
                                h=123456789,
                                round_message=False,
                                supports_streaming=True,
                            ),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                            DocumentAttributeAnimated(),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=123456789,
                                w=123456789,
                                h=123456789,
                                round_message=False,
                                supports_streaming=True,
                            ),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                            DocumentAttributeAnimated(),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=123456789,
                                w=123456789,
                                h=123456789,
                                round_message=False,
                                supports_streaming=True,
                            ),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                            DocumentAttributeAnimated(),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                    Document(
                        id=122333444455555,
                        access_hash=122333444455555,
                        file_reference=BYTES,
                        date=EPOCH,
                        mime_type=SINGLE_WORD,
                        size=123456789,
                        dc_id=123456789,
                        attributes=[
                            DocumentAttributeVideo(
                                duration=123456789,
                                w=123456789,
                                h=123456789,
                                round_message=False,
                                supports_streaming=True,
                            ),
                            DocumentAttributeFilename(file_name=SINGLE_WORD),
                            DocumentAttributeAnimated(),
                        ],
                        thumbs=[
                            PhotoStrippedSize(
                                type=SINGLE_WORD,
                                bytes=BYTES,
                            ),
                            PhotoSize(
                                type=SINGLE_WORD,
                                w=123456789,
                                h=123456789,
                                size=123456789,
                            ),
                        ],
                        video_thumbs=[],
                    ),
                ],
                part=False,
                rtl=False,
                v2=True,
                views=None,
            ),
            attributes=[],
        )
    ),
    reply_markup=None,
    entities=[
        MessageEntityUrl(offset=123456789, length=123456789),
    ],
    views=None,
    forwards=None,
    replies=None,
    edit_date=None,
    post_author=None,
    grouped_id=None,
    reactions=None,
    restriction_reason=[],
    ttl_period=None,
)
