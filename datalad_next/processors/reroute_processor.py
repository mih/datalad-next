"""Generators that allow to route data around upstream generators"""

from __future__ import annotations

from collections import defaultdict
from typing import (
    Any,
    Callable,
    Generator,
    Iterable,
)


__all__ = ['route_in', 'route_out', 'join_with_list']

_active_fifos: dict[str, list] = defaultdict(list)


def route_out(iterable: Iterable,
              route_id: str,
              splitter: Callable[[Any], tuple[list, list]],
              ) -> Generator:
    """route data around the consumer of this generator"""
    fifo = _active_fifos[route_id]
    for item in iterable:
        data_to_process, data_to_store = splitter(item)
        if data_to_process:
            fifo.append(('proc', data_to_store))
            yield data_to_process
        else:
            fifo.append(('store', data_to_store))


def route_in(iterable: Iterable,
             route_id: str,
             joiner: Callable[[Any, Any], Any]
             ) -> Generator:
    """insert previously rerouted data into the consumer of this generator"""
    fifo = _active_fifos[route_id]
    for element in iterable:
        process_info = fifo.pop(0)
        while process_info[0] == 'store':
            yield joiner(None, process_info[1])
            process_info = fifo.pop(0)
        yield joiner(element, process_info[1])
    assert len(fifo) == 0
    del _active_fifos[route_id]


def join_with_list(processed_data: Any | None,
                   stored_data: list
                   ) -> Any | None:
    if not isinstance(processed_data, list):
        return [processed_data] + stored_data
    processed_data.extend(stored_data)
    return processed_data
