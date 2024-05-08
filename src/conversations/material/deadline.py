import re
from datetime import datetime

from babel.dates import format_date, format_datetime
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

from src import constants, messages
from src.customcontext import CustomContext
from src.models import Assignment
from src.utils import session

TYPES = Assignment.__mapper_args__.get("polymorphic_identity")


@session
async def edit(update: Update, context: CustomContext, session: Session):
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
    course = material.course
    deadline = m.date() if (m := material.deadline) else None
    path = re.search(
        rf".*/{constants.EDIT}/{constants.DEADLINE}", context.match.group()
    ).group()

    context.chat_data["url"] = context.match.group()
    _ = context.gettext

    picker = context.buttons.datepicker(context.match, selected=deadline)
    date_time: datetime = picker.date_time

    if date_time:
        datestr = format_date(date_time, "E d MMM", locale=context.language_code)
        message = _("Deadline date selected {}").format(datestr)
        await query.message.reply_text(message, parse_mode=ParseMode.HTML)
        return f"{constants.EDIT} {constants.DEADLINE}"
    keyboard = picker.keyboard
    keyboard += [
        [context.buttons.back(path, rf"/{constants.EDIT}/{constants.DEADLINE}.*$")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        messages.title(context.match, session, context=context)
        + "\n"
        + _("t-symbol")
        + "─ "
        + course.get_name(context.language_code)
        + "\n"
        + messages.material_type_text(context.match, context=context)
        + messages.material_message_text(
            context.match, session, material=material, context=context
        )
        + "\n\n"
        + _("Select {}").format(_("Date"))
        + " "
        + _("/empty to clear {}").format(_("Date"))
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return f"{constants.EDIT} {constants.DEADLINE}"


@session
async def receive_time(update: Update, context: CustomContext, session: Session):
    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_id>\d+)/{constants.EDIT}"
        f"/{constants.DEADLINE}(?:\?y=(?P<y>\d+)(?:&m=(?P<m>\d+))?"
        f"(?:&d=(?P<d>\d+))?)?(?:/{constants.IGNORE})?$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Assignment, material_id)
    _ = context.gettext

    keyboard = [[context.buttons.back(url, f"/{constants.EDIT}/.*")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message.text == "/empty":
        material.deadline = None
        message = _("Success! {} removed").format(_("Deadline"))
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
    message = _("Success! Deadline set {}").format(
        format_datetime(d, "E d MMM hh:mm a", locale=context.language_code)
    )
    await update.message.reply_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE
