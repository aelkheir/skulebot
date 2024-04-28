"""Contains callbacks and handlers for the /settings conversaion"""

import re
from typing import List

from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from src import buttons, commands, constants, messages, queries
from src.models import SettingKey
from src.utils import build_menu, get_setting_value, session, set_setting_value

# ------------------------- Callbacks -----------------------------

URLPREFIX = constants.SETTINGS_


# helperes
def first_list_level(text: str):
    return f"└── <b>{text}</b>"


@session
async def language(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
) -> None:
    "Runs on `^{URLPREFIX}/{LANGUAGE}$`"

    query = update.callback_query

    url = f"{URLPREFIX}/{constants.LANGUAGE}"
    lang_code = queries.user(session, context.user_data["id"]).language_code

    menu = [
        buttons.arabic(
            f"{url}/{constants.EDIT}?lang={constants.AR}",
            selected=lang_code == constants.AR,
        ),
        buttons.english(
            f"{url}/{constants.EDIT}?lang={constants.EN}",
            selected=lang_code == constants.EN,
        ),
    ]
    keyboard = build_menu(
        menu,
        2,
        footer_buttons=buttons.back(url, f"/{constants.LANGUAGE}"),
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = messages.bot_settings() + first_list_level("🌍 Language")
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


@session
async def edit_language(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
) -> None:
    """Runs on callback_data
    `^{URLPREFIX}/{constants.LANGUAGE}/{constants.EDIT}
    (?:\?lang=(?P<lang>{constants.AR}|{constants.EN}))?$`"""

    query = update.callback_query

    new_lang_code = context.match.group("lang")
    user = queries.user(session, context.user_data["id"])
    old_lang_code = user.language_code

    if new_lang_code == old_lang_code:
        await query.answer(messages.success_updated("Language"))
        return constants.ONE
    user.language_code = new_lang_code
    session.flush()
    context.user_data["language_code"] = user.language_code
    await query.answer(messages.success_updated("Language"))

    return await language.__wrapped__(update, context, session)


@session
async def notifications(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
) -> None:
    "Runs on callback_data `^{URLPREFIX}/{NOTIFICATIONS}$`"
    query = update.callback_query

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.NOTIFICATIONS}", context.match.group()).group()

    menu: List = []
    for notification_setting in SettingKey.get_notification_keys():
        value = get_setting_value(
            session, context.user_data["id"], notification_setting
        )
        menu.append(
            buttons.notification_setting_item(
                notification_setting,
                f"{url}/{constants.EDIT}?{notification_setting.name}={int(not value)}",
                selected=bool(value),
            )
        )
    keyboard = build_menu(
        menu,
        3,
        header_buttons=buttons.disable_all(f"{url}/{constants.EDIT}?all=0"),
        footer_buttons=buttons.back(url, f"/{constants.NOTIFICATIONS}"),
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = messages.bot_settings() + first_list_level("🔔 Notifications")
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


@session
async def edit_notification(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
) -> None:
    "runs on ^{URLPREFIX}/{LANGUAGE}/{EDIT}(?:\?lang=(?P<lang>{AR}|{EN}))?$"
    query = update.callback_query

    # the SettingKey mamber name, or 'all' in case of Disable All was pressed
    name = context.match.group("name")

    if name == "all":
        updated = False
        for setting in SettingKey.get_notification_keys():
            value = get_setting_value(session, context.user_data["id"], setting)
            if value:
                set_setting_value(session, context.user_data["id"], setting, False)
                updated = True
        if not updated:
            await query.answer("Done! All notifications are turned Off")
            return constants.ONE
        await query.answer("Done! All notifications are turned Off")
        return await notifications.__wrapped__(update, context, session)

    new_value = bool(int(context.match.group("value")))
    setting_member = SettingKey[name]
    old_value = get_setting_value(session, context.user_data["id"], setting_member)
    if new_value == old_value:
        await query.answer(
            messages.success_updated(f"{name.capitalize()} notifications")
        )
        return await notifications.__wrapped__(update, context, session)
    setting = set_setting_value(
        session, context.user_data["id"], setting_member, new_value
    )
    await query.answer(messages.success_updated(f"{name.capitalize()} notifications"))
    return await notifications.__wrapped__(update, context, session)


# ------------------------- ConversationHander -----------------------------

settings_ = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            language,
            pattern=f"^{URLPREFIX}/{constants.LANGUAGE}$",
        ),
        CallbackQueryHandler(
            notifications,
            pattern=f"^{URLPREFIX}/{constants.NOTIFICATIONS}$",
        ),
    ],
    states={
        constants.ONE: [
            CallbackQueryHandler(
                edit_language,
                pattern=f"^{URLPREFIX}/{constants.LANGUAGE}"
                f"/{constants.EDIT}(?:\?lang=(?P<lang>{constants.AR}|{constants.EN}))?$",
            ),
            CallbackQueryHandler(
                edit_notification,
                pattern=f"^{URLPREFIX}/{constants.NOTIFICATIONS}"
                f"/{constants.EDIT}(?:\?(?P<name>\w+)=(?P<value>0|1))?$",
            ),
            CallbackQueryHandler(commands.settings, pattern=f"^{URLPREFIX}$"),
        ]
    },
    fallbacks=[],
    name=constants.SETTINGS_,
    per_message=True,
    per_user=True,
    per_chat=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
