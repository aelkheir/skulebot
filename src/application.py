"""Contains wrapper functions for creating, running and register handlers
for an application."""

import os
from datetime import time
from typing import cast
from zoneinfo import ZoneInfo

from telegram import Chat, Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    ContextTypes,
    ExtBot,
    MessageHandler,
    filters,
)

from src import commands, constants, conversations, jobs, queries
from src.config import Config, ProductionConfig
from src.customcontext import CustomContext
from src.database import Session
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
    async def raise_app_handler_stop(_: Update, __: ContextTypes.DEFAULT_TYPE) -> None:
        raise ApplicationHandlerStop

    async def leave_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.application.create_task(
            cast(Chat, update.effective_chat).leave(), update=update
        )
        raise ApplicationHandlerStop

    # Ignore updates from error error channel
    application.add_handler(
        MessageHandler(
            filters.Chat(chat_id=Config.ERROR_CHANNEL_CHAT_ID), raise_app_handler_stop
        ),
        group=-2,
    )

    # Leave all channels but error channel
    application.add_handler(
        MessageHandler(
            filters.ChatType.CHANNEL
            & ~filters.StatusUpdate.LEFT_CHAT_MEMBER
            & ~(filters.Chat(chat_id=Config.ERROR_CHANNEL_CHAT_ID)),
            leave_chat,
        ),
        group=-2,
    )

    application.add_handler(typehandler, -1)
    application.add_handlers(commands.handlers, 1)
    application.add_handlers(conversations.handlers, 2)

    # Error Handler
    # Courtesy of @roolsbot
    application.add_error_handler(error_handler)


def schedule_jobs(application: Application):
    job_queue = application.job_queue
    zone = ZoneInfo("Africa/Khartoum")

    # Assignment deadline reminders
    with Session.begin() as session:
        root = queries.user(session=session, telegram_id=Config.ROOTIDS[0])
        if root is None:
            return
        for point in [
            time(hour=6, tzinfo=zone),
            time(hour=18, tzinfo=zone),
        ]:
            JOB_NAME = f"DEADLINE_REMINDER_{point}"
            jobs.remove_job_if_exists(
                JOB_NAME, CustomContext(application, root.chat_id, root.telegram_id)
            )
            job_queue.run_daily(
                jobs.deadline_reminder,
                point,
                name=JOB_NAME,
                user_id=root.telegram_id,
                chat_id=root.chat_id,
            )


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
