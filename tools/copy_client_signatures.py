"""
Scan the `client/` directory, take all function definitions with `self: Client`
as the first parameter, and generate the corresponding `Client` methods to call
them, with matching signatures.

The documentation previously existing in the `Client` definitions is preserved.

Imports of new definitions and formatting must be added with other tools.

Properties and private methods can use a different parameter name than `self`
to avoid being included.
"""

import ast
import subprocess
import sys
from pathlib import Path


class FunctionMethodsVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._try_add_def(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._try_add_def(node)

    def _try_add_def(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        match node.args.posonlyargs + node.args.args:
            case [ast.arg(arg="self", annotation=ast.Name(id="Client")), *_]:
                self.methods.append(node)
            case _:
                pass


class MethodVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self._in_client = False
        self.method_docs: dict[str, str] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == "Client":
            assert not self._in_client
            self._in_client = True
            for subnode in node.body:
                self.visit(subnode)
            self._in_client = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._try_add_doc(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._try_add_doc(node)

    def _try_add_doc(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not self._in_client:
            return

        match node.body:
            case [ast.Expr(value=ast.Constant(value=str(doc))), *_]:
                self.method_docs[node.name] = doc
            case _:
                pass


def main() -> None:
    client_root = Path.cwd() / "client/src/telethon/_impl/client/client"
    client_py = client_root / "client.py"

    fm_visitor = FunctionMethodsVisitor()
    m_visitor = MethodVisitor()

    for file in client_root.glob("*.py"):
        if file.stem in ("__init__", "client"):
            pass
        with file.open(encoding="utf-8") as fd:
            contents = fd.read()

        fm_visitor.visit(ast.parse(contents))

    with client_py.open(encoding="utf-8") as fd:
        contents = fd.read()

    m_visitor.visit(ast.parse(contents))

    class_body: list[ast.stmt] = []

    for function in sorted(fm_visitor.methods, key=lambda f: f.name):
        function.body.clear()
        if doc := m_visitor.method_docs.get(function.name):
            function.body.append(ast.Expr(value=ast.Constant(value=doc)))

        call: ast.AST = ast.Call(
            func=ast.Name(id=function.name, ctx=ast.Load()),
            args=[
                ast.Name(id=a.arg, ctx=ast.Load())
                for a in function.args.posonlyargs + function.args.args
            ],
            keywords=[
                ast.keyword(arg=a.arg, value=ast.Name(id=a.arg, ctx=ast.Load()))
                for a in function.args.kwonlyargs
            ],
        )

        if function.args.posonlyargs:
            function.args.posonlyargs[0].annotation = None
        else:
            function.args.args[0].annotation = None

        if isinstance(function, ast.AsyncFunctionDef):
            call = ast.Await(value=call)  # type: ignore [arg-type]

        match function.returns:
            case ast.Constant(value=None):
                call = ast.Expr(value=call)  # type: ignore [arg-type]
            case _:
                call = ast.Return(value=call)  # type: ignore [arg-type]

        function.body.append(call)
        class_body.append(function)

    generated = ast.unparse(
        ast.ClassDef(
            name="Client",
            bases=[],
            keywords=[],
            body=class_body,
            decorator_list=[],
            type_params=[],
        )
    )[len("class Client:") :].strip()

    start_idx = contents.index("\n", contents.index("# Begin partially @generated"))
    end_idx = contents.index("# End partially @generated")

    with client_py.open("w", encoding="utf-8") as fd:
        fd.write(
            f"{contents[:start_idx]}\n\n    {generated}\n\n    {contents[end_idx:]}"
        )

    print("written @generated")
    exit(subprocess.run((sys.executable, "-m", "black", str(client_py))).returncode)


if __name__ == "__main__":
    main()
