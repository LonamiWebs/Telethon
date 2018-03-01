from abc import ABC, abstractmethod


class Session(ABC):
    @abstractmethod
    def clone(self):
        raise NotImplementedError

    @abstractmethod
    def set_dc(self, dc_id, server_address, port):
        raise NotImplementedError

    @property
    @abstractmethod
    def server_address(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def port(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def auth_key(self):
        raise NotImplementedError

    @auth_key.setter
    @abstractmethod
    def auth_key(self, value):
        raise NotImplementedError

    @property
    @abstractmethod
    def time_offset(self):
        raise NotImplementedError

    @time_offset.setter
    @abstractmethod
    def time_offset(self, value):
        raise NotImplementedError

    @property
    @abstractmethod
    def salt(self):
        raise NotImplementedError

    @salt.setter
    @abstractmethod
    def salt(self, value):
        raise NotImplementedError

    @property
    @abstractmethod
    def device_model(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def system_version(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def app_version(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def lang_code(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def system_lang_code(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def report_errors(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def sequence(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def flood_sleep_threshold(self):
        raise NotImplementedError

    @abstractmethod
    def close(self):
        raise NotImplementedError

    @abstractmethod
    def save(self):
        raise NotImplementedError

    @abstractmethod
    def delete(self):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def list_sessions(cls):
        raise NotImplementedError

    @abstractmethod
    def get_new_msg_id(self):
        raise NotImplementedError

    @abstractmethod
    def update_time_offset(self, correct_msg_id):
        raise NotImplementedError

    @abstractmethod
    def generate_sequence(self, content_related):
        raise NotImplementedError

    @abstractmethod
    def process_entities(self, tlo):
        raise NotImplementedError

    @abstractmethod
    def get_input_entity(self, key):
        raise NotImplementedError

    @abstractmethod
    def cache_file(self, md5_digest, file_size, instance):
        raise NotImplementedError

    @abstractmethod
    def get_file(self, md5_digest, file_size, cls):
        raise NotImplementedError
