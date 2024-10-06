from pytest import mark

from telethon_generator._impl.codegen.serde.common import (
    split_words,
    to_class_name,
    to_method_name,
)


@mark.parametrize(
    ("name", "expected"),
    [
        ("resPQ", ["res", "PQ"]),
        ("p_q_inner_data", ["p", "q", "inner", "data"]),
        ("client_DH_inner_data", ["client", "DH", "inner", "data"]),
        ("ipPort", ["ip", "Port"]),
        ("JSONObjectValue", ["JSON", "Object", "Value"]),
        ("fileMp4", ["file", "Mp4"]),
    ],
)
def test_split_name_words(name: str, expected: list[str]) -> None:
    assert split_words(name) == expected


@mark.parametrize(
    ("name", "expected"),
    [
        ("resPQ", "ResPq"),
        ("p_q_inner_data", "PQInnerData"),
        ("client_DH_inner_data", "ClientDhInnerData"),
        ("ipPort", "IpPort"),
        ("JSONObjectValue", "JsonObjectValue"),
        ("fileMp4", "FileMp4"),
    ],
)
def test_to_class_name(name: str, expected: str) -> None:
    assert to_class_name(name) == expected


@mark.parametrize(
    ("name", "expected"),
    [
        ("resPQ", "res_pq"),
        ("p_q_inner_data", "p_q_inner_data"),
        ("client_DH_inner_data", "client_dh_inner_data"),
        ("ipPort", "ip_port"),
        ("JSONObjectValue", "json_object_value"),
        ("fileMp4", "file_mp4"),
    ],
)
def test_to_method_name(name: str, expected: str) -> None:
    assert to_method_name(name) == expected
