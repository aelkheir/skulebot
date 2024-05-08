import re

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update

from src import constants
from src.customcontext import CustomContext
from src.models import HasNumber, Material
from src.models.material import __classes__
from src.utils import session

TYPES = "|".join(
    [
        cls.__mapper_args__.get("polymorphic_identity")
        for cls in __classes__
        if issubclass(cls, HasNumber)
    ]
)


async def edit(update: Update, context: CustomContext):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.COURSES}/(\d+)/(CLS_GROUP)/(\d+)/{constants.EDIT}/{NUMBER}$`
    """
    query = update.callback_query
    await query.answer()

    context.chat_data["url"] = context.match.group()
    _ = context.gettext

    message = _("Type number")
    await query.message.reply_text(
        message,
    )

    return f"{constants.EDIT} {constants.NUMBER}"


@session
async def receive(update: Update, context: CustomContext, session: Session):
    material_number = int(context.match.groups()[0])

    url = context.chat_data.get("url")
    match: re.Match[str] | None = re.search(
        f"/(?P<material_type>{TYPES})/(?P<material_id>\d+)"
        f"/{constants.EDIT}/{constants.NUMBER}$",
        url,
    )

    material_id = int(match.group("material_id"))
    material = session.get(Material, material_id)
    _ = context.gettext

    if isinstance(material, HasNumber):
        material.number = material_number

        keyboard = [
            [
                context.buttons.back(
                    url,
                    pattern=rf"/{constants.EDIT}.*$",
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = _("Success! {} updated").format(_("Number"))
        await update.message.reply_text(message, reply_markup=reply_markup)

        return constants.ONE
    return None
