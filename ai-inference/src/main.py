"""Entry point: run reconnecting WebSocket client forever."""
from __future__ import annotations

import asyncio
import logging
import signal

from .config import settings
from .ws_client import WSClient


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


async def _main() -> None:
    _setup_logging()
    log = logging.getLogger("ai.main")

    client = WSClient()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _stop(*_: object) -> None:
        log.info("shutdown requested")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    run_task = asyncio.create_task(client.run_forever())
    stop_task = asyncio.create_task(stop.wait())
    done, pending = await asyncio.wait({run_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in done:
        if t is run_task:
            # propagate exception if any
            t.result()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
