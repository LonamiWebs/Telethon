import re
import zlib


def remove_tl_comments(contents: str) -> str:
    return re.sub(r"//[^\n]*(?=\n)", "", contents)


def infer_id(definition: str) -> int:
    representation = (
        definition.replace(":bytes ", ": string")
        .replace("?bytes ", "? string")
        .replace("<", " ")
        .replace(">", "")
        .replace("{", "")
        .replace("}", "")
    )

    representation = re.sub(r" \w+:flags\.\d+\?true", "", representation)
    return zlib.crc32(representation.encode("ascii"))
