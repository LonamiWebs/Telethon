==========
Philosophy
==========


The intention of the library is to have an existing MTProto library
existing with hardly any dependencies (indeed, wherever Python is
available, you can run this library).

Being written in Python means that performance will be nowhere close to
other implementations written in, for instance, Java, C++, Rust, or
pretty much any other compiled language. However, the library turns out
to actually be pretty decent for common operations such as sending
messages, receiving updates, or other scripting. Uploading files may be
notably slower, but if you would like to contribute, pull requests are
appreciated!

If ``libssl`` is available on your system, the library will make use of
it to speed up some critical parts such as encrypting and decrypting the
messages. Files will notably be sent and downloaded faster.

The main focus is to keep everything clean and simple, for everyone to
understand how working with MTProto and Telegram works. Don't be afraid
to read the source, the code won't bite you! It may prove useful when
using the library on your own use cases.
