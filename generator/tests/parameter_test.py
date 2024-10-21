from pytest import mark, raises

from telethon_generator.tl_parser import (
    Flag,
    FlagsParameter,
    NormalParameter,
    Parameter,
    Type,
    TypeDefNotImplementedError,
)


@mark.parametrize("param", [":noname", "notype:", ":"])
def test_empty_param(param: str) -> None:
    with raises(ValueError) as e:
        Parameter.from_str(param)
    e.match("empty")


@mark.parametrize("param", ["", "no colon", "colonless"])
def test_unknown_param(param: str) -> None:
    with raises(ValueError) as e:
        Parameter.from_str(param)
    e.match("not implemented")


@mark.parametrize("param", ["foo:bar?", "foo:?bar", "foo:bar?baz", "foo:bar.baz?qux"])
def test_bad_flags(param: str) -> None:
    with raises(ValueError) as e:
        Parameter.from_str(param)
    e.match("invalid flag")


@mark.parametrize("param", ["foo:<bar", "foo:bar<"])
def test_bad_generics(param: str) -> None:
    with raises(ValueError) as e:
        Parameter.from_str(param)
    e.match("invalid generic")


def test_type_def_param() -> None:
    with raises(TypeDefNotImplementedError) as e:
        Parameter.from_str("{a:Type}")
    e.match("typedef not implemented: a")


def test_unknown_def_param() -> None:
    with raises(ValueError) as e:
        Parameter.from_str("{a:foo}")
    e.match("missing def")


def test_valid_param() -> None:
    assert Parameter.from_str("foo:#") == Parameter(name="foo", ty=FlagsParameter())
    assert Parameter.from_str("foo:!bar") == Parameter(
        name="foo",
        ty=NormalParameter(
            ty=Type(
                namespace=[], name="bar", bare=True, generic_ref=True, generic_arg=None
            ),
            flag=None,
        ),
    )
    assert Parameter.from_str("foo:bar.1?baz") == Parameter(
        name="foo",
        ty=NormalParameter(
            ty=Type(
                namespace=[], name="baz", bare=True, generic_ref=False, generic_arg=None
            ),
            flag=Flag(
                name="bar",
                index=1,
            ),
        ),
    )
    assert Parameter.from_str("foo:bar<baz>") == Parameter(
        name="foo",
        ty=NormalParameter(
            ty=Type(
                namespace=[],
                name="bar",
                bare=True,
                generic_ref=False,
                generic_arg=Type.from_str("baz"),
            ),
            flag=None,
        ),
    )
    assert Parameter.from_str("foo:bar.1?baz<qux>") == Parameter(
        name="foo",
        ty=NormalParameter(
            ty=Type(
                namespace=[],
                name="baz",
                bare=True,
                generic_ref=False,
                generic_arg=Type.from_str("qux"),
            ),
            flag=Flag(name="bar", index=1),
        ),
    )
