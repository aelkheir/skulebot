import re
from typing import List

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

from src import constants, messages
from src.customcontext import CustomContext
from src.models import HasNumber, Material, SingleFile
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
async def handler(update: Update, context: CustomContext, session: Session):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.DELETE}$`
    """

    query = update.callback_query
    await query.answer()

    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    has_confirmed = context.match.group("has_confirmed")
    material_id = context.match.group("material_id")
    material = session.get(Material, material_id)
    course = material.course

    material_title = messages.material_title_text(context.match, material, context)

    _ = context.gettext

    menu_buttons: List
    message = (
        messages.title(context.match, session, context=context)
        + "\n"
        + _("t-symbol")
        + "─ "
        + course.get_name(context.language_code)
        + "\n"
        + messages.material_type_text(context.match, context=context)
        + ("\n" if isinstance(material, SingleFile) else "")
        + messages.material_message_text(
            context.match, session, material=material, context=context
        )
        + "\n\n"
    )
    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message += _("Delete warning {}").format(material_title)
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message += _("Confirm delete warning {}").format(material_title)
    elif has_confirmed == "1":
        session.delete(material)
        menu_buttons = [
            context.buttons.back(
                url,
                pattern=rf"/\d+/{constants.DELETE}",
                text=_(f"{material.type}s"),
            )
        ]
        message = _("Success! {} deleted").format(material_title)

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE
