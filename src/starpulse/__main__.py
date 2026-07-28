"""Entry point: ``python -m starpulse`` or the ``starpulse`` console script."""

from __future__ import annotations

import uvicorn

from starpulse.app import create_app
from starpulse.config.settings import load_settings


def main() -> None:
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.server.host, port=settings.server.port)


if __name__ == "__main__":
    main()
