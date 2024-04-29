"""Contains wrapper functions for creating, running and register handlers
for an application."""

import os

from telegram import Update
from telegram.ext import Application

from src import commands, conversations
from src.config import Config, ProductionConfig
from src.errorhandler import error_handler
from src.persistence import SQLPersistence
from src.typehandler import typehandler


def create() -> Application:
    """Creates an instance of `telegram.ext.Application` and configures it."""
    persistence = SQLPersistence()
    return (
        Application.builder().token(Config.BOT_TOKEN).persistence(persistence).build()
    )


def register_handlers(application: Application):
    """Registers `CommandHandler`s, `ConversationHandler`s ...etc."""

    application.add_handler(typehandler, -1)
    application.add_handlers(commands.handlers, 1)
    application.add_handlers(conversations.handlers, 2)

    # Error Handler
    application.add_error_handler(error_handler)


def run(application: Application):
    """Runs the application.
    Will use `run_polling` in development environments, and `run_webhook`
    in production"""
    if os.getenv("ENV") == "production":
        application.run_webhook(
            listen="0.0.0.0",
            port=ProductionConfig.PORT,
            secret_token=ProductionConfig.WEBHOOK_SERCRET_TOKEN,
            webhook_url=ProductionConfig.WEBHOOK_URL,
        )
    else:
        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=Update.ALL_TYPES)
