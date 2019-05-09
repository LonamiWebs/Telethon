===============================
Understanding the Type Language
===============================


`Telegram's Type Language <https://core.telegram.org/mtproto/TL>`__
(also known as TL, found on ``.tl`` files) is a concise way to define
what other programming languages commonly call classes or structs.

Every definition is written as follows for a Telegram object is defined
as follows:

    ``name#id argument_name:argument_type = CommonType``

This means that in a single line you know what the ``TLObject`` name is.
You know it's unique ID, and you know what arguments it has. It really
isn't that hard to write a generator for generating code to any
platform!

The generated code should also be able to *encode* the ``TLObject`` (let
this be a request or a type) into bytes, so they can be sent over the
network. This isn't a big deal either, because you know how the
``TLObject``\ 's are made, and how the types should be serialized.

You can either write your own code generator, or use the one this
library provides, but please be kind and keep some special mention to
this project for helping you out.

This is only a introduction. The ``TL`` language is not *that* easy. But
it's not that hard either. You're free to sniff the
``telethon_generator/`` files and learn how to parse other more complex
lines, such as ``flags`` (to indicate things that may or may not be
written at all) and ``vector``\ 's.
