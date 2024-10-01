
from __future__ import annotations

import logging
import re
from abc import abstractmethod
from os import name as os_name
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Hashable,
)

if TYPE_CHECKING:
    from os import PathLike

    from datasalad.settings import Setting

from datalad.consts import DATASET_CONFIG_FILE  # type: ignore
from datasalad.itertools import (
    decode_bytes,
    itemize,
)
from datasalad.runners import CommandError as SaladCommandError
from datasalad.settings import CachingSource

from datalad_next.config.item import ConfigurationItem
from datalad_next.runners import (
    CommandError,
    call_git,
    call_git_oneline,
    iter_git_subproc,
)

lgr = logging.getLogger('datalad.config')

class GitConfig(CachingSource):
    """Configuration source using git-config to read and write"""
    is_writable = True

    # Unfortunately there is no known way to tell git to ignore possible local git
    # repository, and unsetting of --git-dir could cause other problems.  See
    # https://lore.kernel.org/git/YscCKuoDPBbs4iPX@lena.dartmouth.edu/T/ .  Setting
    # the git directory to /dev/null or on Windows analogous nul file (could be
    # anywhere, see https://stackoverflow.com/a/27773642/1265472) see allow to
    # achieve the goal to prevent a repository in the current working directory
    # from leaking configuration into the output.
    nul = 'b:\\nul' if os_name == 'nt' else '/dev/null'

    @abstractmethod
    def _get_git_config_cmd(self) -> list[str]:
        """Return the git-config command suitable for a particular config"""

    @abstractmethod
    def _get_git_config_cwd(self) -> Path | None:
        """Return path the git-config command should run in"""

    def reinit(self) -> None:
        super().reinit()
        self._sources: set[str | Path] = set()

    def load(self) -> None:
        cwd = self._get_git_config_cwd() or Path.cwd()
        dct: dict[str, str | tuple[str, ...]] = {}
        fileset: set[str] = set()

        try:
            with iter_git_subproc(
                [*self._get_git_config_cmd(),
                 '--show-origin', '--list', '-z'],
                input=None,
                cwd=cwd,
            ) as gitcfg:
                for line in itemize(
                    decode_bytes(gitcfg),
                    sep='\0',
                    keep_ends=False,
                ):
                    _proc_dump_line(line, fileset, dct)
        except (CommandError, SaladCommandError):
            # TODO: only pass for the case where no corresponding
            # source is found. E.g., it fails with --system whenever
            # there is no /etc/gitconfig
            pass

        # take blobs with verbatim markup
        origin_blobs = {f for f in fileset if f.startswith('blob:')}
        # convert file specifications to Path objects with absolute paths
        origin_paths = {Path(f[5:]) for f in fileset if f.startswith('file:')}
        origin_paths = {f if f.is_absolute() else cwd / f for f in origin_paths}
        # TODO: add "version" tracking. The legacy config manager used mtimes
        # and we will too. but we also need to ensure that the version for
        # the "blobs" is known
        self._sources = origin_paths.union(origin_blobs)

        setter = '__setitem__'
        for k, v in dct.items():
            if not isinstance(v, tuple):
                v = (v,)
            for val in v:
                item = ConfigurationItem(
                    value=val,
                    store_target=self.__class__,
                )
                getattr(super(), setter)(k, item)
                # for every subsequent value we must call add()
                setter = 'add'


    def __setitem__(self, key: Hashable, value: Setting) -> None:
        call_git(
            [*self._get_git_config_cmd(), '--replace-all', str(key), str(value.value)],
            capture_output=True,
        )
        super().__setitem__(key, value)

    def add(self, key: Hashable, value: Setting) -> None:
        call_git(
            [*self._get_git_config_cmd(), '--add', str(key), str(value.value)],
            capture_output=True,

        )
        super().add(key, value)


class SystemGitConfig(GitConfig):
    def _get_git_config_cmd(self) -> list[str]:
        return [f'--git-dir={self.nul}', 'config', '--system']

    def _get_git_config_cwd(self) -> Path | None:
        return Path.cwd()


class GlobalGitConfig(GitConfig):
    def _get_git_config_cmd(self) -> list[str]:
        return [f'--git-dir={self.nul}', 'config', '--global']

    def _get_git_config_cwd(self) -> Path | None:
        return Path.cwd()


