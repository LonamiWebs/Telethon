import functools
import inspect

from .users import UserMethods, _NOT_A_REQUEST
from .. import utils
from ..tl import functions, TLRequest


class _TakeoutClient:
    """
    Proxy object over the client. `c` is the client, `k` it's class,
    `r` is the takeout request, and `t` is the takeout ID.
    """
    def __init__(self, client, request):
        # We're a proxy object with __getattribute__overrode so we
        # need to set attributes through the super class `object`.
        super().__setattr__('c', client)
        super().__setattr__('k', client.__class__)
        super().__setattr__('r', request)
        super().__setattr__('t', None)

    def __enter__(self):
        # We also get self attributes through super()
        if super().__getattribute__('c').loop.is_running():
            raise RuntimeError(
                'You must use "async with" if the event loop '
                'is running (i.e. you are inside an "async def")'
            )

        return super().__getattribute__(
            'c').loop.run_until_complete(self.__aenter__())

    async def __aenter__(self):
        # Enter/Exit behaviour is "overrode", we don't want to call start
        cl = super().__getattribute__('c')
        super().__setattr__('t', (await cl(super().__getattribute__('r'))).id)
        return self

    def __exit__(self, *args):
        return super().__getattribute__(
            'c').loop.run_until_complete(self.__aexit__(*args))

    async def __aexit__(self, *args):
        super().__setattr__('t', None)

    async def __call__(self, request, ordered=False):
        takeout_id = super().__getattribute__('t')
        if takeout_id is None:
            raise ValueError('Cannot call takeout methods outside of "with"')

        single = not utils.is_list_like(request)
        requests = ((request,) if single else request)
        wrapped = []
        for r in requests:
            if not isinstance(r, TLRequest):
                raise _NOT_A_REQUEST
            await r.resolve(self, utils)
            wrapped.append(functions.InvokeWithTakeoutRequest(takeout_id, r))

        return await super().__getattribute__('c')(
            wrapped[0] if single else wrapped, ordered=ordered)

    def __getattribute__(self, name):
        if name[:2] == '__':
            # We want to override special method names
            return super().__getattribute__(name)

        value = getattr(super().__getattribute__('c'), name)
        if inspect.ismethod(value):
            # Emulate bound methods behaviour by partially applying
            # our proxy class as the self parameter instead of the client
            return functools.partial(
                getattr(super().__getattribute__('k'), name), self)
        else:
            return value

    def __setattr__(self, name, value):
        setattr(super().__getattribute__('c'), name, value)


class AccountMethods(UserMethods):
    def takeout(
            self, contacts=None, users=None, chats=None, megagroups=None,
            channels=None, files=None, max_file_size=None):
        """
        Creates a proxy object over the current :ref:`TelegramClient` through
        which making requests will use :tl:`InvokeWithTakeoutRequest` to wrap
        them. In other words, returns the current client modified so that
        requests are done as a takeout:

        >>> from telethon.sync import TelegramClient
        >>>
        >>> with TelegramClient(...) as client:
        >>>     with client.takeout() as takeout:
        >>>         client.get_messages('me')  # normal call
        >>>         takeout.get_messages('me')  # wrapped through takeout

        Some of the calls made through the takeout session will have lower
        flood limits. This is useful if you want to export the data from
        conversations or mass-download media, since the rate limits will
        be lower. Only some requests will be affected, and you will need
        to adjust the `wait_time` of methods like `client.iter_messages
        <telethon.client.messages.MessageMethods.iter_messages>`.

        By default, all parameters are ``False``, and you need to enable
        those you plan to use by setting them to ``True``.

        You should ``except errors.TakeoutInitDelayError as e``, since this
        exception will raise depending on the condition of the session. You
        can then access ``e.seconds`` to know how long you should wait for
        before calling the method again.

        Args:
            contacts (`bool`):
                Set to ``True`` if you plan on downloading contacts.

            users (`bool`):
                Set to ``True`` if you plan on downloading information
                from users and their private conversations with you.

            chats (`bool`):
                Set to ``True`` if you plan on downloading information
                from small group chats, such as messages and media.

            megagroups (`bool`):
                Set to ``True`` if you plan on downloading information
                from megagroups (channels), such as messages and media.

            channels (`bool`):
                Set to ``True`` if you plan on downloading information
                from broadcast channels, such as messages and media.

            files (`bool`):
                Set to ``True`` if you plan on downloading media and
                you don't only wish to export messages.

            max_file_size (`int`):
                The maximum file size, in bytes, that you plan
                to download for each message with media.
        """
        return _TakeoutClient(self, functions.account.InitTakeoutSessionRequest(
            contacts=contacts,
            message_users=users,
            message_chats=chats,
            message_megagroups=megagroups,
            message_channels=channels,
            files=files,
            file_max_size=max_file_size
        ))
