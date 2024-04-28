import re

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src import buttons, constants, messages
from src.models import Material
from src.utils import session


@session
async def handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session, back
):
    """
    {url_prefix}/{constants.COURSES}/(?P<course_id>\d+)
    /(?P<material_type>{TYPES})/(?P<material_id>\d+)
    /{constants.PUBLISH}(?:\?n=(?P<notify>1|0))?$"
    """
    query = update.callback_query

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.PUBLISH}", context.match.group()).group()

    notify = context.match.group("notify")
    material_id = context.match.group("material_id")
    material_obj = session.get(Material, material_id)

    if material_obj.published:
        await query.answer(
            messages.material_title_text(context.match, material_obj)
            + " is already published."
        )
        return constants.ONE
    if url.startswith(constants.CONETENT_MANAGEMENT_):
        material_obj.published = True
        await query.answer(
            f"Success! {messages.material_title_text(context.match, material_obj)}"
            " published."
        )
        return await back.__wrapped__(update, context, session)

    if notify is None:
        await query.answer()

    if notify is None:
        keyboard = [
            [
                buttons.with_notification(url),
                buttons.without_notification(url),
            ],
            [buttons.back(url, pattern=rf"/{constants.PUBLISH}")],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            # messages.enrollment_text(context.match, session)
            # + "\n"
            messages.title(context.match, session)
            + "\n"
            + messages.course_text(context.match, session)
            + messages.material_message_text(context.match, session)
            + "\n Would you like to publish"
            + f" {messages.material_title_text(context.match, material_obj)}"
            + " with or without notifications?"
        )

        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    elif notify == "0":
        material_obj.published = True
        session.flush()
        await query.answer(
            f"Success! {messages.material_title_text(context.match, material_obj)}"
            " published. Not sending notifications."
        )
        return await back.__wrapped__(update, context, session)
    elif notify == "1":
        # TODO handle publishing logic
        pass
    return None
