from pytest import mark, raises
from telethon_generator.tl_parser import (
    Definition,
    Flag,
    FlagsParameter,
    NormalParameter,
    Parameter,
    Type,
)


def test_parse_empty_def() -> None:
    with raises(ValueError) as e:
        Definition.from_str("")
    e.match("empty")


@mark.parametrize("defn", ["foo#bar = baz", "foo#? = baz", "foo# = baz"])
def test_parse_bad_id(defn: str) -> None:
    with raises(ValueError) as e:
        Definition.from_str(defn)
    e.match("invalid id")


def test_parse_no_name() -> None:
    with raises(ValueError) as e:
        Definition.from_str(" = foo")
    e.match("missing name")


@mark.parametrize("defn", ["foo", "foo ="])
def test_parse_no_type(defn: str) -> None:
    with raises(ValueError) as e:
        Definition.from_str(defn)
    e.match("missing type")


def test_parse_unimplemented() -> None:
    with raises(ValueError) as e:
        Definition.from_str("int ? = Int")
    e.match("not implemented")


@mark.parametrize(
    ("defn", "id"),
    [
        (
            "rpc_answer_dropped msg_id:long seq_no:int bytes:int = RpcDropAnswer",
            0xA43AD8B7,
        ),
        (
            "rpc_answer_dropped#123456 msg_id:long seq_no:int bytes:int = RpcDropAnswer",
            0x123456,
        ),
    ],
)
def test_parse_override_id(defn: str, id: int) -> None:
    assert Definition.from_str(defn).id == id


def test_parse_valid_definition() -> None:
    defn = Definition.from_str("a#1=d")
    assert defn.name == "a"
    assert defn.id == 1
    assert len(defn.params) == 0
    assert defn.ty == Type(
        namespace=[],
        name="d",
        bare=True,
        generic_ref=False,
        generic_arg=None,
    )

    defn = Definition.from_str("a=d<e>")
    assert defn.name == "a"
    assert defn.id != 0
    assert len(defn.params) == 0
    assert defn.ty == Type(
        namespace=[],
        name="d",
        bare=True,
        generic_ref=False,
        generic_arg=Type.from_str("e"),
    )

    defn = Definition.from_str("a b:c = d")
    assert defn.name == "a"
    assert defn.id != 0
    assert len(defn.params) == 1
    assert defn.ty == Type(
        namespace=[],
        name="d",
        bare=True,
        generic_ref=False,
        generic_arg=None,
    )

    defn = Definition.from_str("a#1 {b:Type} c:!b = d")
    assert defn.name, "a"
    assert defn.id, 1
    assert len(defn.params), 1
    assert isinstance(defn.params[0].ty, NormalParameter)
    assert defn.params[0].ty.ty.generic_ref
    assert defn.ty == Type(
        namespace=[],
        name="d",
        bare=True,
        generic_ref=False,
        generic_arg=None,
    )


def test_parse_multiline_definition() -> None:
    defn = """
        first#1 lol:param
            = t;
        """

    assert Definition.from_str(defn).id, 1

    defn = """
        second#2
            lol:String
        = t;
        """

    assert Definition.from_str(defn).id, 2

    defn = """
        third#3

            lol:String

        =
                    t;
        """

    assert Definition.from_str(defn).id, 3


def test_parse_complete() -> None:
    defn = "ns1.name#123 {X:Type} flags:# pname:flags.10?ns2.Vector<!X> = ns3.Type"
    assert Definition.from_str(defn) == Definition(
        namespace=["ns1"],
        name="name",
        id=0x123,
        params=[
            Parameter(
                name="flags",
                ty=FlagsParameter(),
            ),
            Parameter(
                name="pname",
                ty=NormalParameter(
                    ty=Type(
                        namespace=["ns2"],
                        name="Vector",
                        bare=False,
                        generic_ref=False,
                        generic_arg=Type(
                            namespace=[],
                            name="X",
                            bare=False,
                            generic_ref=True,
                            generic_arg=None,
                        ),
                    ),
                    flag=Flag(name="flags", index=10),
                ),
            ),
        ],
        ty=Type(
            namespace=["ns3"],
            name="Type",
            bare=False,
            generic_ref=False,
            generic_arg=None,
        ),
    )


@mark.parametrize(
    "defn",
    [
        "name param:!X = Type",
        "name {X:Type} param:!Y = Type",
        "name param:flags.0?true = Type",
        "name foo:# param:flags.0?true = Type",
    ],
)
def test_parse_missing_def(defn: str) -> None:
    with raises(ValueError) as e:
        Definition.from_str(defn)

    e.match("missing def")


def test_test_to_string() -> None:
    defn = "ns1.name#123 {X:Type} flags:# pname:flags.10?ns2.Vector<!X> = ns3.Type"
    assert str(Definition.from_str(defn)), defn
