""" Generator the emits only complete lines """

from __future__ import annotations

import sys
from typing import (
    Generator,
    Iterable,
)


__all__ = ['lines_processor']


def lines_processor(iterable: Iterable[bytes | str],
                    separator: str | bytes | None = None,
                    keep_ends: bool = False,
                    ) -> Generator[bytes | str, None, None]:

    if separator is None:
        yield from _split_lines(iterable, keep_ends=keep_ends)
    else:
        yield from _split_lines_with_separator(
            iterable,
            separator=separator,
            keep_ends=keep_ends,
        )


def _split_lines_with_separator(iterable: Iterable[bytes | str],
                                separator: str | bytes,
                                keep_ends: bool = False,
                                ) -> Generator[bytes | str, None, None]:
    assembled = None
    for chunk in iterable:
        if not assembled:
            assembled = chunk
        else:
            assembled += chunk
        lines = assembled.split(sep=separator)
        if len(lines) == 1:
            continue

        if assembled.endswith(separator):
            assembled = None
        else:
            assembled = lines[-1]
        lines.pop(-1)
        if keep_ends:
            for line in lines:
                yield line + separator
        else:
            yield from lines

    if assembled:
        yield assembled


def _split_lines(iterable: Iterable[bytes | str],
                 keep_ends: bool = False,
                 ) -> Generator[bytes | str, None, None]:
    assembled = None
    for chunk in iterable:
        if not assembled:
            assembled = chunk
        else:
            assembled += chunk
        # We don't know all elements on which python splits lines, therefore we
        # split once with ends and once without ends. Lines that differ have no
        # ending
        lines_with_end = assembled.splitlines(keepends=True)
        lines_without_end = assembled.splitlines(keepends=False)
        if lines_with_end[-1] == lines_without_end[-1]:
            assembled = lines_with_end[-1]
            lines_with_end.pop(-1)
            lines_without_end.pop(-1)
        else:
            assembled = None
        if keep_ends:
            yield from lines_with_end
        else:
            yield from lines_without_end

    if assembled:
        yield assembled
