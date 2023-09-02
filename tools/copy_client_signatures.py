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
import sys
from _ast import AsyncFunctionDef, ClassDef
from pathlib import Path
from typing import Dict, List, Union


class FunctionMethodsVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.methods: List[Union[ast.FunctionDef, ast.AsyncFunctionDef]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._try_add_def(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        self._try_add_def(node)

    def _try_add_def(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        match node.args.args:
            case [ast.arg(arg="self", annotation=ast.Name(id="Client")), *_]:
                self.methods.append(node)


class MethodVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self._in_client = False
        self.method_docs: Dict[str, str] = {}

    def visit_ClassDef(self, node: ClassDef) -> None:
        if node.name == "Client":
            assert not self._in_client
            self._in_client = True
            for subnode in node.body:
                self.visit(subnode)
            self._in_client = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._try_add_doc(node)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> None:
        self._try_add_doc(node)

    def _try_add_doc(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        if not self._in_client:
            return

        match node.body:
            case [ast.Expr(value=ast.Constant(value=str(doc))), *_]:
                self.method_docs[node.name] = doc


def main() -> None:
    client_root = Path.cwd() / sys.argv[1]

    fm_visitor = FunctionMethodsVisitor()
    m_visitor = MethodVisitor()

    for file in client_root.glob("*.py"):
        if file.stem in ("__init__", "client"):
            pass
        with file.open(encoding="utf-8") as fd:
            contents = fd.read()

        fm_visitor.visit(ast.parse(contents))

    with (client_root / "client.py").open(encoding="utf-8") as fd:
        contents = fd.read()

    m_visitor.visit(ast.parse(contents))

    for function in sorted(fm_visitor.methods, key=lambda f: f.name):
        function.body = []
        if doc := m_visitor.method_docs.get(function.name):
            function.body.append(ast.Expr(value=ast.Constant(value=doc)))

        call: ast.AST = ast.Call(
            func=ast.Name(id=function.name, ctx=ast.Load()),
            args=[ast.Name(id=a.arg, ctx=ast.Load()) for a in function.args.args],
            keywords=[
                ast.keyword(arg=a.arg, value=ast.Name(id=a.arg, ctx=ast.Load()))
                for a in function.args.kwonlyargs
            ],
        )

        function.args.args[0].annotation = None

        if isinstance(function, ast.AsyncFunctionDef):
            call = ast.Await(value=call)

        match function.returns:
            case ast.Constant(value=None):
                call = ast.Expr(value=call)
            case _:
                call = ast.Return(value=call)

        function.body.append(call)

        print(ast.unparse(function))


if __name__ == "__main__":
    main()
