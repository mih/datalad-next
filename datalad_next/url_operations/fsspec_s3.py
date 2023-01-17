from typing import (
    Tuple,
)

from urllib.parse import urlparse

from fsspec.core import url_to_fs

from botocore.exceptions import NoCredentialsError

from datalad_next.utils.credman import CredentialManager

from . import (
    UrlOperationsAuthorizationError,
    UrlOperationsRemoteError,
)


def get_fs(url, target_url, *, cfg, credential) -> Tuple:
    object_url = target_url
    s3bucket_name = urlparse(object_url).netloc
    # TODO consider `endpoint_url` and maybe other customizations too
    fs_kwargs = {}
    try:
        # we start with no explicit credentials. This will cause boto to
        # use anonymous or some credentials stored in the config files
        # it recognizes, or use the respective env vars (incl session tokens).
        # This approach will yield the highest efficiency across a diverse
        # set of use cases
        return _get_fs(url, anon=False, **fs_kwargs)
    except PermissionError as e:
        # TODO log this error
        # access without credential provisioning failed. this could mean
        # different things:
        # - credentials are deployed externally via env vars, but anonymous
        #   access (anon=True) would be needed, because the credentials do
        #   not match
        # - credentionals are needed and provisioned, but are wrong
        pass
    except NoCredentialsError as e:
        # TODO log this error
        # credentials are known to be required needed by not available
        pass
    except Exception:
        # something unexpected, reraise
        raise UrlOperationsRemoteError(object_url) from e

    # if we get here, access failed in a credential-related fashion.
    # try to determine credentials for this target bucket.
    # if there are no credentials available, but credentials are deployed
    # via env vars, remote the credentials and try again

    # TODO the following could possibly migrate into
    # get_specialremote_credential_properties()
    #
    # compose a standard realm identifer
    # TODO recognize alternative endpoints here
    host = 's3.amazonaws.com'
    # this is the way AWS exposes bucket content via https, but we
    # stick to s3:// to avoid confusion. Therefore we are also not
    # adding the bucketname as the first component of the URL path
    # (where it would be in real s3:// URLs, instead of the host).
    # Taken together we get a specialization of an S3 realm that is
    # endpoint/service specific (hence we do not confuse AWS
    # credentials with those of a private MinIO instance).
    # TODO it is not 100% clear to mih whether a credential would
    # always tend to be for a bucket-wide scope, or whether per-object
    # credentials are a thing
    realm = f's3://{s3bucket_name}.{host}'

    credman = CredentialManager(cfg)
    credname, cred = credman.obtain(
        credential,
        prompt=f'Credential required to access {object_url}',
        query_props=dict(realm=realm),
        type_hint='s3',
        expected_props=['key', 'secret'],
    )

    credprops = dict(key=cred['key'], secret=cred['secret'])
    if object_url == url:
        fs_kwargs.update(**credprops)
    else:
        fs_kwargs.update(s3=credprops)

    # now try again, this time with a credential
    try:
        fs_url_stat = _get_fs(
            url,
            **fs_kwargs
        )
    except PermissionError as e:
        raise UrlOperationsAuthorizationError(object_url) from e
    except Exception as e:
        raise UrlOperationsRemoteError(object_url) from e
    # if we get here, we have a working credential, store it
    # (will be skipped without a given name after possibly
    # prompting for one)
    credman.set(
        # use given name, will prompt if none
        credname,
        # make lookup of most recently used credential for the realm
        # (the bucket) possible
        _last_used=True,
        _context=f'for accessing {realm}',
        **cred
    )
    return fs_url_stat


def _get_fs(url, **kwargs):
    fs, urlpath = url_to_fs(url, **kwargs)
    # check proper functioning
    stat = fs.stat(urlpath)
    return fs, urlpath, stat