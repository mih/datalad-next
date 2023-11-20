from __future__ import annotations

from ..lines_processor import lines_processor


text = '''This is the first line of text
the second line of text, followed by an empty line

4th line of text with some non-ASCII characters: äöß


{"key0": "some text \\u1822"}

7th line with interesting characters: € 😃👽
an a non-terminated line'''

text_lines = text.splitlines(keepends=True)
text_chunks = [
    text[i:i+100]
    for i in range(0, len(text) + 100, 100)
]



text_chunks = [
    'abc',
    'def\n012',
    '\n',
    '\n'
]
byte_chunks = [chunk.encode() for chunk in text_chunks]


def test_assembling_and_splitting():
    r = tuple(lines_processor(text_chunks, keep_ends=True))
    assert len(r) == 3
    assert ''.join(r) == ''.join(text_chunks)

    s = tuple(lines_processor(byte_chunks, keep_ends=True))
    assert len(s) == 3
    assert b''.join(s) == b''.join(byte_chunks)

    r = tuple(lines_processor(text_chunks, separator='\n', keep_ends=True))
    assert len(r) == 3
    assert ''.join(r) == ''.join(text_chunks)

    s = tuple(lines_processor(byte_chunks, separator=b'\n', keep_ends=True))
    assert len(s) == 3
    assert b''.join(s) == b''.join(byte_chunks)

    r = tuple(lines_processor(text_chunks, separator='\n'))
    assert len(r) == 3
    assert ''.join(r) == ''.join(text_chunks).replace('\n', '')

    s = tuple(lines_processor(byte_chunks, separator=b'\n'))
    assert len(s) == 3
    assert b''.join(s) == b''.join(byte_chunks).replace(b'\n', b'')

    r = tuple(lines_processor(text_chunks + ['aaa'], separator='\n', keep_ends=True))
    assert len(r) == 4
    assert r[3] == 'aaa'
