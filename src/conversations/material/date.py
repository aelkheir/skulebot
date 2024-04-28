import re
from datetime import date

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import Review
from src.utils import session

TYPES = Review.__mapper_args__.get("polymorphic_identity")


async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.EDIT}/{NUMBER}$`
    """
    query = update.callback_query
    await query.answer()

    context.chat_data["url"] = context.match.group()

    message = messages.type_date() + ". Type /empty to remove current date"
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.DATE}"


@session
async def receive(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
        f"/{constants.EDIT}/{constants.DATE}$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Review, material_id)
    try:
        keyboard = [[buttons.back(url, rf"/{constants.EDIT}.*$", "to Review")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message.text == "/empty":
            material.date = None
            message = messages.success_deleted("date")
            await update.message.reply_text(message, reply_markup=reply_markup)
            return constants.ONE

        year, month, day = (
            context.match.group("y"),
            int(context.match.group("m")),
            context.match.group("d"),
        )
        year, day = int(year) + 2000 if len(year) == 2 else int(year), (
            int(day) if day else 1
        )
        material.date = date(year, month, day)
        message = messages.success_updated("Review date")
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE
    # Invalid date values
    except ValueError:
        await update.message.reply_text(message)
        return f"{constants.EDIT} {constants.DATE}"
