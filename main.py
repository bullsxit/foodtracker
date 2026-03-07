from __future__ import annotations

import asyncio
import logging

from config import get_config
from database.database import db
from bot import create_application


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for LOCAL development – runs the bot in polling mode.

    In production the bot runs in webhook mode inside the FastAPI lifespan
    (started by `uvicorn webapp.server:app`).  This file is only needed for
    local testing without a public HTTPS URL.
    """
    # Ensure there is an event loop in the main thread.
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialise database.
    loop.run_until_complete(db.init_models())

    application = create_application()
    logger.info("Starting Telegram bot in polling mode (local dev)…")
    application.run_polling()


if __name__ == "__main__":
    main()
