import tl_generator
from tl.telegram_client import TelegramClient
from utils.helpers import load_settings


if __name__ == '__main__':
    if not tl_generator.tlobjects_exist():
        print('Please run `python3 tl_generator.py` first!')

    else:
        print('Loading interactive example...')

        # First, initialize our TelegramClient and connect
        settings = load_settings()
        client = TelegramClient(session_user_id=settings.get('session_name', 'anonymous'),
                                layer=55,
                                api_id=settings['api_id'],
                                api_hash=settings['api_hash'])

        client.connect()
        input('You should now be connected. Press enter when you are ready to continue.')

        # Then, ensure we're authorized and have access
        if not client.is_user_authorized():
            client.send_code_request(str(settings['user_phone']))

            code = input('Enter the code you just received: ')
            client.make_auth(settings['user_phone'], code)

        # After that, load the top dialogs and show a list
        # We use zip(*list_of_tuples) to pair all the elements together,
        # hence being able to return a new list of each triple pair!
        # See http://stackoverflow.com/a/12974504/4759433 for a better explanation
        dialogs, displays, inputs = zip(*client.get_dialogs(8))

        for i, display in enumerate(displays):
            i += 1  # 1-based index for normies
            print('{}. {}'.format(i, display))

        # Let the user decide who they want to talk to
        i = int(input('Who do you want to send messages to?: ')) - 1
        dialog = dialogs[i]
        display = displays[i]
        input_peer = inputs[i]

        # And start a while loop!
        print('You are now sending messages to "{}". Type "!q" when you want to exit.'.format(display))
        while True:
            msg = input('Enter a message: ')
            if msg == '!q':
                break
            client.send_message(input_peer, msg, markdown=True, no_web_page=True)

        print('Thanks for trying the interactive example! Exiting.')
