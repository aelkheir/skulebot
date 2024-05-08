import re
from datetime import date

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

from src import constants
from src.customcontext import CustomContext
from src.models import Review
from src.utils import session

TYPES = Review.__mapper_args__.get("polymorphic_identity")


async def edit(update: Update, context: CustomContext):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.EDIT}/{NUMBER}$`
    """
    query = update.callback_query
    await query.answer()

    context.chat_data["url"] = context.match.group()
    _ = context.gettext

    message = _("Type date") + _("/empty to clear {}").format(_("Date"))
    await query.message.reply_text(message, parse_mode=ParseMode.HTML)

    return f"{constants.EDIT} {constants.DATE}"


@session
async def receive(update: Update, context: CustomContext, session: Session):
    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
        f"/{constants.EDIT}/{constants.DATE}$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Review, material_id)
    _ = context.gettext
    try:
        keyboard = [[context.buttons.back(url, rf"/{constants.EDIT}.*$")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message.text == "/empty":
            material.date = None
            message = _("Success! {} removed").format(_("Date"))
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
        message = _("Success! {} updated").format(_("Date"))
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE
    # Invalid date values
    except ValueError:
        await update.message.reply_text(message)
        return f"{constants.EDIT} {constants.DATE}"
