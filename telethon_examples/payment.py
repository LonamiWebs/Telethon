from telethon import TelegramClient, events, types, functions

import asyncio
import logging
import tracemalloc
import os
import time
import sys

loop = asyncio.get_event_loop()

"""
Provider token can be obtained via @BotFather. more info at https://core.telegram.org/bots/payments#getting-a-token

If you are using test token, set test=True in generate_invoice function,
If you are using real token, set test=False
"""
provider_token = ''

tracemalloc.start()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARNING)
logger = logging.getLogger(__name__)


def get_env(name, message, cast=str):
    if name in os.environ:
        return os.environ[name]
    while True:
        value = input(message)
        try:
            return cast(value)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


bot = TelegramClient(
    os.environ.get('TG_SESSION', 'payment'),
    get_env('TG_API_ID', 'Enter your API ID: ', int),
    get_env('TG_API_HASH', 'Enter your API hash: '),
    proxy=None
)


# That event is handled when customer enters his card/etc, on final pre-checkout
# If we don't `SetBotPrecheckoutResultsRequest`, money won't be charged from buyer, and nothing will happen next.
@bot.on(events.Raw(types.UpdateBotPrecheckoutQuery))
async def payment_pre_checkout_handler(event: types.UpdateBotPrecheckoutQuery):
    if event.payload.decode('UTF-8') == 'product A':
        # so we have to confirm payment
        await bot(
            functions.messages.SetBotPrecheckoutResultsRequest(
                query_id=event.query_id,
                success=True,
                error=None
            )
        )
    elif event.payload.decode('UTF-8') == 'product B':
        # same for another
        await bot(
            functions.messages.SetBotPrecheckoutResultsRequest(
                query_id=event.query_id,
                success=True,
                error=None
            )
        )
    else:
        # for example, something went wrong (whatever reason). We can tell customer about that:
        await bot(
            functions.messages.SetBotPrecheckoutResultsRequest(
                query_id=event.query_id,
                success=False,
                error='Something went wrong'
            )
        )

    raise events.StopPropagation


# That event is handled at the end, when customer payed.
@bot.on(events.Raw(types.UpdateNewMessage))
async def payment_received_handler(event):
    if isinstance(event.message.action, types.MessageActionPaymentSentMe):
        payment: types.MessageActionPaymentSentMe = event.message.action
        # do something after payment was received
        if payment.payload.decode('UTF-8') == 'product A':
            await bot.send_message(event.message.from_id, 'Thank you for buying product A!')
        elif payment.payload.decode('UTF-8') == 'product B':
            await bot.send_message(event.message.from_id, 'Thank you for buying product B!')
        raise events.StopPropagation


# let's put it in one function for more easier way
def generate_invoice(price_label: str, price_amount: int, currency: str, title: str,
                     description: str, payload: str, start_param: str) -> types.InputMediaInvoice:
    price = types.LabeledPrice(label=price_label, amount=price_amount)  # label - just a text, amount=10000 means 100.00
    invoice = types.Invoice(
        currency=currency,  # currency like USD
        prices=[price],  # there could be a couple of prices.
        test=True,  # if you're working with test token, else set test=False.
        # More info at https://core.telegram.org/bots/payments

        # params for requesting specific fields
        name_requested=False,
        phone_requested=False,
        email_requested=False,
        shipping_address_requested=False,

        # if price changes depending on shipping
        flexible=False,

        # send data to provider
        phone_to_provider=False,
        email_to_provider=False
    )
    return types.InputMediaInvoice(
        title=title,
        description=description,
        invoice=invoice,
        payload=payload.encode('UTF-8'),  # payload, which will be sent to next 2 handlers
        provider=provider_token,

        provider_data=types.DataJSON('{}'),
        # data about the invoice, which will be shared with the payment provider. A detailed description of
        # required fields should be provided by the payment provider.

        start_param=start_param,
        # Unique deep-linking parameter. May also be used in UpdateBotPrecheckoutQuery
        # see: https://core.telegram.org/bots#deep-linking
        # it may be the empty string if not needed

    )


@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event: events.NewMessage.Event):
    await event.respond('/product_a - product A\n/product_b - product B\n/product_c - product, shall cause an error')


@bot.on(events.NewMessage(pattern='/product_a'))
async def start_handler(event: events.NewMessage.Event):
    await bot.send_message(
        event.chat_id, 'Sending invoice A',
        file=generate_invoice(
            price_label='Pay', price_amount=10000, currency='RUB', title='Title A', description='description A',
            payload='product A', start_param='abc'
        )
    )


@bot.on(events.NewMessage(pattern='/product_b'))
async def start_handler(event: events.NewMessage.Event):
    await bot.send_message(
        event.chat_id, 'Sending invoice B',
        file=generate_invoice(
            price_label='Pay', price_amount=20000, currency='RUB', title='Title B', description='description B',
            payload='product B', start_param='abc'
        )
    )


@bot.on(events.NewMessage(pattern='/product_c'))
async def start_handler(event: events.NewMessage.Event):
    await bot.send_message(
        event.chat_id, 'Sending invoice C',
        file=generate_invoice(
            price_label='Pay', price_amount=50000, currency='RUB', title='Title C',
            description='description c - shall cause an error', payload='product C', start_param='abc'
        )
    )


async def main():
    await bot.start()
    await bot.run_until_disconnected()


if __name__ == '__main__':
    if not provider_token:
        logger.error("No provider token supplied.")
        exit(1)
    loop.run_until_complete(main())
