""" Generator the emits only complete lines """

from __future__ import annotations

from typing import (
    Generator,
    Iterable,
)


__all__ = ['lines_processor']


def lines_processor(iterable: Iterable[bytes | str],
                    separator: str | bytes | None = None,
                    keep_ends: bool = False,
                    ) -> Generator[bytes | str, None, None]:
    """ Generator that emits only complete lines from the input iterable

    This generator wraps another generator and yields only complete lines, which
    are built from the output of `iterable`. The lines are split either by
    `separator`, if `separator` is not `None`, or by the line-separators that
    are built into `splitlines`.

    The generator works on strings or bytes, depending on the type of the first
    element in `iterable`. During its runtime, the type of the elements in
    `iterable` must not change. If `separator` is not `None`, its type must
    match the type of the elements in `iterable`.

    The complexity of line-splitting without a defined separator is higher than
    the complexity of line-splitting with a defined separator (this is due to
    the externally unavailable set of line-separators that are built into
    `splitlines`).

    Also, not keeping ends is faster than keeping ends, when a separator is
    defined.

    EOF ends all lines, but will never be present in the result, even if
    ``keep_ends`` is ``True``.

    Parameters
    ----------
    iterable: Iterable[bytes | str]
        The iterable that yields the input data
    separator: str | bytes | None
        The separator that is used to split the lines. If `None`, the lines are
        split by the line-separators that are built into `splitlines`.
    keep_ends: bool
        If `True`, the line-separator will be contained in each yielded line. If
        `False`, the line-separator will not be contained in the yielded lines.

    Yields
    ------
    bytes | str
        The lines that are built from the input data. The type of the yielded
        lines depends on the type of the first element in `iterable`.
    """
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
