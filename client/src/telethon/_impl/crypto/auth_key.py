from dataclasses import dataclass
from hashlib import sha1

from typing_extensions import Self


@dataclass
class AuthKey:
    """Represents a Telegram's authorization key.

    To generate a new, valid authorization key, one should use the methods
    provided by the generation module.

    Authorization key: https://core.telegram.org/mtproto/auth_key
    """

    data: bytes
    aux_hash: bytes
    key_id: bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        if len(data) != 256:
            raise ValueError("Auth key data must be exactly 256 bytes")

        sha = sha1(data).digest()
        aux_hash = sha[:8]
        key_id = sha[12:20]
        return cls(data=data, aux_hash=aux_hash, key_id=key_id)

    def __bytes__(self) -> bytes:
        return self.data

    def calc_new_nonce_hash(self, new_nonce: int, number: int) -> int:
        return int.from_bytes(
            sha1(new_nonce.to_bytes(32) + number.to_bytes(1) + self.aux_hash).digest()[
                4:
            ]
        )
