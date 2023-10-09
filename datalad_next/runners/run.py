"""
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from subprocess import (
    DEVNULL,
    TimeoutExpired,
)
from typing import (
    IO,
)

from datalad.runner.nonasyncrunner import _ResultGenerator
from datalad.runner.protocol import GeneratorMixIn


from . import (
    Protocol,
    ThreadedRunner,
)


class TimeoutHandlingGenerator(Generator):
    def __init__(self, result_generator):
        self.result_generator = result_generator
        self.countdown = None
        self.first_call = False
        self.return_code = None

    def send(self, value):
        """ Send function that filters and handles timeouts

        If `self.countdown` is not None and the first process timeout is
        encountered, a termination request is sent to the running process.
        If this is not the first process timeout, countdown is decremented by
        one. If countdown reaches zero, the process is killed.
        """
        result = next(self.result_generator)
        if result == ('timeout', None):
            if self.countdown is not None:
                if self.first_call is True:
                    self.result_generator.runner.process.terminate()
                    self.first_call = False
                    return result
                self.countdown -= 1
                if self.countdown <= 0:
                    self.result_generator.runner.process.kill()
        return result

    def throw(self, exception_type, value=None, trace_back=None):
        return Generator.throw(self, exception_type, value, trace_back)


@contextmanager
def run(
    cmd: list,
    protocol_class: Protocol,
    *,
    cwd: Path | None = None,
    input: int | IO | bytes | Queue[bytes | None] | None = None,
    # only generator protocols make sense for timeout, and timeouts are
    # only checked when the generator polls
    timeout: float | None = None,
) -> dict | _ResultGenerator:
    runner = ThreadedRunner(
        cmd=cmd,
        protocol_class=protocol_class,
        stdin=DEVNULL if input is None else input,
        cwd=cwd,
        timeout=timeout,
        exception_on_error=False,
    )
    result_or_generator = runner.run()
    if issubclass(protocol_class, GeneratorMixIn):
        user_generator = TimeoutHandlingGenerator(result_generator=result_or_generator)
        user_generator.runner = result_or_generator.runner
        try:
            yield user_generator
        finally:
            # if we get here the subprocess has no business running
            # anymore. When run() exited normally, this should
            # already be the case. To make sure that no zombies
            # accumulate, we arm the `TimeoutHandlingGenerator` by
            # setting its countdown attribute to a number N . This will
            # trigger a terminate-signal to the process at the next
            # timeout and after N additional timeouts the process will
            # receive a kill-signal.
            user_generator.countdown = 2
            tuple(user_generator)
            # Copy the return code to the user-facing generator
            user_generator.return_code = result_or_generator.return_code
    else:
        try:
            yield result_or_generator
        finally:
            pass
