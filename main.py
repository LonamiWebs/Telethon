import tl_generator
from tl.telegram_client import TelegramClient
from utils.helpers import load_settings


if __name__ == '__main__':
    if not tl_generator.tlobjects_exist():
        print('Please run `python3 tl_generator.py` first!')

    else:
        settings = load_settings()
        client = TelegramClient(session_user_id=settings.get('session_name', 'anonymous'),
                                layer=54,
                                api_id=settings['api_id'],
                                api_hash=settings['api_hash'])

        client.connect()
        if not client.is_user_authorized():
            phone_code_hash = client.send_code_request(settings['user_phone'])
            code = input('Enter the code you just received: ')
            client.make_auth(settings['user_phone'], phone_code_hash, code)
