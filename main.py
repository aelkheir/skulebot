"""Setup and run a simple echo bot."""

import logging

from src import application

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    app = application.create()
    application.register_handlers(app)
    application.run(app)


if __name__ == "__main__":
    main()
