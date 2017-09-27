from hashlib import sha256

from ..tl import Session
from ..tl.functions.upload import GetCdnFileRequest, ReuploadCdnFileRequest
from ..tl.types.upload import CdnFileReuploadNeeded, CdnFile
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

    @staticmethod
    def prepare_decrypter(client, client_cls, cdn_redirect):
        """Prepares a CDN decrypter, returning (decrypter, file data).
           'client' should be the original TelegramBareClient that
           tried to download the file.

           'client_cls' should be the class of the TelegramBareClient.
        """
        # TODO Avoid the need for 'client_cls=TelegramBareClient'
        # https://core.telegram.org/cdn
        cdn_aes = AESModeCTR(
            key=cdn_redirect.encryption_key,
            # 12 first bytes of the IV..4 bytes of the offset (0, big endian)
            iv=cdn_redirect.encryption_iv[:12] + bytes(4)
        )

        # Create a new client on said CDN
        dc = client._get_dc(cdn_redirect.dc_id, cdn=True)
        session = Session(client.session)
        session.server_address = dc.ip_address
        session.port = dc.port
        cdn_client = client_cls(  # Avoid importing TelegramBareClient
            session, client.api_id, client.api_hash,
            timeout=client._sender.connection.get_timeout()
        )
        # This will make use of the new RSA keys for this specific CDN.
        #
        # We assume that cdn_redirect.cdn_file_hashes are ordered by offset,
        # and that there will be enough of these to retrieve the whole file.
        #
        # This relies on the fact that TelegramBareClient._dc_options is
        # static and it won't be called from this DC (it would fail).
        cdn_client.connect()

        # CDN client is ready, create the resulting CdnDecrypter
        decrypter = CdnDecrypter(
            cdn_client, cdn_redirect.file_token,
            cdn_aes, cdn_redirect.cdn_file_hashes
        )

        cdn_file = client(GetCdnFileRequest(
            file_token=cdn_redirect.file_token,
            offset=cdn_redirect.cdn_file_hashes[0].offset,
            limit=cdn_redirect.cdn_file_hashes[0].limit
        ))
        if isinstance(cdn_file, CdnFileReuploadNeeded):
            # We need to use the original client here
            client(ReuploadCdnFileRequest(
                file_token=cdn_redirect.file_token,
                request_token=cdn_file.request_token
            ))

            # We want to always return a valid upload.CdnFile
            cdn_file = decrypter.get_file()
        else:
            cdn_file.bytes = decrypter.cdn_aes.encrypt(cdn_file.bytes)
            cdn_hash = decrypter.cdn_file_hashes.pop(0)
            decrypter.check(cdn_file.bytes, cdn_hash)

        return decrypter, cdn_file

    def get_file(self):
        """Calls GetCdnFileRequest and decrypts its bytes.
           Also ensures that the file hasn't been tampered.
        """
        if self.cdn_file_hashes:
            cdn_hash = self.cdn_file_hashes.pop(0)
            cdn_file = self.client(GetCdnFileRequest(
                self.file_token, cdn_hash.offset, cdn_hash.limit
            ))
            cdn_file.bytes = self.cdn_aes.encrypt(cdn_file.bytes)
            self.check(cdn_file.bytes, cdn_hash)
        else:
            cdn_file = CdnFile(bytes(0))

        return cdn_file

    @staticmethod
    def check(data, cdn_hash):
        """Checks the integrity of the given data"""
        if sha256(data).digest() != cdn_hash.hash:
            raise CdnFileTamperedError()
