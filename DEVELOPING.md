Code generation:

```sh
pip install -e generator/
python -m telethon_generator.codegen api.tl client/src/telethon/_impl/tl
python -m telethon_generator.codegen mtproto.tl client/src/telethon/_impl/tl/mtproto
```

Formatting, type-checking and testing:

```
./check.sh
```
