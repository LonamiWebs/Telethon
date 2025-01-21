from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from typing_extensions import Self

from ...tl import abcs
from .meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client.client import Client


class Authorizations(metaclass=NoPublicConstructor):
    """
    Authorizations, logged in sessions.

    You can get a user's authorizations from methods such as :meth:`telethon.Client.get_authorizations`.
    """

    def __init__(
        self,
        client: Client,
        raw: abcs.account.Authorizations,
    ) -> None:
        assert isinstance(raw, abcs.account.Authorizations)
        self._client = client
        self._raw = raw
        self._authorizations = [Authorization._from_raw(client, auth) for auth in self._raw.authorizations]

    @classmethod
    def _from_raw(
        cls,
        client: Client,
        authorizations: abcs.account.Authorizations,
    ) -> Self:
        return cls._create(client, authorizations)

    @property
    def ttl_days(self) -> int:
        return self._raw.authorization_ttl_days

    @property
    def sessions(self) -> List[abcs.Authorization]:
        return self._authorizations


class Authorization(metaclass=NoPublicConstructor):
    """
    A single authorization.

    This will only be constructed as part of :meth:`telethon.Client.get_authorizations`.
    """

    def __init__(
        self,
        client: Client,
        raw: abcs.Authorization,
    ) -> None:
        assert isinstance(raw, abcs.Authorization)
        self._client = client
        self._raw = raw

    @classmethod
    def _from_raw(
        cls,
        client: Client,
        authorization: abcs.Authorization,
    ) -> Self:
        return cls._create(client, authorization)

    @property
    def api_id(self) -> int:
        return self._raw.api_id

    @property
    def app_name(self) -> str:
        return self._raw.app_name

    @property
    def app_version(self) -> str:
        return self._raw.app_version

    @property
    def call_requests_disabled(self) -> bool:
        return self._raw.call_requests_disabled

    @property
    def country(self) -> str:
        return self._raw.country

    @property
    def current(self) -> bool:
        return self._raw.current

    @property
    def date_active(self) -> int:
        return self._raw.date_active

    @property
    def date_created(self) -> int:
        return self._raw.date_created

    @property
    def device_model(self) -> str:
        return self._raw.device_model

    @property
    def encrypted_requests_disabled(self) -> bool:
        return self._raw.encrypted_requests_disabled

    @property
    def hash(self) -> int:
        return self._raw.hash

    @property
    def ip(self) -> Optional[str]:
        if self._raw.ip == '':
            return None
        return self._raw.ip

    @property
    def official_app(self) -> bool:
        return self._raw.official_app

    @property
    def password_pending(self) -> bool:
        return self._raw.password_pending

    @property
    def platform(self) -> str:
        return self._raw.platform

    @property
    def region(self) -> str:
        return self._raw.region

    @property
    def system_version(self) -> str:
        return self._raw.system_version

    @property
    def unconfirmed(self) -> bool:
        return self._raw.unconfirmed
