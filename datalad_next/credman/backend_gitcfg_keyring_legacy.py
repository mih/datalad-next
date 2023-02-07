from typing import (
    Dict,
    Generator,
)

from datalad_next.exceptions import (
    CapturedException,
    CommandError,
)
from datalad_next.utils.credman_backend_gitcfg_keyring import (
    GitConfigKeyringBackend,
)


class GitConfigKeyringWithLegacySupportBackend(GitConfigKeyringBackend):
    def get_credential(self, identifier):
        # if we have a chance to query for stored legacy credentials
        # we do this first to have the more modern parts of the
        # system overwrite them reliably
        cred = self._get_legacy_field_from_keyring(identifier, type) or {}

        # retrieve properties from config
        cred.update(super().get_credential(identifier))

        secret = self._cfg.get(self._get_cred_cfg_var(identifier, 'secret'))

        return cred

    def _get_secret_from_keyring(self, name, type_hint=None):
        """
        Returns
        -------
        str or None
          None is return when no secret for the given credential name
          could be found. Otherwise, the secret is returned.
        """
        # always get the uniform
        secret = self._keyring.get(name, 'secret')
        if secret:
            return secret
        # fall back on a different "field" that is inferred from the
        # credential type
        secret_field = self._cred_types.get(
            type_hint, {}).get('secret')
        if not secret_field:
            return
        # first try to get it from the config to catch any overrides
        secret = self._cfg.get(self._get_cred_cfg_var(name, secret_field))
        if secret is not None:
            return secret
        secret = self._keyring.get(name, secret_field)
        return secret

    def delete_credential(self,
                          identifier: str,
                          type_hint: str | None = None) -> bool:
        super().delete_credential(self, identifier)

        # remove legacy records too
        for field in self._cred_types.get(
                type_hint, {}).get('fields', []):
            self._delete_keyring_field(identifier, field)

    def list_credentials(self) -> Generator[str, None, None]:
        from datalad.downloaders.providers import Providers

        # we must deduplicate between modern and legacy credentials
        # first modern ones
        reported = set()
        for name in super().list_credentials():
            if name not in reported:
                yield name
            reported.add(name)

        # and the legacy ones
        for name in set(
            p.credential.name
            for p in Providers.from_config_files()
            if p.credential
        ):
            if name not in reported:
                yield name
            reported.add(name)

    def _get_legacy_field_from_keyring(self, name, type_hint):
        if not type_hint or type_hint not in self._cred_types:
            return

        cred = {}
        lc = self._cred_types[type_hint]
        for field in (lc['fields'] or []):
            if field == lc['secret']:
                continue
            val = self._keyring.get(name, field)
            if val:
                # legacy credentials used property names with underscores,
                # but this is no longer syntax-compliant -- fix on read
                cred[field.replace('_', '-')] = val
        if 'type' not in cred:
            cred['type'] = type_hint
        return cred
