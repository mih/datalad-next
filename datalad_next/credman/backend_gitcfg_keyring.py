from typing import (
    Dict,
    Generator,
    Type,
)

from datalad_next.exceptions import (
    CapturedException,
    CommandError,
)
from .backend import CredentialBackend
from .credential import (
    Credential,
    Secret,
    UserPassword,
    Token,
)

_credential_types = {
    'secret': Secret,
    'user_password': UserPassword,
    'token': Token,
}


class GitConfigKeyringBackend(CredentialBackend):
    _cfg_section_prefix = 'datalad.credential.'

    def __init__(self, cfg=None):
        """

        Parameters
        ----------
        cfg: ConfigManager, optional
          If given, all configuration queries are performed using this
          ``ConfigManager`` instance. Otherwise ``datalad.cfg`` is used.
        """
        self._cfg = cfg
        self.__keyring = None

    def get_credential_type(
            self, type_id: str | None = None) -> Type[Credential]:
        return _credential_types.get(type_id, Secret)

    def __getitem__(self, identifier: str) -> Credential:
        var_prefix = self._get_cred_cfg_var(identifier, '')
        # get any related info from config
        cred_props = {
            k[len(var_prefix):]: v
            for k, v in self._cfg.items()
            if k.startswith(var_prefix)
        }
        cred = self.get_credential_type(cred_props.get('type'))(**cred_props)
        # be statisfied with a secret from the config
        if cred.secret:
            return cred

        # otherwise ask the secret store, always get the uniform
        # 'secret' field
        secret = self._keyring.get(identifier, 'secret')

        if not cred_props and not secret:
            # no properties, no secret
            raise KeyError(f'No credential with name {identifier!r}')

        cred.secret = secret
        return cred

    def _get_credential_secret(self, identifier: str) -> str:
        return self._keyring.get(identifier, 'secret')

    def __setitem__(self, identifier: str, value: Credential):
        # update record, which properties did actually change?
        # this is not always the same as the input, e.g. when
        # a property would be _set_ at global scope, but is already
        # defined at system scope
        # TODO is this actually a good thing to do? What if the
        # higher scope drops the setting and cripples a user setup?
        # the feature-angle here is that an existing piece of
        # information is not copied into the user-domain, where it
        # is then fixed, and a system update cannot alter it without
        # user intervention
        updated = {}

        # remove props
        #
        remove_props = [
            k for k, v in properties.items() if v is None and k != 'secret']
        self._unset_credprops_anyscope(identifier, remove_props)
        updated.update(**{k: None for k in remove_props})

        # set non-secret props
        #
        set_props = {
            k: v for k, v in properties.items()
            if v is not None and k != 'secret'
        }
        for k, v in set_props.items():
            var = self._get_cred_cfg_var(identifier, k)
            if self._cfg.get(var) == v:
                # desired value already exists, we are not
                # storing again to preserve the scope it
                # was defined in
                continue
            # we always write to the global scope (ie. user config)
            # credentials are typically a personal, not a repository
            # specific entity -- likewise secrets go into a personal
            # not repository-specific store
            # for custom needs users can directly set the respective
            # config
            self._cfg.set(var, v, scope='global', force=True, reload=False)
            updated[k] = v
        if set_props:
            # batch reload
            self._cfg.reload()

        # at this point we will have a secret. it could be from ENV
        # or provided, or entered. we always want to put it in the
        # store
        if 'secret' in properties:
            # TODO at test for setting with secret=None as a property
            # this would cause a credential without a secret. Is this possible?
            # Is this desirable? If so, document and support explicitly. And
            # add a test
            self._keyring.set(identifier, 'secret', properties['secret'])
            updated['secret'] = properties['secret']
        return updated

    def __delitem__(self, identifier: str):
        # prefix for all config variables of this credential
        prefix = self._get_cred_cfg_var(identifier, '')

        to_remove = [
            k[len(prefix):] for k in self._cfg.keys()
            if k.startswith(prefix)
        ]
        if to_remove:
            self._unset_credprops_anyscope(identifier, to_remove)

        # we always use the uniform 'secret' field
        self._delete_keyring_field(identifier, 'secret')

    def __iter__(self) -> Generator[str, None, None]:
        yield from self._get_known_credential_names()

    def __contains__(self, identifier: str) -> bool:
        return identifier in self._get_known_credential_names()

    def _delete_keyring_field(self, record: str, field: str):
        # delete the secret from the keystore, if there is any
        try:
            self._keyring.delete(record, field)
        except Exception as e:
            if self._keyring.get(record, field) is None:
                # whatever it was, the target is reached
                CapturedException(e)
            else:
                # we could not delete the field
                raise  # pragma: nocover

    @property
    def _keyring(self):
        """Returns the DataLad keyring wrapper

        This internal property may vanish whenever changes to the supported
        backends are made.
        """
        if self.__keyring:
            return self.__keyring
        from datalad.support.keyring_ import keyring
        self.__keyring = keyring
        return keyring

    def _get_known_credential_names(self) -> set:
        known_credentials = set(
            '.'.join(k.split('.')[2:-1]) for k in self._cfg.keys()
            if k.startswith(self._cfg_section_prefix)
        )
        return known_credentials

    def _unset_credprops_anyscope(self, name, keys):
        """Reloads the config after unsetting all relevant variables

        This method does not modify the keystore.
        """
        nonremoved_vars = []
        for k in keys:
            var = self._get_cred_cfg_var(name, k)
            if var not in self._cfg:
                continue
            try:
                self._cfg.unset(var, scope='global', reload=False)
            except CommandError as e:
                CapturedException(e)
                try:
                    self._cfg.unset(var, scope='local', reload=False)
                except CommandError as e:
                    CapturedException(e)
                    nonremoved_vars.append(var)
        if nonremoved_vars:
            raise RuntimeError(
                f"Cannot remove configuration items {nonremoved_vars} "
                f"for credential, defined outside global or local "
                "configuration scope. Remove manually")
        self._cfg.reload()

    def _get_cred_cfg_var(self, name, prop):
        """Return a config variable name for a credential property

        Parameters
        ----------
        name : str
          Credential name
        prop : str
          Property name

        Returns
        -------
        str
        """
        return f'{self._cfg_section_prefix}{name}.{prop}'
