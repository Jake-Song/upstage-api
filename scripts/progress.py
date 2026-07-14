"""Terminal progress indicator for standalone scripts."""

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event, Thread


@contextmanager
def progress_bar(label: str) -> Iterator[None]:
    stream = sys.stderr
    if not stream.isatty():
        yield
        return

    width = 24
    block_width = 6
    stopped = Event()
    started = time.monotonic()

    def draw(position: int) -> None:
        bar = (
            " " * position
            + "=" * block_width
            + " " * (width - block_width - position)
        )
        elapsed = time.monotonic() - started
        stream.write(f"\r[{bar}] {label} ({elapsed:.1f}s)")
        stream.flush()

    def animate() -> None:
        position = 0
        direction = 1
        while not stopped.wait(0.1):
            position += direction
            if position in {0, width - block_width}:
                direction *= -1
            draw(position)

    draw(0)
    thread = Thread(target=animate, daemon=True)
    thread.start()
    succeeded = False
    try:
        yield
        succeeded = True
    finally:
        stopped.set()
        thread.join()
        elapsed = time.monotonic() - started
        fill = "=" if succeeded else "!"
        status = "done" if succeeded else "failed"
        stream.write(f"\r[{fill * width}] {label}: {status} ({elapsed:.1f}s)\n")
        stream.flush()
