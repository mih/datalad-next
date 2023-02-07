from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Generator


# this must implement enough of the dict API to work as a drop-in
# replacement.
# this is specifically not like the Credential class in datalad-core.
# this one does UI interactions, and interfaces operations with
# a secret store. here we only aim at providing a container for
# a credential.
# we make it a mapping, such that **credential works
class Credential(Mapping):
    #_secret_field = must be a str
    #_mandatory_props = must be a container like a tuple
    def __init__(self, *args, **kwargs):
        # _props is the true information store
        # most of what this class does is filter information access to
        # this dict
        self._props = dict(*args, **kwargs)
        self._props['type'] = self.type_label

    def __getitem__(self, key: str) -> str:
        return self._props[key]

    def __setitem__(self, key: str, value: str | None):
        if key == 'type' and self._props.get(key) != value:
            raise KeyError(
                'Must not change credential type, create new instance instead')
        self._props[key] = value

    def __delitem__(self, key: str):
        del self._props[key]

    def __iter__(self) -> Generator[str, None, None]:
        yield from self._props

    def __contains__(self, key: str) -> bool:
        return key in self._props

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._props.__repr__()})'

    def __len__(self) -> int:
        return len(self._props)

    def get(self, key, default=None):
        return self._props.get(key, default)

    @property
    def secret(self) -> str:
        return self._props.get(self._secret_field)

    @secret.setter
    def secret(self, val: str):
        self._props[self._secret_field] = val

    @property
    def secret_fieldname(self):
        return self._secret_field

    @property
    def properties(self) -> MappingProxyType:
        # read-only view
        return MappingProxyType(
            {k: v for k, v in self._props.items() if k != self._secret_field}
        )

    @property
    def missing_properties(self) -> set:
        # which properties are explicitly set to None
        missing = set(
            k for k, v in self._props.items() if v is None
        )
        # which props are declared mandatory and have no value or do not
        # exist at all
        missing.update(
            k for k in self._mandatory_props if not self._props.get(k)
        )
        return missing

    @property
    def type_label(self):
        return self.__class__.__name__.lower()


class Secret(Credential):
    # standard credential, a secret plus any credentials
    _secret_field = 'secret'
    _mandatory_props = tuple()


class UserPassword(Credential):
    # standard credential, a secret plus any credentials
    _secret_field = 'password'
    _mandatory_props = ('user', 'password')

    @property
    def type_label(self):
        # name choice has historic reasons, this is what datalad-core
        # did from its infancy
        return 'user_password'


class Token(Credential):
    _secret_field = 'token'
    _mandatory_props = tuple()
