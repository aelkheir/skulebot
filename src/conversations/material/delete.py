import re
from typing import List

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import HasNumber, Material
from src.models.material import __classes__
from src.utils import build_menu, session

TYPES = "|".join(
    [
        cls.__mapper_args__.get("polymorphic_identity")
        for cls in __classes__
        if issubclass(cls, HasNumber)
    ]
)


@session
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.DELETE}$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    has_confirmed = context.match.group("has_confirmed")
    material_id = context.match.group("material_id")
    material = session.get(Material, material_id)

    menu_buttons: List
    message = (
        messages.title(context.match, session)
        + "\n"
        + messages.course_text(context.match, session)
        + messages.material_message_text(context.match, session)
    )
    if has_confirmed is None:
        menu_buttons = buttons.delete_group(url=url)
        message += "\n" + messages.delete_confirm(
            messages.material_title_text(context.match, material)
        )
    elif has_confirmed == "0":
        menu_buttons = buttons.confirm_delete_group(url=url)
        message += "\n" + messages.delete_reconfirm(
            messages.material_title_text(context.match, material)
        )
    elif has_confirmed == "1":
        session.delete(material)
        menu_buttons = [
            buttons.back(
                url,
                pattern=rf"/\d+/{constants.DELETE}",
                text=f"to {material.type.capitalize()}s",
            )
        ]
        message = messages.success_deleted(
            messages.material_title_text(context.match, material)
        )

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE
