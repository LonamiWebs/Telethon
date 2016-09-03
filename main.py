import parser.tl_generator

from network.tcp_transport import TcpTransport
from network.authenticator import do_authentication

if __name__ == '__main__':
    if not parser.tl_generator.tlobjects_exist():
        print('First run. Generating TLObjects...')
        parser.tl_generator.generate_tlobjects('scheme.tl')
        print('Done.')

    transport = TcpTransport('149.154.167.91', 443)
    auth_key, time_offset = do_authentication(transport)
    print(auth_key.aux_hash)
    print(auth_key.key)
    print(auth_key.key_id)
    print(time_offset)
