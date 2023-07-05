```sh
pip install -e generator/
python -m telethon_generator.codegen api.tl telethon/src/_impl/tl
python -m telethon_generator.codegen mtproto.tl telethon/src/_impl/tl/mtproto
```
