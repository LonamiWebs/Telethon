#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""steps involved in the scarpping process

The below steps were copied from https://GitHub.com/SpEcHiDe/MyTelegramOrgRoBot

1) open my.telegram.org
2) enter your phone number
3) we will receive a "random_hash" and "Web Login Code"
4) login to my.telegram.org using the given informations,
5) on successful login, it will return a "stel-cookie"
6) this cookie needs to be used for all consecutive requests
7) the provided user might / might not have a Telegram app_id created
8) we identify this by scarpping my.telegram.org/apps and checking the "title" tag of the page
9) appropriately, call "scarp_tg_existing_app" or "s_create_new_tg_app" depending on the previous condition
10) finally we get app_id and api_hash from the webpage"""

import aiohttp
import typing
from bs4 import BeautifulSoup


async def request_tg_code_get_random_hash(session, input_phone_number):
    """ requests Login Code
    and returns a random_hash
    which is used in STEP TWO """
    request_url = "https://my.telegram.org/auth/send_password"
    request_data = {
        "phone": input_phone_number
    }
    response_c = await session.post(request_url, data=request_data)
    json_response = await response_c.json()
    return json_response["random_hash"]


async def login_step_get_stel_cookie(
    session,
    input_phone_number,
    tg_random_hash,
    tg_cloud_password
):
    """Logins to my.telegram.org and returns the cookie,
    or False in case of failure"""
    request_url = "https://my.telegram.org/auth/login"
    request_data = {
        "phone": input_phone_number,
        "random_hash": tg_random_hash,
        "password": tg_cloud_password
    }
    response_c = await session.post(request_url, data=request_data)
    response_c_text = await response_c.text()
    #
    re_val = None
    re_status_id = None
    if response_c_text == "true":
        re_val = response_c.headers.get("Set-Cookie")
        re_status_id = True
    else:
        re_val = response_c_text
        re_status_id = False
    return re_status_id, re_val


async def scarp_tg_existing_app(session, stel_token):
    """scraps the web page using the provided cookie,
    returns True or False appropriately"""
    request_url = "https://my.telegram.org/apps"
    custom_header = {
        "Cookie": stel_token
    }
    response_c = await session.get(request_url, headers=custom_header)
    response_text = await response_c.text()
    # print(response_text)
    soup = BeautifulSoup(response_text, features="html.parser")
    title_of_page = soup.title.string
    #
    re_dict_vals = {}
    re_status_id = None
    if "configuration" in title_of_page:
        # print(soup.prettify())
        g_inputs = soup.find_all("span", {"class": "input-xlarge"})
        # App configuration
        app_id = g_inputs[0].string
        api_hash = g_inputs[1].string
        # Available MTProto servers
        test_configuration = g_inputs[4].string
        production_configuration = g_inputs[5].string
        # It is forbidden to pass this value to third parties.
        re_dict_vals = {
            "App Configuration": {
                "app_id": app_id,
                "api_hash": api_hash
            },
            "Available MTProto Servers": {
                "test_configuration": test_configuration,
                "production_configuration": production_configuration
            },
            "Disclaimer": "It is forbidden to pass this value to third parties."
        }
        re_status_id = True
    else:
        tg_app_hash = soup.find("input", {"name": "hash"}).get("value")
        re_dict_vals = {
            "tg_app_hash": tg_app_hash
        }
        re_status_id = False
    return re_status_id, re_dict_vals


async def s_create_new_tg_app(
    session,
    stel_token,
    tg_app_hash,
    app_title,
    app_shortname,
    app_url,
    app_platform,
    app_desc
):
    #pylint: disable-msg=too-many-arguments
    """ creates a new my.telegram.org/apps
    using the provided parameters """
    request_url = "https://my.telegram.org/apps/create"
    custom_header = {
        "Cookie": stel_token
    }
    request_data = {
        "hash": tg_app_hash,
        "app_title": app_title,
        "app_shortname": app_shortname,
        "app_url": app_url,
        "app_platform": app_platform,
        "app_desc": app_desc
    }
    response_c = await session.post(
        request_url,
        data=request_data,
        headers=custom_header
    )
    return response_c


async def auto_scarp_my_tg_api_hash(
    phone: typing.Callable[[], str] = lambda: input("Enter your Phone Number: [this should be a number already registered on Telegram] "),
    web_login_code: typing.Callable[[], str] = lambda: input("Please send the code that you received from Telegram: "),
    my_tg_app_title: typing.Callable[[], str] = lambda: input("Enter the title of your application: "),
    my_tg_app_shortname: typing.Callable[[], str] = lambda: input("Enter a short_name for your application: "),
    my_tg_app_url: typing.Callable[[], str] = lambda: input("Enter the URL of your application: "),
    my_tg_app_platform: typing.Callable[[], str] = lambda: input("Enter the Platform for your application: "),
    my_tg_app_description: typing.Callable[[], str] = lambda: input("Enter a description of your application: ")
) -> (int, str):
    async with aiohttp.ClientSession() as session:
        phone = phone()
        random_hash = await request_tg_code_get_random_hash(session, phone)
        vo, no = await login_step_get_stel_cookie(
            session,
            phone,
            random_hash,
            web_login_code()
        )

        if not vo:
            raise ValueError(no)

        vmo, vno = await scarp_tg_existing_app(session, no)
        if not vmo:
            await s_create_new_tg_app(
                session,
                no,
                vno,
                my_tg_app_title(),
                my_tg_app_shortname(),
                my_tg_app_url(),
                my_tg_app_platform(),
                my_tg_app_description()
            )
        vmo, vno = await scarp_tg_existing_app(session, no)
        if not vmo:
            """this should usually not happen but will happen when the scarpper breaks, but never happened, yet """
            raise ValueError("-_-")

    return int(vno["App Configuration"]["app_id"]), vno["App Configuration"]["api_hash"]
