"""Setup and run a simple echo bot."""
import logging
import os

if os.getenv("ENV", "development") == "development":
    from dotenv import load_dotenv

    load_dotenv()

import random
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,


    MessageHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it the bot token.
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # in 'development' enviroments run the bot on polling, in 'production' use a webhook
    ENV = os.getenv("ENV", "development")
    if ENV == "development":
        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    elif ENV == "production":
        PORT = int(os.getenv("PORT", "8443"))
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            secret_token=os.getenv("WEBHOOK_SECRET_TOKEN"),
            webhook_url=os.getenv("WEBHOOK_URL"),
        )


if __name__ == "__main__":
    main()
