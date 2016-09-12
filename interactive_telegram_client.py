import tl_generator
from tl.types import UpdateShortChatMessage
from tl.types import UpdateShortMessage

if not tl_generator.tlobjects_exist():
    import errors

    raise errors.TLGeneratorNotRan()
else:
    del tl_generator

from telegram_client import TelegramClient
from utils.helpers import load_settings

# For pretty printing, thanks to http://stackoverflow.com/a/37501797/4759433
import sys
import readline
from time import sleep
import shutil

# Get the (current) number of lines in the terminal
cols, rows = shutil.get_terminal_size()


def print_title(title):
    # Clear previous window
    print('\n')
    available_cols = cols - 2  # -2 sincewe omit '┌' and '┐'
    print('┌{}┐'.format('─' * available_cols))
    print('│{}│'.format(title.center(available_cols)))
    print('└{}┘'.format('─' * available_cols))


class InteractiveTelegramClient(TelegramClient):
    def __init__(self, session_user_id, user_phone, layer, api_id, api_hash):
        print_title('Initialization')

        print('Initializing interactive example...')
        super().__init__(session_user_id, layer, api_id, api_hash)

        print('Connecting to Telegram servers...')
        self.connect()

        # Then, ensure we're authorized and have access
        if not self.is_user_authorized():
            print('First run. Sending code request...')
            self.send_code_request(user_phone)

            code = input('Enter the code you just received: ')
            self.make_auth(user_phone, code)

    def run(self):
        # Listen for updates
        self.add_update_handler(self.update_handler)

        # Enter a while loop to chat as long as the user wants
        while True:
            # Retrieve the top dialogs
            dialog_count = 10
            dialogs, displays, inputs = self.get_dialogs(dialog_count)

            i = None
            while i is None:
                try:
                    print_title('Dialogs window')

                    # Display them so the user can choose
                    for i, display in enumerate(displays):
                        i += 1  # 1-based index for normies
                        print('{}. {}'.format(i, display))

                    # Let the user decide who they want to talk to
                    i = input('Who do you want to send messages to ("!q" to exit)?: ')
                    if i == '!q':
                        return

                    i = int(i if i else 0) - 1
                    # Ensure it is inside the bounds, otherwise set to None and retry
                    if not 0 <= i < dialog_count:
                        i = None

                except ValueError:
                    pass

            # Retrieve the selected user
            display = displays[i]
            input_peer = inputs[i]

            # Show some information
            print_title('Chat with "{}"'.format(display))
            print('Available commands:'.format(display))
            print('  !q: Quits the current chat.')
            print('  !h: prints the latest messages (message History) of the chat.')
            print('  !p <path>: sends a Photo located at the given path')

            # And start a while loop to chat
            while True:
                msg = input('Enter a message: ')
                # Quit
                if msg == '!q':
                    break

                # History
                elif msg == '!h':
                    # First retrieve the messages and some information
                    total_count, messages, senders = self.get_message_history(input_peer, limit=10)
                    # Iterate over all (in reverse order so the latest appears the last in the console)
                    # and print them in "[hh:mm] Sender: Message" text format
                    for msg, sender in zip(reversed(messages), reversed(senders)):
                        # Get the name of the sender if any
                        name = sender.first_name if sender else '???'

                        # Format the message content
                        if msg.media:
                            content = '<{}> {}'.format(  # The media may or may not have a caption
                                msg.media.__class__.__name__, getattr(msg.media, 'caption', ''))
                        else:
                            content = msg.message

                        # And print it to the user
                        print('[{}:{}] (ID={}) {}: {}'.format(
                            msg.date.hour, msg.date.minute, msg.id, name, content))

                # Send photo
                elif msg.startswith('!p '):
                    file_path = msg[len('!p '):]  # Slice the message to get the path

                    print('Uploading {}...'.format(file_path))
                    input_file = self.upload_file(file_path)

                    # After we have the handle to the uploaded file, send it to our peer
                    self.send_photo_file(input_file, input_peer)
                    print('Media sent!')

                # Send chat message (if any)
                elif msg:
                    self.send_message(input_peer, msg, markdown=True, no_web_page=True)

    @staticmethod
    def update_handler(update_object):
        if type(update_object) is UpdateShortMessage:
            print('[User #{} sent {}]'.format(update_object.user_id, update_object.message))

        elif type(update_object) is UpdateShortChatMessage:
            print('[Chat #{} sent {}]'.format(update_object.chat_id, update_object.message))


if __name__ == '__main__':
    # Load the settings and initialize the client
    settings = load_settings()
    client = InteractiveTelegramClient(
        session_user_id=settings.get('session_name', 'anonymous'),
        user_phone=str(settings['user_phone']),
        layer=55,
        api_id=settings['api_id'],
        api_hash=settings['api_hash'])

    print('Initialization done!')

    try:
        client.run()

    except Exception as e:
        print('Unexpected error ({}), will not continue: {}'.format(type(e), e))

    finally:
        print_title('Exit')
        print('Thanks for trying the interactive example! Exiting...')
        client.disconnect()
