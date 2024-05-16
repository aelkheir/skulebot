"""Contains wrapper functions for creating, running and register handlers
for an application."""

import os

from telegram import Update
from telegram.ext import Application, ContextTypes, ExtBot

from src import commands, constants, conversations
from src.config import Config, ProductionConfig
from src.customcontext import CustomContext
from src.errorhandler import error_handler
from src.persistence import SQLPersistence
from src.typehandler import typehandler


async def post_init(application: Application):
    """Set bot bio, description in supported locales"""
    bot: ExtBot = application.bot
    for language_code, translation in constants.Locales:
        _ = translation.gettext
        await bot.set_my_description(_("Bot description"), language_code)
        await bot.set_my_short_description(_("Bot bio"), language_code)
        if language_code == constants.EN:
            await bot.set_my_description(_("Bot description"))
            await bot.set_my_short_description(_("Bot bio"))


def create() -> Application:
    """Creates an instance of `telegram.ext.Application` and configures it."""
    persistence = SQLPersistence()
    context_types = ContextTypes(context=CustomContext)
    return (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .post_init(post_init)
        .context_types(context_types)
        .persistence(persistence)
        .build()
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
