Code generation:

```sh
pip install -e generator/
python tools/codegen.py
```

Formatting, type-checking and testing:

```sh
pip install isort black mypy pytest pytest-asyncio
python tools/check.py
```

Documentation:

```sh
pip install sphinx_rtd_theme
python tools/docgen.py
```
