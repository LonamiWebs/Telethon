from .basecodec import BaseCodec


SSL_PORT = 443


class HttpCodec(BaseCodec):
    @staticmethod
    def header_length():
        return 4

    @staticmethod
    def tag():
        return None

    def encode_packet(self, data, ip, port):
        return ('POST /api HTTP/1.1\r\n'
                'Host: {}:{}\r\n'
                'Content-Type: application/x-www-form-urlencoded\r\n'
                'Connection: keep-alive\r\n'
                'Keep-Alive: timeout=100000, max=10000000\r\n'
                'Content-Length: {}\r\n\r\n'
                .format(ip, port, len(data))
                .encode('ascii') + data)

    def decode_header(self, header):
        if not header.endswith(b'\r\n\r\n'):
            return -1

        header = header.lower()
        start = header.index(b'content-length: ') + 16
        print(header)
        return int(header[start:header.index(b'\r', start)])
