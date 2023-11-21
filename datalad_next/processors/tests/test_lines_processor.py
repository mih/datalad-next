from __future__ import annotations

import pytest

from ..lines_processor import lines_processor


text_chunks = [
    'abc',
    'def\n012',
    '\n',
    '\n'
]
byte_chunks = [chunk.encode() for chunk in text_chunks]
text_chunks_other = [chunk.replace('\n', '\r\n') for chunk in text_chunks]
byte_chunks_other = [chunk.encode() for chunk in text_chunks_other]


@pytest.mark.parametrize(
    'input_chunks,separator',
    [
        (text_chunks, '\n'),
        (byte_chunks, b'\n'),
        (text_chunks_other, '\r\n'),
        (byte_chunks_other, b'\r\n')
    ]
)
def test_assembling_and_splitting(input_chunks, separator):
    empty = input_chunks[0][:0]

    r = tuple(lines_processor(input_chunks, keep_ends=True))
    assert len(r) == 3
    assert empty.join(r) == empty.join(input_chunks)

    r = tuple(lines_processor(input_chunks, separator=separator, keep_ends=True))
    assert len(r) == 3
    assert empty.join(r) == empty.join(input_chunks)

    r = tuple(lines_processor(input_chunks, separator=separator))
    assert len(r) == 3
    assert empty.join(r) == empty.join(input_chunks).replace(separator, empty)

    r = tuple(lines_processor(input_chunks + input_chunks[:1], separator=separator, keep_ends=True))
    assert len(r) == 4
    assert r[3] == input_chunks[0]
