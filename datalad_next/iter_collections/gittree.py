"""Report on the content of a Git tree-ish

The main functionality is provided by the :func:`iter_gittree()` function.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import (
    Path,
    PurePath,
    PurePosixPath,
)
from typing import Generator

from datalad_next.runners import iter_subproc
from datalad_next.itertools import (
    decode_bytes,
    itemize,
)

from .utils import PathBasedItem

lgr = logging.getLogger('datalad.ext.next.iter_collections.gittree')


# TODO Could be `StrEnum`, came with PY3.11
class GitTreeItemType(Enum):
    """Enumeration of item types of Git trees
    """
    file = 'file'
    executablefile = 'executablefile'
    symlink = 'symlink'
    directory = 'directory'
    submodule = 'submodule'


@dataclass
class GitTreeItem(PathBasedItem):
    name: PurePath
    # gitsha is not the sha1 of the file content, but the output
    # of `git hash-object` which does something like
    # `printf "blob $(wc -c < "$file_name")\0$(cat "$file_name")" | sha1sum`
    gitsha: str | None = None
    gittype: GitTreeItemType | None = None


_mode_type_map = {
    '100644': GitTreeItemType.file,
    '100755': GitTreeItemType.executablefile,
    '040000': GitTreeItemType.directory,
    '120000': GitTreeItemType.symlink,
    '160000': GitTreeItemType.submodule,
}


def iter_gittree(
    path: Path,
    treeish: str,
    *,
    recursive: str = 'repository',
) -> Generator[GitTreeItem, None, None]:
    """Uses ``git ls-tree`` to report on a tree in a Git repository

    Parameters
    ----------
    path: Path
      Path of a directory in a Git repository to report on. This directory
      need not be the root directory of the repository, but must be part of
      the repository. If the directory is not the root directory of a
      non-bare repository, the iterator is constrained to items underneath
      that directory.
    recursive: {'repository', 'no'}, optional
      Behavior for recursion into subtrees. By default (``repository``),
      all tree within the repository underneath ``path``) are reported,
      but not tree within submodules. If ``no``, only direct children
      are reported on.

    Yields
    ------
    :class:`GitTreeItem`
    """
    # we force-convert to Path to give us the piece of mind we want.
    # The docs already ask for that, but it is easy to
    # forget/ignore and leads to non-obvious errors. Running this once is
    # a cheap safety net
    path = Path(path)

    # although it would be easy to also query the object size, we do not
    # do so, because it has a substantial runtime impact. It is unclear
    # what the main factor for the slowdown is, but in test cases I can
    # see 10x slower
    #lstree_args = ['--long']
    lstree_args = []
    if recursive == 'repository':
        lstree_args.append('-r')

    for line in _git_ls_tree(path, treeish, *lstree_args):
        yield _get_tree_item(line)


def _get_tree_item(spec: str) -> GitTreeItem:
    props, path = spec.split('\t')
    # 0::2 gets the first and third (last) item, effectively skippping the
    # type name (blob/tree etc.), we have the mode lookup for that, which
    # provides more detail
    mode, sha = props.split(' ')[0::2]
    return GitTreeItem(
        name=PurePosixPath(path),
        gitsha=sha,
        gittype=_mode_type_map[mode],
    )


def _git_ls_tree(path, *args):
    with iter_subproc(
            [
                'git',
                'ls-tree',
                # we rely on zero-byte splitting below
                '-z',
                # otherwise take whatever is coming in
                *args,
            ],
            cwd=path,
    ) as r:
        yield from decode_bytes(
            itemize(
                r,
                sep=b'\0',
                keep_ends=False,
            )
        )
