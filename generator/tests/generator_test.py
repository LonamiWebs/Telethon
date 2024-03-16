from typing import List, Optional

from telethon_generator.codegen import FakeFs, generate
from telethon_generator.tl_parser import Definition, ParsedTl, parse_tl_file


def get_definitions(contents: str) -> List[Definition]:
    return [defn for defn in parse_tl_file(contents) if not isinstance(defn, Exception)]


def gen_py_code(
    *,
    typedefs: Optional[List[Definition]] = None,
    functiondefs: Optional[List[Definition]] = None,
) -> str:
    fs = FakeFs()
    generate(
        fs, ParsedTl(layer=0, typedefs=typedefs or [], functiondefs=functiondefs or [])
    )
    generated = bytearray()
    for path, data in fs._files.items():
        if path.stem not in ("__init__", "layer"):
            generated += f"# {path}\n".encode("utf-8")
            generated += data
            data += b"\n"
    return str(generated, "utf-8")


def test_generic_functions_use_bytes_parameters() -> None:
    definitions = get_definitions(
        "invokeWithLayer#da9b0d0d {X:Type} layer:int query:!X = X;"
    )
    result = gen_py_code(functiondefs=definitions)
    assert "invoke_with_layer" in result
    assert "query: _bytes" in result
    assert "buffer += query" in result


def test_recursive_direct() -> None:
    definitions = get_definitions("textBold#6724abc4 text:RichText = RichText;")
    result = gen_py_code(typedefs=definitions)
    assert "text: abcs.RichText" in result
    assert "read_serializable" in result
    assert "write_boxed_to" in result


def test_recursive_indirect() -> None:
    definitions = get_definitions(
        """
        messageExtendedMedia#ee479c64 media:MessageMedia = MessageExtendedMedia;
        messageMediaInvoice#f6a548d3 flags:# extended_media:flags.4?MessageExtendedMedia = MessageMedia;
        """
    )
    result = gen_py_code(typedefs=definitions)
    assert "media: abcs.MessageMedia" in result
    assert "extended_media: Optional[abcs.MessageExtendedMedia])" in result
    assert "write_boxed_to" in result
    assert "._write_to" not in result
    assert "read_serializable" in result


def test_recursive_no_hang() -> None:
    definitions = get_definitions(
        """
        inputUserFromMessage#1da448e2 peer:InputPeer msg_id:int user_id:long = InputUser;
        inputPeerUserFromMessage#a87b0a1c peer:InputPeer msg_id:int user_id:long = InputPeer;
        """
    )
    gen_py_code(typedefs=definitions)


def test_recursive_vec() -> None:
    definitions = get_definitions(
        """
        jsonObjectValue#c0de1bd9 key:string value:JSONValue = JSONObjectValue;

        jsonArray#f7444763 value:Vector<JSONValue> = JSONValue;
        jsonObject#99c1d49d value:Vector<JSONObjectValue> = JSONValue;
        """
    )
    result = gen_py_code(typedefs=definitions)
    assert "value: Sequence[abcs.JsonObjectValue]" in result


def test_object_blob_special_case() -> None:
    definitions = get_definitions(
        """
        rpc_result#f35c6d01 req_msg_id:long result:Object = RpcResult;
        """
    )
    result = gen_py_code(typedefs=definitions)
    assert "reader.read_remaining()" in result


def test_object_blob_with_prefix_special_case() -> None:
    definitions = get_definitions(
        """
        message msg_id:long seqno:int bytes:int body:Object = Message;
        """
    )
    result = gen_py_code(typedefs=definitions)
    assert "reader.read(_bytes)" in result


def test_bool_mapped_from_int() -> None:
    definitions = get_definitions(
        """
        contact#145ade0b user_id:long mutual:Bool = Contact;
        """
    )
    result = gen_py_code(typedefs=definitions)
    assert "_mutual in (0x997275b5, 0xbc799737)" in result
    assert "=_mutual == 0x997275b5" in result
    assert "0x997275b5 if self.mutual else 0xbc799737" in result
