""" Iterators that support subprocess pipelining and output processing

This module provides iterators that are useful when combining
iterable_subprocesses and for processing of subprocess output.

.. currentmodule:: datalad_next.processors

.. autosummary::
   :toctree: generated

    decode_processor
    json_processor
    json_processor_with_flag
    lines_processor
    pattern_processor
    route_out
    route_in
    join_with_list
"""


from .decode_processor import decode_processor
from .json_processor import (
    json_processor,
    json_processor_with_flag,
)
from .lines_processor import lines_processor
from .pattern_processor import pattern_processor
from .reroute_processor import (
    join_with_list,
    route_in,
    route_out,
)
