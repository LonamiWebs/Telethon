import tl_generator
if not tl_generator.tlobjects_exist():
    import errors
    raise errors.TLGeneratorNotRan()
else:
    del tl_generator

from tl.telegram_client import TelegramClient
from utils.helpers import load_settings

from datetime import datetime


if __name__ == '__main__':
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

    # Enter a while loop to chat as long as the user wants
    while True:
        # Retrieve the top dialogs
        dialogs, displays, inputs = client.get_dialogs(8)

        # Display them so the user can choose
        for i, display in enumerate(displays):
            i += 1  # 1-based index for normies
            print('{}. {}'.format(i, display))

        # Let the user decide who they want to talk to
        i = int(input('Who do you want to send messages to (0 to exit)?: ')) - 1
        if i == -1:
            break

        # Retrieve the selected user
        dialog = dialogs[i]
        display = displays[i]
        input_peer = inputs[i]

        # Show some information
        print('You are now sending messages to "{}". Available commands:'.format(display))
        print('  !q: Quits the current chat.')
        print('  !h: prints the latest messages (message History) of the chat.')

        # And start a while loop to chat
        while True:
            msg = input('Enter a message: ')
            # Quit
            if msg == '!q':
                break

            # History
            elif msg == '!h':
                # First retrieve the messages and some information
                total_count, messages, senders = client.get_message_history(input_peer, limit=10)
                # Iterate over all (in reverse order so the latest appears the last in the console)
                # and print them in "[hh:mm] Sender: Message" text format
                for msg, sender in zip(reversed(messages), reversed(senders)):
                    name = sender.first_name if sender else '???'
                    date = datetime.fromtimestamp(msg.date)
                    print('[{}:{}] {}: {}'.format(date.hour, date.minute, name, msg.message))

            # Send chat message
            else:
                client.send_message(input_peer, msg, markdown=True, no_web_page=True)

    print('Thanks for trying the interactive example! Exiting.')
