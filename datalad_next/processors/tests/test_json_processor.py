from __future__ import annotations

import json
import timeit

from ..json_processor import json_processor
from ..decode_processor import decode_processor
from ..lines_processor import lines_processor


o = {
    'list1': [
        'a', 'bäöl', 1
    ],
    'dict1': {
        'x': 123,
        'y': 234,
        'z': 456,
    }
}


b = b'\n'.join(json.dumps(x).encode() for x in [o] * 10)

c = [
    b[i:i+10]
    for i in range(0, len(b) + 10, 10)
]


def test_combi():
    print(c)

    for x in json_processor(decode_processor(lines_processor(c))):
        print(x)



def test_combi_performance():
    def read_all(g):
        #tuple(json_processor(lines_processor(g)))
        tuple(json_processor(decode_processor(lines_processor(g))))

    d = timeit.timeit(lambda: read_all(c), number=33000)
    print(d)
