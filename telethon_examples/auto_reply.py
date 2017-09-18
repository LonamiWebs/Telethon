#!/usr/bin/env python3
# disclaimer: you should not actually use this. it can be quite spammy.
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from getpass import getpass
from telethon.tl.types import InputPeerUser,InputPeerChannel
from telethon.tl.types import Updates
from telethon.tl.types import UpdateNewChannelMessage,UpdateNewMessage
from telethon.tl.functions.messages import SendMessageRequest,EditMessageRequest
from telethon.tl.types import MessageService
from nltk.tokenize import word_tokenize
from os import environ
from time import sleep

CHANNELS = {}
CHANNELNAMES = {}
USERS = {}
EMACS_BLACKLIST = [1058260578, # si @linux_group
        123456789]
REACTS = {'emacs':'Needs more vim.',
        'chrome':'Needs more firefox.',
}

class NeedsMore(TelegramClient):
    def __init__(self):
        settings = {'api_id':int(environ['TG_API_ID']),
                'api_hash':environ['TG_API_HASH'],
                'user_phone':environ['TG_PHONE'],
                'session_name':'needsmore'}
        super().__init__(
            settings.get('session_name','session1'),
            settings['api_id'],
            settings['api_hash'],
            proxy=None,
            process_updates=True)

        user_phone = settings['user_phone']

        print('INFO: Connecting to Telegram Servers...', end='', flush=True)
        self.connect()
        print('Done!')

        if not self.is_user_authorized():
            print('INFO: Unauthorized user')
            self.send_code_request(user_phone)
            code_ok = False
            while not code_ok:
                code = input('Enter the auth code: ')
                try:
                    code_ok = self.sign_in(user_phone, code)
                except SessionPasswordNeededError:
                    pw = getpass('Two step verification enabled. Please enter your password: ')
                    self.sign_in(password=pw)
            print('INFO: Client initialized succesfully!')

    def run(self):
        # Listen for updates
        while True:
            update = self.updates.poll() # This will block until an update is available
            triggers = []
            if isinstance(update, Updates):
                for x in update.updates:
                    if not isinstance(x,UpdateNewChannelMessage): continue
                    if isinstance(x.message,MessageService): continue
                    # We're only interested in messages to supergroups
                    words = word_tokenize(x.message.message.lower())
                    # Avoid matching 'emacs' in 'spacemacs' and similar
                    if 'emacs' in words and x.message.to_id.channel_id not in EMACS_BLACKLIST:
                        triggers.append(('emacs',x.message))
                    if 'chrome' in words:
                        triggers.append(('chrome',x.message))
                    if 'x files theme' == x.message.message.lower() and x.message.out:
                        # Automatically reply to yourself saying 'x files theme' with the audio
                        msg = x.message
                        chan = InputPeerChannel(msg.to_id.channel_id,CHANNELS[msg.to_id.channel_id])
                        self.send_voice_note(chan,'xfiles.m4a',reply_to=msg.id)
                        sleep(1)
                    if '.shrug' in x.message.message.lower() and x.message.out:
                        # Automatically replace '.shrug' in any message you
                        # send to a supergroup with the shrug emoticon
                        msg = x.message
                        chan = InputPeerChannel(msg.to_id.channel_id,CHANNELS[msg.to_id.channel_id])
                        self(EditMessageRequest(chan,msg.id,
                            message=msg.message.replace('.shrug','¯\_(ツ)_/¯')))
                        sleep(1)

f               for trigger in triggers:
                    msg = trigger[1]
                    chan = InputPeerChannel(msg.to_id.channel_id,CHANNELS[msg.to_id.channel_id])
                    log_chat = InputPeerUser(user_id=123456789,access_hash=987654321234567890)
                    self.send_message(log_chat,"{} said {} in {}. Sending react {}".format(
                        msg.from_id,msg.message,CHANNELNAMES[msg.to_id.channel_id],REACTS[trigger[0]][:20]))
                    react = '>{}\n{}'.format(trigger[0],REACTS[trigger[0]])
                    self.invoke(SendMessageRequest(chan,react,reply_to_msg_id=msg.id))
                    sleep(1)

if __name__ == "__main__":
    #TODO: this block could be moved to __init__
    # You can create these text files using https://github.com/LonamiWebs/Telethon/wiki/Retrieving-all-dialogs
    with open('channels.txt','r') as f:
        # Format: channel_id access_hash #Channel Name
        lines = f.readlines()
        chans = [l.split(' #',1)[0].split(' ') for l in lines]
        CHANNELS = {int(c[0]):int(c[1]) for c in chans} # id:hash
        CHANNELNAMES = {int(l.split()[0]):l.split('#',1)[1].strip() for l in lines} #id:name
    with open('users','r') as f:
        # Format: [user_id, access_hash, 'username', 'Firstname Lastname']
        lines = f.readlines()
        uss = [l.strip()[1:-1].split(',') for l in lines]
        USERS = {int(user[0]):int(user[1]) for user in uss} # id:hash

    needsmore = NeedsMore()
    needsmore.run()
