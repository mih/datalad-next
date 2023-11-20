from __future__ import annotations

from typing import Iterable

from ..pattern_processor import pattern_processor


def test_pattern_processor():

    def perform_test(data_chunks: Iterable[str | bytes],
                     pattern: str | bytes,
                     expected: list[str | bytes],
                     ) -> None:

        result = list(pattern_processor(data_chunks, pattern=pattern))
        assert result == expected

    perform_test(
        data_chunks=['a', 'b', 'c', 'd', 'e'],
        pattern='abc',
        expected=['abc', 'de'],
    )

    perform_test(
        data_chunks=['a', 'b', 'c', 'a', 'b', 'c'],
        pattern='abc',
        expected=['abc', 'abc'],
    )

    # Ensure that unaligned pattern prefixes are not keeping data chunks short
    perform_test(
        data_chunks=['a', 'b', 'c', 'dddbbb', 'a', 'b', 'x'],
        pattern='abc',
        expected=['abc', 'dddbbb', 'abx'],
    )

    # Expect that a trailing minimum length-chunk that ends with a pattern
    # prefix is not returned as data, but as remainder, if it is not the final
    # chunk
    perform_test(
        data_chunks=['a', 'b', 'c', 'd', 'a'],
        pattern='abc',
        expected=['abc', 'da'],
    )

    # Expect the last chunk to be returned as data, if final is True, although
    # it ends with a pattern prefix. If final is false, the last chunk will be
    # returned as a remainder, because it ends with a pattern prefix.
    perform_test(
        data_chunks=['a', 'b', 'c', 'dddbbb', 'a'],
        pattern='abc',
        expected=['abc', 'dddbbb', 'a'],
    )

    perform_test(
        data_chunks=['a', 'b', 'c', '9', 'a'],
        pattern='abc',
        expected=['abc', '9a'],
    )
