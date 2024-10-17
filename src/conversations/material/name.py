import re

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update

from src import constants
from src.customcontext import CustomContext
from src.models import Review
from src.models.material import get_material_class
from src.utils import session

TYPES = Review.__mapper_args__.get("polymorphic_identity")


@session
async def receive(update: Update, context: CustomContext, session: Session):
    data = context.chat_data[f"{constants.ADD} {constants.NAME}"]
    url = data["url"]
    course_id, academic_year_id, material_type = (
        data["course_id"],
        data["year_id"],
        data["material_type"],
    )
    _ = context.gettext
    MaterialClass = get_material_class(material_type)

    _ = context.gettext
    if issubclass(MaterialClass, Review):
        en_name, ar_name = context.match.group("en_name"), context.match.group(
            "ar_name"
        )
        review = Review(
            course_id=course_id,
            academic_year_id=academic_year_id,
            published=False,
            en_name=en_name,
            ar_name=ar_name,
        )
        session.add(review)
        session.flush()

        back_url = re.sub(f"/{constants.ADD}.*", f"/{review.id}", url)
        keyboard = [[context.buttons.back(absolute_url=back_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = _("Success! {} created").format(_(review.type))
        await update.message.reply_text(message, reply_markup=reply_markup)
        return constants.ONE
    return None
