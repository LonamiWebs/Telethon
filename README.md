# Telethon
**Telethon** is Telegram client implementation in Python. This project's _core_ is **completely based** on
[TLSharp](https://github.com/sochix/TLSharp). All the files which are fully based on it will have a notice
on the top of the file. Also don't forget to have a look to the original project.

The files without the previously mentioned notice are no longer part of TLSharp itself, or have enough modifications
to make them entirely different.

# Table of contents
- [Why Telethon?](#why-telethon)
- [Requirements](#requirements)
  - [Python modules](#python-modules)
  - [Obtaining your `API ID` and `Hash`](#obtaining-your-api-id-and-hash)
- [Running Telethon](#running-telethon)
- [Advanced uses](#advanced-uses)
  - [How to add more functions to `TelegramClient`](#how-to-add-more-functions-to-telegramclient)
  - [Tips for porting Telethon](#tips-for-porting-telethon)
  - [Code generator limitations](#code-generator-limitations)
- [Plans for the future](#plans-for-the-future)

## Why Telethon?
> Why should I bother with Telethon? You already mentioned [TLSharp](https://github.com/sochix/TLSharp).
> [telegram-cli](https://github.com/vysheng/tg) has also been around for a long while. And we have the
> [official](https://github.com/telegramdesktop/tdesktop) [clients](https://github.com/DrKLO/Telegram)!

With Telethon you don't really need to know anything before using it. Create a client with your settings.
Connect. You're ready to go.

Being written on Python, Telethon can run as a script under any environment you wish, (yes,
[Android too](https://f-droid.org/repository/browse/?fdfilter=termux&fdid=com.termux)). You can schedule it,
or use it in any other script you have. Want to send a message to someone when you're available? Write a script.
Do you want check for new messages at a given time and find relevant ones? Write a script.

An official client has a feature which Telethon doesn't? [Implement it easily](#how-to-add-more-functions-to-telegramclient).

## Requirements
### Python modules
This project requires the following Python modules, which can be installed by issuing `sudo -H pip3 install <module>` on a
Linux terminal:
- `pyaes` ([GitHub](https://github.com/ricmoo/pyaes), [package index](https://pypi.python.org/pypi/pyaes))

### Obtaining your `API ID` and `Hash`
1. Follow [this link](https://my.telegram.org) and login with your phone number.
2. Click under `API Development tools`.
3. A `Create new application` window will appear. Fill in your application details.
There is no need to enter any `URL`, and only the first two fields (`App title` and `Short name`)
can be changed later as long as I'm aware.
4. Click on `Create application` at the end. Now that you have the `API ID` and `Hash`,
head to `api/` directory and create a copy of the `settings_example` file, naming it `settings` (lowercase!).
Then fill the file with the corresponding values (your `api_id`, `api_hash` and phone number in international format).

## Running Telethon
First of all, you need to run the `tl_generator.py` by issuing `python3 tl_generator.py`. This will generate all the
TLObjects from the given `scheme.tl` file. When it's done, you can run `python3 main.py` to start the interactive example.

## Advanced uses
### How to add more functions to `TelegramClient`
As of now, you cannot call any Telegram function unless you first write it by hand under `tl/telegram_client.py`. Why?
Every Telegram function (or _Request_) work in its own way. In some, you may only be interested in a single result field,
and in others you may need to format the result in a different way. However, a plan for the future is to be able to call
any function by giving its `namespace.name` and passing the arguments. But until that happens, to add a new function do:

1. Have a look under `tl/functions/` and find the `Request` that suits your needs.
2. Have a look inside that `Request` you chose, and find what arguments and in what order you'll need to call it.
3. Import it in `tl/telegram_client.py` by using `from tl.functions import SomeTelegramRequest`.
4. Add a new method, or function, that looks as follows:
```python
def my_function(self, my_arguments):
    request = SomeTelegramRequest(my_arguments)

    self.sender.send(request)
    self.sender.receive(request)
    
    return request.result
```
To determine how the result will look like, simply look at the original `.tl` definition. After the `=`,
you will see the type. Let's see an example:
`stickerPack#12b299d4 emoticon:string documents:Vector<long> = StickerPack;`

As it turns out, the result is going to be an `StickerPack`. Without a second doubt, head into `tl/types/` and find it;
open the file and see what the result will look like. Alternatively, you can simply `print(str(request.result))`!

Be warned that there may be more than one different type on the results. This is due to Telegram's polymorphism,
for example, a message may or not be empty, etc.

_Hint: You could even write your own class based on `TelegramClient` and add more features._

### Tips for porting Telethon
First of all, you need to understand how the `scheme.tl` (`TL` language) works. Every object definition is written as follows:

`name#id argument_name:argument_type = CommonType`

This means that in a single line you know what the `TLObject` name is. You know it's unique ID,
and you know what arguments it has. It really isn't that hard to write a generator for generating code to any platform!

The generated code should also be able to _encode_ the `Request` into bytes, so they can be sent over the network.
This isn't a big deal either, because you know how the `TLObject`'s are made.

Once you have your own [code generator](tl_generator.py), start by looking at the
[first release](https://github.com/LonamiWebs/Telethon/releases/tag/v0.1) of Telethon.
The code there is simple to understand, easy to read and hence easy to port. No extra useless features.
Only the bare bones. Perfect for starting a _new implementation_.

P.S.: I may have lied a bit. The `TL` language is not that easy. But it's not that hard either.
You're free to sniff the `parser/` files and learn how to parse other more complex lines.
Or simply use that code and change the [SourceBuilder](parser/source_builder.py)!

### Code generator limitations
The current code generator is not complete, yet adding the missing features would only over-complicate an already hard-to-read code.
Some parts of the `.tl` file _should_ be omitted, because they're "built-in" in the generated code (such as writing booleans, etc.).

In order to make sure that all the generated files will work, please make sure to **always** comment out these lines in `scheme.tl`
(the latest version can always be found
[here](https://github.com/telegramdesktop/tdesktop/blob/master/Telegram/SourceFiles/mtproto/scheme.tl)):

```tl
// boolFalse#bc799737 = Bool;
// boolTrue#997275b5 = Bool;
// true#3fedd339 = True;
// vector#1cb5c415 {t:Type} # [ t ] = Vector t;
```

Also please make sure to rename `updates#74ae4240 ...` to `updates_tg#74ae4240 ...` or similar to avoid confusion between
the `updates` folder and the `updates.py` file!

## Plans for the future
If everything works well, this probably ends up being a Python package :)

But as of now, and until that happens, help is highly appreciated!
