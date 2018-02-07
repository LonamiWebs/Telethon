import abc
from ..tl import types, functions
from ..extensions import markdown
from .. import utils


class _EventBuilder(abc.ABC):
    @abc.abstractmethod
    def build(self, update):
        """Builds an event for the given update if possible, or returns None"""

    @abc.abstractmethod
    def resolve(self, client):
        """Helper method to allow event builders to be resolved before usage"""
