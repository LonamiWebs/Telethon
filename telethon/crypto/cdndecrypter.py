"""
This module holds the CdnDecrypter utility class.
"""
from hashlib import sha256

from ..tl.functions.upload import GetCdnFileRequest, ReuploadCdnFileRequest
from ..tl.types.upload import CdnFileReuploadNeeded, CdnFile
from ..crypto import AESModeCTR
from ..errors import CdnFileTamperedError


class CdnDecrypter:
    """
    Used when downloading a file results in a 'FileCdnRedirect' to
    both prepare the redirect, decrypt the file as it downloads, and
    ensure the file hasn't been tampered. https://core.telegram.org/cdn
    """
    def __init__(self, cdn_client, file_token, cdn_aes, cdn_file_hashes):
        """
        Initializes the CDN decrypter.

        :param cdn_client: a client connected to a CDN.
        :param file_token: the token of the file to be used.
        :param cdn_aes: the AES CTR used to decrypt the file.
        :param cdn_file_hashes: the hashes the decrypted file must match.
        """
        self.client = cdn_client
        self.file_token = file_token
        self.cdn_aes = cdn_aes
        self.cdn_file_hashes = cdn_file_hashes

    @staticmethod
    def prepare_decrypter(client, cdn_client, cdn_redirect):
        """
        Prepares a new CDN decrypter.

        :param client: a TelegramClient connected to the main servers.
        :param cdn_client: a new client connected to the CDN.
        :param cdn_redirect: the redirect file object that caused this call.
        :return: (CdnDecrypter, first chunk file data)
        """
        cdn_aes = AESModeCTR(
            key=cdn_redirect.encryption_key,
            # 12 first bytes of the IV..4 bytes of the offset (0, big endian)
            iv=cdn_redirect.encryption_iv[:12] + bytes(4)
        )

        # We assume that cdn_redirect.cdn_file_hashes are ordered by offset,
        # and that there will be enough of these to retrieve the whole file.
        decrypter = CdnDecrypter(
            cdn_client, cdn_redirect.file_token,
            cdn_aes, cdn_redirect.cdn_file_hashes
        )

        cdn_file = cdn_client(GetCdnFileRequest(
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
        """
        Calls GetCdnFileRequest and decrypts its bytes.
        Also ensures that the file hasn't been tampered.

        :return: the CdnFile result.
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
        """
        Checks the integrity of the given data.
        Raises CdnFileTamperedError if the integrity check fails.

        :param data: the data to be hashed.
        :param cdn_hash: the expected hash.
        """
        if sha256(data).digest() != cdn_hash.hash:
            raise CdnFileTamperedError()
