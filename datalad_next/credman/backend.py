from __future__ import annotations

from typing import (
    Generator,
)
from .credential import (
    Credential,
    Secret,
)


class CredentialBackend:
    """Interface to be implemented for any CredentialManager backend"""
    def __getitem__(self, identifier: str) -> Credential:
        """Retrieve a particular credential

        The returned credentials contains all known properties and a secret
        (if available).

        Parameters
        ----------
        identifier: str
          The identifier of the credential to be retrieved.

        Returns
        -------
        dict
          A mapping of credential properties to their values. The property key
          of a credential's secret is 'secret'.
        """
        raise NotImplementedError

    def __setitem__(self, identifier: str, value: Credential):
        """Set a particular credential.

        Parameters
        ----------
        identifier: str
          The identifier of the credential to be deleted.
        value: Credential
          The credential to set.
        """
        raise NotImplementedError

    def __delitem__(self, identifier: str):
        """Delete a particular credential

        Parameters
        ----------
        identifier: str
          The identifier of the credential to be deleted.
        """
        raise NotImplementedError

    def __iter__(self) -> Generator[str, None, None]:
        """Yields the identifiers of all known credentials"""
        raise NotImplementedError

    def __contains__(self, identifier: str) -> bool:
        raise NotImplementedError

    def get_credential_type(self, type_id: str | None = None) -> Type[Credential]:
        # the only recognized standard credentials is comprised (at minimum)
        # of a 'secret' only.
        # particular backends may support additional/different credentials.
        # the reason why backends get a say in this at all is that they
        # need to ensure that the "secret" (in whatever disguise it is
        # presented) actually is put into a secret store -- which may
        # be different from the place all other credential properties
        # are stored.
        # The credential manager is asking the backend on what information
        # it needs to know, and how they should be labeled, and feeds
        # the collected credential info in this format back to the backend.
        return Secret
