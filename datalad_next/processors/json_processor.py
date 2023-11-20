""" Generator that converts input chunks into JSON objects """

from __future__ import annotations

import json
from typing import (
    Any,
    Generator,
    Iterable,
)


__all__ = ['json_processor']


def json_processor(iterable: Iterable[bytes | str],
                   ) -> Generator[tuple[Any, bool], None, None]:
    """convert items yielded by `iterable` into JSON objects

    The items should be correct JSON-strings (or bytestrings). Incorrect JSON
    will lead to a JSONDecodeError. Generally JSON-decoding is faster if the
    items are strings. Bytestrings will work as well, but might be slower
    """
    for json_string in iterable:
        yield json.loads(json_string)


def json_processor_with_flag(iterable: Iterable[bytes | str],
                             ) -> Generator[tuple[Any, bool], None, None]:
    """convert items yielded by `iterable` into JSON objects and a success flag

    The items should be correct JSON-strings (or bytestrings). The generator
    returns either a tuple containing a decoded JSON-object and `True`, if the
    JSON string could be deooded correctly, or it will return an exception and
    `False`, if a JSONDecodeError occurred during JSON parsing.
    Generally JSON-decoding is faster if the items are strings. Bytestrings will
    work as well, but might be slower.
    """
    for json_string in iterable:
        try:
            yield json.loads(json_string), True
        except json.decoder.JSONDecodeError as e:
            yield e, False
