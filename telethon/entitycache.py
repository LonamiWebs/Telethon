import inspect
import itertools

from . import utils
from .tl import types

# Which updates have the following fields?
_has_field = {
    ('user_id', int): [],
    ('chat_id', int): [],
    ('channel_id', int): [],
    ('peer', 'TypePeer'): [],
    ('peer', 'TypeDialogPeer'): [],
    ('message', 'TypeMessage'): [],
}

# Note: We don't bother checking for some rare:
# * `UpdateChatParticipantAdd.inviter_id` integer.
# * `UpdateNotifySettings.peer` dialog peer.
# * `UpdatePinnedDialogs.order` list of dialog peers.
# * `UpdateReadMessagesContents.messages` list of messages.
# * `UpdateChatParticipants.participants` list of participants.
#
# There are also some uninteresting `update.message` of type string.


def _fill():
    for name in dir(types):
        update = getattr(types, name)
        if getattr(update, 'SUBCLASS_OF_ID', None) == 0x9f89304e:
            cid = update.CONSTRUCTOR_ID
            sig = inspect.signature(update.__init__)
            for param in sig.parameters.values():
                vec = _has_field.get((param.name, param.annotation))
                if vec is not None:
                    vec.append(cid)

    # Future-proof check: if the documentation format ever changes
    # then we won't be able to pick the update types we are interested
    # in, so we must make sure we have at least an update for each field
    # which likely means we are doing it right.
    if not all(_has_field.values()):
        raise RuntimeError('FIXME: Did the init signature or updates change?')


# We use a function to avoid cluttering the globals (with name/update/cid/doc)
_fill()


class EntityCache:
    """
    In-memory input entity cache, defaultdict-like behaviour.
    """
    def add(self, entities):
        """
        Adds the given entities to the cache, if they weren't saved before.
        """
        if not utils.is_list_like(entities):
            # Invariant: all "chats" and "users" are always iterables,
            # and "user" never is (so we wrap it inside a list).
            entities = itertools.chain(
                getattr(entities, 'chats', []),
                getattr(entities, 'users', []),
                (hasattr(entities, 'user') and [entities.user]) or []
            )

        for entity in entities:
            try:
                pid = utils.get_peer_id(entity)
                if pid not in self.__dict__:
                    # Note: `get_input_peer` already checks for `access_hash`
                    self.__dict__[pid] = utils.get_input_peer(entity)
            except TypeError:
                pass

    def __getitem__(self, item):
        """
        Gets the corresponding :tl:`InputPeer` for the given ID or peer,
        or raises ``KeyError`` on any error (i.e. cannot be found).
        """
        if not isinstance(item, int) or item < 0:
            try:
                return self.__dict__[utils.get_peer_id(item)]
            except TypeError:
                raise KeyError('Invalid key will not have entity') from None

        for cls in (types.PeerUser, types.PeerChat, types.PeerChannel):
            result = self.__dict__.get(utils.get_peer_id(cls(item)))
            if result:
                return result

        raise KeyError('No cached entity for the given key')

    def ensure_cached(
            self,
            update,
            has_user_id=frozenset(_has_field[('user_id', int)]),
            has_chat_id=frozenset(_has_field[('chat_id', int)]),
            has_channel_id=frozenset(_has_field[('channel_id', int)]),
            has_peer=frozenset(_has_field[('peer', 'TypePeer')] + _has_field[('peer', 'TypeDialogPeer')]),
            has_message=frozenset(_has_field[('message', 'TypeMessage')])
    ):
        """
        Ensures that all the relevant entities in the given update are cached.
        """
        # This method is called pretty often and we want it to have the lowest
        # overhead possible. For that, we avoid `isinstance` and constantly
        # getting attributes out of `types.` by "caching" the constructor IDs
        # in sets inside the arguments, and using local variables.
        dct = self.__dict__
        cid = update.CONSTRUCTOR_ID
        if cid in has_user_id and \
                update.user_id not in dct:
            return False

        if cid in has_chat_id and \
                utils.get_peer_id(types.PeerChat(update.chat_id)) not in dct:
            return False

        if cid in has_channel_id and \
                utils.get_peer_id(types.PeerChannel(update.channel_id)) not in dct:
            return False

        if cid in has_peer and \
                utils.get_peer_id(update.peer) not in dct:
            return False

        if cid in has_message:
            x = update.message
            y = getattr(x, 'peer_id', None)  # handle MessageEmpty
            if y and utils.get_peer_id(y) not in dct:
                return False

            y = getattr(x, 'from_id', None)
            if y and utils.get_peer_id(y) not in dct:
                return False

            # We don't quite worry about entities anywhere else.
            # This is enough.

        return True
