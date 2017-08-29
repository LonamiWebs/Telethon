from hashlib import sha256

from ..tl import Session
from ..tl.functions.upload import GetCdnFileRequest, ReuploadCdnFileRequest
from ..tl.types.upload import CdnFileReuploadNeeded
from ..crypto import AESModeCTR
from ..errors import CdnFileTamperedError


class CdnDecrypter:
    """Used when downloading a file results in a 'FileCdnRedirect' to
       both prepare the redirect, decrypt the file as it downloads, and
       ensure the file hasn't been tampered.
    """
    def __init__(self, cdn_client, file_token, cdn_aes, cdn_file_hashes):
        self.client = cdn_client
        self.file_token = file_token
        self.cdn_aes = cdn_aes
        self.cdn_file_hashes = cdn_file_hashes
        self.shaes = [sha256() for _ in range(len(cdn_file_hashes))]

    @staticmethod
    def prepare_decrypter(client, client_cls, cdn_redirect, offset, part_size):
        """Prepares a CDN decrypter, returning (decrypter, file data).
           'client' should be the original TelegramBareClient that
           tried to download the file.

           'client_cls' should be the class of the TelegramBareClient.
        """
        # TODO Avoid the need for 'client_cls=TelegramBareClient'
        # https://core.telegram.org/cdn
        cdn_aes = AESModeCTR(
            key=cdn_redirect.encryption_key,
            iv=cdn_redirect.encryption_iv[:12] + (offset >> 4).to_bytes(4, 'big')
        )

        # Create a new client on said CDN
        dc = client._get_dc(cdn_redirect.dc_id, cdn=True)
        session = Session(client.session)
        session.server_address = dc.ip_address
        session.port = dc.port
        cdn_client = client_cls(  # Avoid importing TelegramBareClient
            session, client.api_id, client.api_hash,
            timeout=client._timeout
        )
        # This will make use of the new RSA keys for this specific CDN
        cdn_file = cdn_client.connect(initial_query=GetCdnFileRequest(
            cdn_redirect.file_token, offset, part_size
        ))

        # CDN client is ready, create the resulting CdnDecrypter
        decrypter = CdnDecrypter(
            cdn_client, cdn_redirect.file_token,
            cdn_aes, cdn_redirect.cdn_file_hashes
        )

        if isinstance(cdn_file, CdnFileReuploadNeeded):
            # We need to use the original client here
            client(ReuploadCdnFileRequest(
                file_token=cdn_redirect.file_token,
                request_token=cdn_file.request_token
            ))

            # We want to always return a valid upload.CdnFile
            cdn_file = decrypter.get_file(offset, part_size)
        else:
            cdn_file.bytes = decrypter.cdn_aes.encrypt(cdn_file.bytes)
            decrypter.check(offset, cdn_file.bytes)

        return decrypter, cdn_file

    def get_file(self, offset, limit):
        """Calls GetCdnFileRequest and decrypts its bytes.
           Also ensures that the file hasn't been tampered.
        """
        result = self.client(GetCdnFileRequest(self.file_token, offset, limit))
        result.bytes = self.cdn_aes.encrypt(result.bytes)
        self.check(offset, result.bytes)
        return result

    def check(self, offset, data):
        """Checks the integrity of the given data"""
        for cdn_hash, sha in zip(self.cdn_file_hashes, self.shaes):
            inter = self.intersect(
                cdn_hash.offset, cdn_hash.offset + cdn_hash.limit,
                offset, offset + len(data)
            )
            if inter:
                x1, x2 = inter[0] - offset, inter[1] - offset
                sha.update(data[x1:x2])
            elif offset > cdn_hash.offset:
                if cdn_hash.hash == sha.digest():
                    self.cdn_file_hashes.remove(cdn_hash)
                    self.shaes.remove(sha)
                else:
                    raise CdnFileTamperedError()

    def finish_check(self):
        """Similar to the check method, but for all unchecked hashes"""
        for cdn_hash, sha in zip(self.cdn_file_hashes, self.shaes):
            if cdn_hash.hash != sha.digest():
                raise CdnFileTamperedError()

        self.cdn_file_hashes.clear()
        self.shaes.clear()

    @staticmethod
    def intersect(x1, x2, z1, z2):
        if x1 > z1:
            return None if x1 > z2 else (x1, min(x2, z2))
        else:
            return (z1, min(x2, z2)) if x2 > z1 else None
