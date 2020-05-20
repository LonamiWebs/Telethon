from telethon import TelegramClient, events, types, functions

import asyncio
import logging
import tracemalloc

loop = asyncio.get_event_loop()

api_id = 0
api_hash = ""
provider_token = ""  # https://core.telegram.org/bots/payments#getting-a-token

tracemalloc.start()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARN)
logger = logging.getLogger(__name__)

bot = TelegramClient("bot_test_payment_telethon", api_id, api_hash)


# That event is handled when customer enters his card/etc, on final pre-checkout
# If we don't `SetBotPrecheckoutResultsRequest`, money won't be charged from buyer, and nothing will happen next.
@bot.on(events.Raw(types.UpdateBotPrecheckoutQuery))
async def payment_pre_checkout_handler(event: types.UpdateBotPrecheckoutQuery):
    if event.payload.decode("UTF-8") == 'product A':
        #  so we have to confirm payment
        await bot(
            functions.messages.SetBotPrecheckoutResultsRequest(
                query_id=event.query_id,
                success=True,
                error=None
            )
        )
    elif event.payload.decode("UTF-8") == 'product B':
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
                error="Something went wrong"
            )
        )

    raise events.StopPropagation


# That event is handled at the end, when customer payed.
@bot.on(events.Raw(types.UpdateNewMessage))
async def payment_received_handler(event):
    if isinstance(event.message.action, types.MessageActionPaymentSentMe):
        payment: types.MessageActionPaymentSentMe = event.message.action
        # do something after payment was recieved
        if payment.payload.decode("UTF-8") == 'product A':
            await bot.send_message(event.message.from_id, "Thank you for buying product A!")
        elif payment.payload.decode("UTF-8") == "product B":
            await bot.send_message(event.message.from_id, "Thank you for buying product B!")
        raise events.StopPropagation


# let's put it in one function for more easier way
def generate_invoice(price_label: str, price_amount: int, currency: str, title: str,
                     description: str, payload: str, start_param: str) -> types.InputMediaInvoice:
    price = types.LabeledPrice(label=price_label, amount=price_amount)  # label - just a text, amount=10000 means 100.00
    invoice = types.Invoice(
        currency=currency,  # currency like USD
        prices=[price],  # there could be a couple of prices.
        test=True,  # if you're working with test token

        #  next params are saying for themselves
        name_requested=False,
        phone_requested=False,
        email_requested=False,
        shipping_address_requested=False,
        flexible=False,
        phone_to_provider=False,
        email_to_provider=False

    )
    return types.InputMediaInvoice(
        title=title,
        description=description,
        invoice=invoice,
        payload=payload.encode("UTF-8"),  # payload, which will be sent to next 2 handlers
        provider=provider_token,
        provider_data=types.DataJSON("{}"),  # honestly, no idea.
        start_param=start_param,
        # start_param will be passed with UpdateBotPrecheckoutQuery,
        # I don't really know why is it needed, I guess like payload.

    )


@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event: events.NewMessage.Event):
    await event.respond("/product_a - product A\n/product_b - product B\n/product_c - product, shall cause an error")


@bot.on(events.NewMessage(pattern="/product_a"))
async def start_handler(event: events.NewMessage.Event):
    await event.respond(
        "here you go!",
        file=generate_invoice(
            "Pay", 10000, "RUB", "Title A", "description A", "product A", "abc"
        )
    )


@bot.on(events.NewMessage(pattern="/product_b"))
async def start_handler(event: events.NewMessage.Event):
    await event.respond(
        "here you go!",
        file=generate_invoice(
            "Pay", 20000, "RUB", "Title B", "description B", "product B", "abc"
        )
    )


@bot.on(events.NewMessage(pattern="/product_c"))
async def start_handler(event: events.NewMessage.Event):
    await event.respond(
        "here you go!",
        file=generate_invoice(
            "Pay", 50000, "RUB", "Title C", "description c - shall cause an error", "product C", "abc"
        )
    )


async def main():
    await bot.start()
    print(f"Started.")
    await asyncio.gather(bot.run_until_disconnected())


loop.run_until_complete(main())
