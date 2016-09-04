# Telethon
**Telethon** is Telegram client implementation in Python. This project's _core_ is **completely based** on
[TLSharp](https://github.com/sochix/TLSharp). All the files which are fully based on it will have a notice
on the top of the file. Also don't forget to have a look to the original project.

The files without the previously mentioned notice are no longer part of TLSharp itself, or have enough modifications
to make them entirely different.

### Requirements
This project requires the following Python modules, which can be installed by issuing `sudo -H pip3 install <module>` on a
Linux terminal:
- `pyaes` ([GitHub](https://github.com/ricmoo/pyaes), [package index](https://pypi.python.org/pypi/pyaes))

Also, you need to obtain your both [API ID and Hash](my.telegram.org). Once you have them, head to `api/` and create a copy of
the `settings_example` file, naming it `settings` (lowercase!). Then fill the file with the corresponding values (your `api_id`,
`api_hash` and phone number in international format). Now it is when you're ready to go!

### Plans for the future
If everything works well, this probably ends up being a Python package :)

But as of now, and until that happens, help is highly appreciated!

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
