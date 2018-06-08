import unittest
import os
from io import BytesIO
from random import randint
from hashlib import sha256
from telethon import TelegramClient

# Fill in your api_id and api_hash when running the tests
# and REMOVE THEM once you've finished testing them.
api_id = None
api_hash = None


class HigherLevelTests(unittest.TestCase):
    def setUp(self):
        if not api_id or not api_hash:
            raise ValueError('Please fill in both your api_id and api_hash.')

    @unittest.skip("you can't seriously trash random mobile numbers like that :)")
    def test_cdn_download(self):
        client = TelegramClient(None, api_id, api_hash)
        client.session.set_dc(0, '149.154.167.40', 80)
        self.assertTrue(client.connect())

        try:
            phone = '+999662' + str(randint(0, 9999)).zfill(4)
            client.send_code_request(phone)
            client.sign_up('22222', 'Test', 'DC')

            me = client.get_me()
            data = os.urandom(2 ** 17)
            client.send_file(
                me, data,
                progress_callback=lambda c, t:
                    print('test_cdn_download:uploading {:.2%}...'.format(c/t))
            )
            msg = client.get_messages(me)[1][0]

            out = BytesIO()
            client.download_media(msg, out)
            self.assertEqual(sha256(data).digest(), sha256(out.getvalue()).digest())

            out = BytesIO()
            client.download_media(msg, out)  # Won't redirect
            self.assertEqual(sha256(data).digest(), sha256(out.getvalue()).digest())

            client.log_out()
        finally:
            client.disconnect()
