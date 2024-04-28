import re
from datetime import datetime

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import Assignment
from src.utils import session

TYPES = Assignment.__mapper_args__.get("polymorphic_identity")


@session
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    """
    Runs on callback_data
    `^{URLPREFIX}/{COURSES}/(\d+)/{ASSIGNMENTS}/(\d+)
    /{EDIT}/{DEADLINE}?y=(?:(\d+)&m=(\d+)?&d=(\d+)?)?(:?\?IGNORE)?$`
    """

    query = update.callback_query
    await query.answer()

    if constants.IGNORE in context.match.group():
        return constants.ONE

    material_id = int(context.match.group("material_id"))
    material = session.get(Assignment, material_id)
    deadline = m.date() if (m := material.deadline) else None
    path = re.search(
        rf".*/{constants.EDIT}/{constants.DEADLINE}", context.match.group()
    ).group()

    context.chat_data["url"] = context.match.group()

    picker = buttons.datepicker(context.match, selected=deadline)
    date_time: datetime = picker.date_time

    if date_time:
        message = (
            f"Alright, you selected"
            f" <b>{date_time.strftime('%A %d %B %Y')}</b>,"
            " now type in the time in 24 hour format"
        )
        await query.message.reply_text(message, parse_mode=ParseMode.HTML)
        return f"{constants.EDIT} {constants.DEADLINE}"
    keyboard = picker.keyboard
    keyboard += [[buttons.back(path, rf"/{constants.EDIT}/{constants.DEADLINE}.*$")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        messages.title(context.match, session)
        + "\n"
        + f"{messages.course_text(context.match, session)}"
        + f"{messages.material_message_text(context.match, session)}"
        + "\nSelect deadline date.\nType /empty to remove current deadline"
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return f"{constants.EDIT} {constants.DEADLINE}"


@session
async def receive_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_id>\d+)/{constants.EDIT}"
        f"/{constants.DEADLINE}(?:\?y=(?P<y>\d+)(?:&m=(?P<m>\d+))?"
        f"(?:&d=(?P<d>\d+))?)?(?:/{constants.IGNORE})?$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Assignment, material_id)

    keyboard = [[buttons.back(url, f"/{constants.EDIT}/.*", "to Assignment")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message.text == "/empty":
        material.deadline = None
        message = messages.success_deleted("deadline")
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE

    hour, minute = int(context.match.groups()[0]), int(context.match.groups()[1])
    if hour >= 24 or minute >= 60:
        return constants.EDIT

    year = int(match.group("y"))
    month = int(match.group("m"))
    day = int(match.group("d"))

    d = datetime(year, month, day, hour, minute)
    material.deadline = d

    message = (
        f"Success! Assignment deadline"
        f" set to <b>{d.strftime('%A %d %B %Y %H:%M')}</b>."
    )
    await update.message.reply_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE
