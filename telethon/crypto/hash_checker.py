from hashlib import sha256
from ..errors import CdnFileTamperedError


class HashChecker:
    def __init__(self, cdn_file_hashes):
        self.cdn_file_hashes = cdn_file_hashes
        self.shaes = [sha256() for _ in range(len(cdn_file_hashes))]

    def check(self, offset, data):
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
