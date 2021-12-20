from abc import ABC, abstractmethod


class Session(ABC):
    def __init__(self):
        pass

    def clone(self, to_instance=None):
        """
        Creates a clone of this session file.
        """
        return to_instance or self.__class__()

    @abstractmethod
    def set_dc(self, dc_id, server_address, port):
        """
        Sets the information of the data center address and port that
        the library should connect to, as well as the data center ID,
        which is currently unused.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def dc_id(self):
        """
        Returns the currently-used data center ID.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def server_address(self):
        """
        Returns the server address where the library should connect to.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def port(self):
        """
        Returns the port to which the library should connect to.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def auth_key(self):
        """
        Returns an ``AuthKey`` instance associated with the saved
        data center, or `None` if a new one should be generated.
        """
        raise NotImplementedError

    @auth_key.setter
    @abstractmethod
    def auth_key(self, value):
        """
        Sets the ``AuthKey`` to be used for the saved data center.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def takeout_id(self):
        """
        Returns an ID of the takeout process initialized for this session,
        or `None` if there's no were any unfinished takeout requests.
        """
        raise NotImplementedError

    @takeout_id.setter
    @abstractmethod
    def takeout_id(self, value):
        """
        Sets the ID of the unfinished takeout process for this session.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_update_state(self, entity_id):
        """
        Returns the ``UpdateState`` associated with the given `entity_id`.
        If the `entity_id` is 0, it should return the ``UpdateState`` for
        no specific channel (the "general" state). If no state is known
        it should ``return None``.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_update_state(self, entity_id, state):
        """
        Sets the given ``UpdateState`` for the specified `entity_id`, which
        should be 0 if the ``UpdateState`` is the "general" state (and not
        for any specific channel).
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        """
        Called on client disconnection. Should be used to
        free any used resources. Can be left empty if none.
        """

    @abstractmethod
    async def save(self):
        """
        Called whenever important properties change. It should
        make persist the relevant session information to disk.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self):
        """
        Called upon client.log_out(). Should delete the stored
        information from disk since it's not valid anymore.
        """
        raise NotImplementedError

    @abstractmethod
    async def process_entities(self, tlo):
        """
        Processes the input ``TLObject`` or ``list`` and saves
        whatever information is relevant (e.g., ID or access hash).
        """
        raise NotImplementedError

    @abstractmethod
    async def get_input_entity(self, key):
        """
        Turns the given key into an ``InputPeer`` (e.g. ``InputPeerUser``).
        The library uses this method whenever an ``InputPeer`` is needed
        to suit several purposes (e.g. user only provided its ID or wishes
        to use a cached username to avoid extra RPC).
        """
        raise NotImplementedError
