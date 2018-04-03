from abc import ABC, abstractmethod
import time
import struct
import os


class Session(ABC):
    def __init__(self):
        # Session IDs can be random on every connection
        self.id = struct.unpack('q', os.urandom(8))[0]

        self._sequence = 0
        self._last_msg_id = 0
        self._time_offset = 0
        self._salt = 0
        self._report_errors = True
        self._flood_sleep_threshold = 60

    def clone(self, to_instance=None):
        """
        Creates a clone of this session file.
        """
        cloned = to_instance or self.__class__()
        cloned._report_errors = self.report_errors
        cloned._flood_sleep_threshold = self.flood_sleep_threshold
        return cloned

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
        data center, or ``None`` if a new one should be generated.
        """
        raise NotImplementedError

    @auth_key.setter
    @abstractmethod
    def auth_key(self, value):
        """
        Sets the ``AuthKey`` to be used for the saved data center.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self):
        """
        Called on client disconnection. Should be used to
        free any used resources. Can be left empty if none.
        """

    @abstractmethod
    def save(self):
        """
        Called whenever important properties change. It should
        make persist the relevant session information to disk.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self):
        """
        Called upon client.log_out(). Should delete the stored
        information from disk since it's not valid anymore.
        """
        raise NotImplementedError

    @classmethod
    def list_sessions(cls):
        """
        Lists available sessions. Not used by the library itself.
        """
        return []

    @abstractmethod
    def process_entities(self, tlo):
        """
        Processes the input ``TLObject`` or ``list`` and saves
        whatever information is relevant (e.g., ID or access hash).
        """
        raise NotImplementedError

    @abstractmethod
    def get_input_entity(self, key):
        """
        Turns the given key into an ``InputPeer`` (e.g. ``InputPeerUser``).
        The library uses this method whenever an ``InputPeer`` is needed
        to suit several purposes (e.g. user only provided its ID or wishes
        to use a cached username to avoid extra RPC).
        """
        raise NotImplementedError

    @abstractmethod
    def cache_file(self, md5_digest, file_size, instance):
        """
        Caches the given file information persistently, so that it
        doesn't need to be re-uploaded in case the file is used again.

        The ``instance`` will be either an ``InputPhoto`` or ``InputDocument``,
        both with an ``.id`` and ``.access_hash`` attributes.
        """
        raise NotImplementedError

    @abstractmethod
    def get_file(self, md5_digest, file_size, cls):
        """
        Returns an instance of ``cls`` if the ``md5_digest`` and ``file_size``
        match an existing saved record. The class will either be an
        ``InputPhoto`` or ``InputDocument``, both with two parameters
        ``id`` and ``access_hash`` in that order.
        """
        raise NotImplementedError

    @property
    def salt(self):
        """
        Returns the current salt used when encrypting messages.
        """
        return self._salt

    @salt.setter
    def salt(self, value):
        """
        Updates the salt (integer) used when encrypting messages.
        """
        self._salt = value

    @property
    def report_errors(self):
        """
        Whether RPC errors should be reported
        to https://rpc.pwrtelegram.xyz or not.
        """
        return self._report_errors

    @report_errors.setter
    def report_errors(self, value):
        """
        Sets the boolean value that indicates whether RPC errors
        should be reported to https://rpc.pwrtelegram.xyz or not.
        """
        self._report_errors = value

    @property
    def time_offset(self):
        """
        Time offset (in seconds) to be used
        in case the local time is incorrect.
        """
        return self._time_offset

    @time_offset.setter
    def time_offset(self, value):
        """
        Updates the integer time offset in seconds.
        """
        self._time_offset = value

    @property
    def flood_sleep_threshold(self):
        """
        Threshold below which the library should automatically sleep
        whenever a FloodWaitError occurs to prevent it from raising.
        """
        return self._flood_sleep_threshold

    @flood_sleep_threshold.setter
    def flood_sleep_threshold(self, value):
        """
        Sets the new time threshold (integer, float or timedelta).
        """
        self._flood_sleep_threshold = value

    @property
    def sequence(self):
        """
        Current sequence number needed to generate messages.
        """
        return self._sequence

    @sequence.setter
    def sequence(self, value):
        """
        Updates the sequence number (integer) value.
        """
        self._sequence = value

    def get_new_msg_id(self):
        """
        Generates a new unique message ID based on the current
        time (in ms) since epoch, applying a known time offset.
        """
        now = time.time() + self._time_offset
        nanoseconds = int((now - int(now)) * 1e+9)
        new_msg_id = (int(now) << 32) | (nanoseconds << 2)

        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id

        return new_msg_id

    def update_time_offset(self, correct_msg_id):
        """
        Updates the time offset to the correct
        one given a known valid message ID.
        """
        now = int(time.time())
        correct = correct_msg_id >> 32
        self._time_offset = correct - now
        self._last_msg_id = 0

    def generate_sequence(self, content_related):
        """
        Generates the next sequence number depending on whether
        it should be for a content-related query or not.
        """
        if content_related:
            result = self._sequence * 2 + 1
            self._sequence += 1
            return result
        else:
            return self._sequence * 2
