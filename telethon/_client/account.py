import functools
import inspect
import typing

from .users import _NOT_A_REQUEST
from .._misc import helpers, utils
from .. import _tl

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


# TODO Make use of :tl:`InvokeWithMessagesRange` somehow
#      For that, we need to use :tl:`GetSplitRanges` first.
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

    async def __aenter__(self):
        # Enter/Exit behaviour is "overrode", we don't want to call start.
        client = self.__client
        if client.session.takeout_id is None:
            client.session.takeout_id = (await client(self.__request)).id
        elif self.__request is not None:
            raise ValueError("Can't send a takeout request while another "
                "takeout for the current session still not been finished yet.")
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.__success is None and self.__finalize:
            self.__success = exc_type is None

        if self.__success is not None:
            result = await self(_tl.fn.account.FinishTakeoutSession(
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
            if not isinstance(r, _tl.TLRequest):
                raise _NOT_A_REQUEST()
            await r.resolve(self, utils)
            wrapped.append(_tl.fn.InvokeWithTakeout(takeout_id, r))

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


def takeout(
        self: 'TelegramClient',
        finalize: bool = True,
        *,
        contacts: bool = None,
        users: bool = None,
        chats: bool = None,
        megagroups: bool = None,
        channels: bool = None,
        files: bool = None,
        max_file_size: bool = None) -> 'TelegramClient':
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
        request = _tl.fn.account.InitTakeoutSession(
            **request_kwargs)
    else:
        request = None

    return _TakeoutClient(finalize, self, request)

async def end_takeout(self: 'TelegramClient', success: bool) -> bool:
    try:
        async with _TakeoutClient(True, self, None) as takeout:
            takeout.success = success
    except ValueError:
        return False
    return True
