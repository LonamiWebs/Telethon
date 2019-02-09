import functools
import inspect

from .users import UserMethods, _NOT_A_REQUEST
from .. import utils
from ..tl import functions, TLRequest


class _TakeoutClient:
    """
    Proxy object over the client.
    """
    __PROXY_INTERFACE = ('__enter__', '__exit__', '__aenter__', '__aexit__')

    def __init__(self, finalize, client, request):
        # We use the name mangling for attributes to make them inaccessible
        # from within the shadowed client object and to distinguish them from
        # its own attributes where needed.
        self.__finalize = finalize
        self.__client = client
        self.__request = request
        self.__success = None

    @property
    def success(self):
        return self.__success

    @success.setter
    def success(self, value):
        self.__success = value

    def __enter__(self):
        if self.__client.loop.is_running():
            raise RuntimeError(
                'You must use "async with" if the event loop '
                'is running (i.e. you are inside an "async def")'
            )

        return self.__client.loop.run_until_complete(self.__aenter__())

    async def __aenter__(self):
        # Enter/Exit behaviour is "overrode", we don't want to call start.
        client = self.__client
        if client.session.takeout_id is None:
            client.session.takeout_id = (await client(self.__request)).id
        elif self.__request is not None:
            raise ValueError("Can't send a takeout request while another "
                "takeout for the current session still not been finished yet.")
        return self

    def __exit__(self, *args):
        return self.__client.loop.run_until_complete(self.__aexit__(*args))

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.__success is None and self.__finalize:
            self.__success = exc_type is None

        if self.__success is not None:
            result = await self(functions.account.FinishTakeoutSessionRequest(
                self.__success))
            if not result:
                raise ValueError("Failed to finish the takeout.")
            self.session.takeout_id = None

    async def __call__(self, request, ordered=False):
        takeout_id = self.__client.session.takeout_id
        if takeout_id is None:
            raise ValueError('Takeout mode has not been initialized '
                '(are you calling outside of "with"?)')

        single = not utils.is_list_like(request)
        requests = ((request,) if single else request)
        wrapped = []
        for r in requests:
            if not isinstance(r, TLRequest):
                raise _NOT_A_REQUEST()
            await r.resolve(self, utils)
            wrapped.append(functions.InvokeWithTakeoutRequest(takeout_id, r))

        return await self.__client(
            wrapped[0] if single else wrapped, ordered=ordered)

    def __getattribute__(self, name):
        # We access class via type() because __class__ will recurse infinitely.
        # Also note that since we've name-mangled our own class attributes,
        # they'll be passed to __getattribute__() as already decorated. For
        # example, 'self.__client' will be passed as '_TakeoutClient__client'.
        # https://docs.python.org/3/tutorial/classes.html#private-variables
        if name.startswith('__') and name not in type(self).__PROXY_INTERFACE:
            raise AttributeError  # force call of __getattr__

        # Try to access attribute in the proxy object and check for the same
        # attribute in the shadowed object (through our __getattr__) if failed.
        return super().__getattribute__(name)

    def __getattr__(self, name):
        value = getattr(self.__client, name)
        if inspect.ismethod(value):
            # Emulate bound methods behavior by partially applying our proxy
            # class as the self parameter instead of the client.
            return functools.partial(
                getattr(self.__client.__class__, name), self)

        return value

    def __setattr__(self, name, value):
        if name.startswith('_{}__'.format(type(self).__name__.lstrip('_'))):
            # This is our own name-mangled attribute, keep calm.
            return super().__setattr__(name, value)
        return setattr(self.__client, name, value)


class AccountMethods(UserMethods):
    def takeout(
            self, finalize=True, *, contacts=None, users=None, chats=None,
            megagroups=None, channels=None, files=None, max_file_size=None):
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

        By default, all parameters are ``None``, and you need to enable those
        you plan to use by setting them to either ``True`` or ``False``.

        You should ``except errors.TakeoutInitDelayError as e``, since this
        exception will raise depending on the condition of the session. You
        can then access ``e.seconds`` to know how long you should wait for
        before calling the method again.

        There's also a `success` property available in the takeout proxy
        object, so from the `with` body you can set the boolean result that
        will be sent back to Telegram. But if it's left ``None`` as by
        default, then the action is based on the `finalize` parameter. If
        it's ``True`` then the takeout will be finished, and if no exception
        occurred during it, then ``True`` will be considered as a result.
        Otherwise, the takeout will not be finished and its ID will be
        preserved for future usage as `client.session.takeout_id
        <telethon.sessions.abstract.Session.takeout_id>`.

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
        request_kwargs = dict(
            contacts=contacts,
            message_users=users,
            message_chats=chats,
            message_megagroups=megagroups,
            message_channels=channels,
            files=files,
            file_max_size=max_file_size
        )
        arg_specified = (arg is not None for arg in request_kwargs.values())

        if self.session.takeout_id is None or any(arg_specified):
            request = functions.account.InitTakeoutSessionRequest(
                **request_kwargs)
        else:
            request = None

        return _TakeoutClient(finalize, self, request)

    async def end_takeout(self, success):
        """
        Finishes a takeout, with specified result sent back to Telegram.

        Returns:
            ``True`` if the operation was successful, ``False`` otherwise.
        """
        try:
            async with _TakeoutClient(True, self, None) as takeout:
                takeout.success = success
        except ValueError:
            return False
        return True
