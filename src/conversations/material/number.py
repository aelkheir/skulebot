import re

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import HasNumber
from src.models.material import Material, __classes__
from src.utils import session

TYPES = "|".join(
    [
        cls.__mapper_args__.get("polymorphic_identity")
        for cls in __classes__
        if issubclass(cls, HasNumber)
    ]
)


async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.EDIT}/{NUMBER}$`
    """
    query = update.callback_query
    await query.answer()

    context.chat_data["url"] = context.match.group()

    message = messages.type_number()
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.NUMBER}"


@session
async def receive(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    material_number = int(context.match.groups()[0])

    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
        f"/{constants.EDIT}/{constants.NUMBER}$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Material, material_id)
    if isinstance(material, HasNumber):
        material.number = material_number

        keyboard = [
            [
                buttons.back(
                    url,
                    pattern=rf"/{constants.EDIT}.*$",
                    text=f"to {material.type.capitalize()}",
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = messages.success_updated(f"{material.type.capitalize()} number")
        await update.message.reply_text(message, reply_markup=reply_markup)

        return constants.ONE
    return None
