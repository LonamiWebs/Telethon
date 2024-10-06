from typing import Optional

from pytest import mark, raises

from telethon_generator.tl_parser import Type


def test_empty_simple() -> None:
    with raises(ValueError) as e:
        Type.from_str("")
    e.match("empty")


def test_simple() -> None:
    assert Type.from_str("foo") == Type(
        namespace=[], name="foo", bare=True, generic_ref=False, generic_arg=None
    )


@mark.parametrize("ty", [".", "..", ".foo", "foo.", "foo..foo", ".foo."])
def test_check_empty_namespaced(ty: str) -> None:
    with raises(ValueError) as e:
        Type.from_str(ty)
        e.match("empty")


def test_check_namespaced() -> None:
    assert Type.from_str("foo.bar.baz") == Type(
        namespace=["foo", "bar"],
        name="baz",
        bare=True,
        generic_ref=False,
        generic_arg=None,
    )


@mark.parametrize(
    "ty",
    [
        "foo",
        "Foo.bar",
        "!bar",
    ],
)
def test_bare(ty: str) -> None:
    assert Type.from_str(ty).bare


@mark.parametrize(
    "ty",
    [
        "Foo",
        "Foo.Bar",
        "!foo.Bar",
    ],
)
def test_bare_not(ty: str) -> None:
    assert not Type.from_str(ty).bare


@mark.parametrize(
    "ty",
    [
        "!f",
        "!Foo",
        "!X",
    ],
)
def test_generic_ref(ty: str) -> None:
    assert Type.from_str(ty).generic_ref


def test_generic_ref_not() -> None:
    assert not Type.from_str("f").generic_ref


@mark.parametrize(
    ("ty", "generic"),
    [
        ("foo.bar", None),
        ("foo<bar>", "bar"),
        ("foo<bar.Baz>", "bar.Baz"),
        ("foo<!bar.Baz>", "!bar.Baz"),
        ("foo<bar<baz>>", "bar<baz>"),
    ],
)
def test_generic_arg(ty: str, generic: Optional[str]) -> None:
    if generic is None:
        assert Type.from_str(ty).generic_arg is None
    else:
        assert Type.from_str(ty).generic_arg == Type.from_str(generic)