class LocalGitConfig(GitConfig):
    def __init__(self, path: PathLike):
        super().__init__()
        pathobj = Path(path)

        try:
            #TODO CHECK FOR GIT_DIR and adjust
            self._in_worktree = call_git_oneline(
                ['rev-parse', '--is-inside-work-tree'],
                cwd=pathobj,
                force_c_locale=True,
            ) == 'true'
        except CommandError as e:
            from os import environ
            msg = f"no Git repository at {path}: {e!r} {environ.get('GIT_DIR')}"
            raise ValueError(msg) from e

        self._gitdir = Path(
            path if not self._in_worktree
            else call_git_oneline(
                ['rev-parse', '--path-format=absolute', '--git-dir'],
                cwd=pathobj,
                force_c_locale=True,
            )
        )

    def _get_git_config_cmd(self) -> list[str]:
        return ['--git-dir', str(self._gitdir), 'config', '--local']

    def _get_git_config_cwd(self) -> Path | None:
        # we set --git-dir, CWD does not matter
        return None


class DataladBranchConfig(LocalGitConfig):
    def __init__(self, path: PathLike):
        super().__init__(path)
        self._path = path

    def _get_git_config_cmd(self) -> list[str]:
        return [
            '--git-dir', str(self._gitdir), 'config',
            *(('--file', str(self._path / DATASET_CONFIG_FILE))
              if self._in_worktree
              else ('--blob', f'HEAD:{DATASET_CONFIG_FILE}'))
        ]

    def _ensure_target_dir(self):
        cmd = self._get_git_config_cmd()
        if '--file' in cmd:
            custom_file = Path(cmd[cmd.index('--file') + 1])
            custom_file.parent.mkdir(exist_ok=True)

    def __setitem__(self, key: Hashable, value: Setting) -> None:
        self._ensure_target_dir()
        super().__setitem__(key, value)

    def add(self, key: Hashable, value: Setting) -> None:
        self._ensure_target_dir()
        super().add(key, value)


def _proc_dump_line(
    line: str,
    fileset: set[str],
    dct: dict[str, str | tuple[str, ...]],
) -> None:
    # line is a null-delimited chunk
    k = None
    # in anticipation of output contamination, process within a loop
    # where we can reject non syntax compliant pieces
    while line:
        if line.startswith(('file:', 'blob:')):
            fileset.add(line)
            break
        if line.startswith('command line:'):
            # no origin that we could as a pathobj
            break
        # try getting key/value pair from the present chunk
        k, v = _gitcfg_rec_to_keyvalue(line)
        if k is not None:
            # we are done with this chunk when there is a good key
            break
        # discard the first line and start over
        ignore, line = line.split('\n', maxsplit=1)
        lgr.debug('Non-standard git-config output, ignoring: %s', ignore)
    if not k:
        # nothing else to log, all ignored dump was reported before
        return
    if TYPE_CHECKING:
        assert k is not None
    if v is None:
        # man git-config:
        # just name, which is a short-hand to say that the variable is
        # the boolean
        v = "true"
    # multi-value reporting
    present_v = dct.get(k)
    if present_v is None:
        dct[k] = v
    elif isinstance(present_v, tuple):
        dct[k] = (*present_v, v)
    else:
        dct[k] = (present_v, v)


# git-config key syntax with a section and a subsection
# see git-config(1) for syntax details
cfg_k_regex = re.compile(r'([a-zA-Z0-9-.]+\.[^\0\n]+)$', flags=re.MULTILINE)
# identical to the key regex, but with an additional group for a
# value in a null-delimited git-config dump
cfg_kv_regex = re.compile(
    r'([a-zA-Z0-9-.]+\.[^\0\n]+)\n(.*)$',
    flags=re.MULTILINE | re.DOTALL
)


def _gitcfg_rec_to_keyvalue(rec: str) -> tuple[str | None, str | None]:
    """Helper for parse_gitconfig_dump()

    Parameters
    ----------
    rec: str
      Key/value specification string

    Returns
    -------
    str, str
      Parsed key and value. Key and/or value could be None
      if not syntax-compliant (former) or absent (latter).
    """
    kv_match = cfg_kv_regex.match(rec)
    if kv_match:
        k, v = kv_match.groups()
    elif cfg_k_regex.match(rec):
        # could be just a key without = value, which git treats as True
        # if asked for a bool
        k, v = rec, None
    else:
        # no value, no good key
        k = v = None
    return k, v
