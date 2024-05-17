from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import ContextTypes, TypeHandler

from src import constants, queries
from src.config import Config
from src.models import RoleName, User
from src.utils import session, set_my_commands


@session
async def register_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """This callback will be executed before every handler to make sure
    the user object exists in the database. when it doesn't exit we create it
    and cache it in `user_data`."""
    if context.user_data.get("id") is None:
        telegram_id = update.effective_user.id
        chat_id = update.effective_chat.id
        language_code = update.effective_user.language_code
        user = queries.user(session, telegram_id=telegram_id)
        if not user:
            user = User(
                telegram_id=telegram_id,
                chat_id=chat_id,
                language_code=(
                    language_code
                    if language_code in [constants.EN, constants.AR]
                    else constants.EN
                ),
            )
            session.add(user)
            user.roles.append(queries.role(session, RoleName.USER))
            if telegram_id in Config.ROOTIDS:
                user.roles.append(queries.role(session, RoleName.ROOT))
            session.flush()
        context.user_data["id"] = user.id
        context.user_data["language_code"] = user.language_code
        context.user_data["telegram_id"] = user.telegram_id
        context.chat_data["id"] = user.chat_id

        await set_my_commands(update.get_bot(), user)

    if (user := update.effective_user) and context.user_data.get(
        "full_name"
    ) != user.full_name:
        context.user_data["full_name"] = user.full_name


typehandler = TypeHandler(Update, callback=register_user)
