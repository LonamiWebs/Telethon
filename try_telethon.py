#!/usr/bin/env python3
import traceback

from telethon_examples.interactive_telegram_client \
    import InteractiveTelegramClient


def load_settings(path='api/settings'):
    """Loads the user settings located under `api/`"""
    result = {}
    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            value_pair = line.split('=')
            left = value_pair[0].strip()
            right = value_pair[1].strip()
            if right.isnumeric():
                result[left] = int(right)
            else:
                result[left] = right

    return result


if __name__ == '__main__':
    # Load the settings and initialize the client
    settings = load_settings()
    kwargs = {}
    if settings.get('socks_proxy'):
        import socks  # $ pip install pysocks
        host, port = settings['socks_proxy'].split(':')
        kwargs = dict(proxy=(socks.SOCKS5, host, int(port)))

    client = InteractiveTelegramClient(
        session_user_id=str(settings.get('session_name', 'anonymous')),
        user_phone=str(settings['user_phone']),
        api_id=settings['api_id'],
        api_hash=str(settings['api_hash']),
        **kwargs)

    print('Initialization done!')

    try:
        client.run()

    except Exception as e:
        print('Unexpected error ({}): {} at\n{}'.format(
            type(e), e, traceback.format_exc()))

    finally:
        client.disconnect()
        print('Thanks for trying the interactive example! Exiting...')
