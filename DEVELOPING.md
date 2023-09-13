Code generation:

```sh
pip install -e generator/
python tools/codegen.py
```

Formatting, type-checking and testing:

```sh
pip install -e client/[dev]
python tools/check.py
```

Documentation (requires [sphinx](https://www.sphinx-doc.org) and [graphviz](https://www.graphviz.org)'s `dot`):

```sh
pip install -e client/[doc]
python tools/docgen.py
```

Note that multiple optional dependency sets can be specified by separating them with a comma (`[dev,doc]`).
