from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from src import buttons, commands, constants, messages, queries
from src.models import RoleName, Status
from src.utils import session, set_my_commands

URLPREFIX = constants.REQUEST_MANAGEMENT_
"""Used as a prefix for all `callback data` in this conversation"""


# ------------------------------- entry_points ---------------------------
@session
async def request_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.ACCESSREQUSTS}/(?P<request_id>\d+)\?action=(?P<action>\w+)$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    request_id = context.match.group("request_id")
    request = queries.access_request(session, access_request_id=request_id)
    action = context.match.group("action")

    # request we deleted in a previous menu
    if request is None:
        return constants.ONE

    if request.status != Status.PENDING:
        return constants.ONE

    user = request.enrollment.user
    if action == Status.GRANTED:
        granted_accessess = [
            e
            for e in user.enrollments
            if e.access_request and e.access_request.status == Status.GRANTED
        ]
        request.status = Status.GRANTED
        await context.bot.send_message(
            user.chat_id,
            (
                "Congratulations 🎉! Now you have access to update materials. "
                "We appreciate your contributions."
            ),
        )
        if len(granted_accessess) == 0:
            user.roles.append(queries.role(session, RoleName.EDITOR))
            await set_my_commands(context.bot, user)
            help_message = messages.help(
                user_roles={role.name for role in user.roles}, new=RoleName.EDITOR
            )
        await context.bot.send_message(
            user.chat_id,
            "Here is your updated list of commands\n"
            f"{'\n'.join(help_message.splitlines()[1:])}",
            parse_mode=ParseMode.HTML,
        )
    if action == Status.REJECTED:
        session.delete(request)
        request.status = Status(action)
    chat = await context.bot.get_chat(request.enrollment.user.chat_id)
    mention = chat.mention_html(chat.full_name or "User")
    message = (
        f"Success! {request.status.capitalize()} "
        f"Editor Access to {mention} for\n\n"
        f"{messages.enrollment_text(enrollment=request.enrollment)}"
    )
    keyboard = [
        [buttons.back(url, f"/{constants.ACCESSREQUSTS}.*", text="to Pending Requests")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    success = await query.delete_message()

    if success:
        await query.message.reply_html(message, reply_markup=reply_markup)
        return constants.ONE

    return None


# -------------------------- states callbacks ---------------------------
@session
async def request(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.ACCESSREQUSTS}/(?P<request_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    request_id = context.match.group("request_id")
    request = queries.access_request(session, request_id)

    if request.status != Status.PENDING:
        return constants.ONE
    chat = await context.bot.get_chat(request.enrollment.user.chat_id)
    mention = chat.mention_html(chat.full_name or "User")
    caption = (
        f"Editor Access re-Request: {mention}\n\n"
        f"{chat.full_name} is requesting editor access for\n"
        f"{messages.enrollment_text(enrollment=request.enrollment)}"
    )
    keyboard = [
        [
            buttons.grant_access(f"{url}?action={Status.GRANTED}"),
            buttons.reject(f"{url}?action={Status.REJECTED}"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_photo(
        photo=request.verification_photo.telegram_id,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )
    return constants.ONE


# ------------------------- ConversationHander -----------------------------

entry_points = [
    CallbackQueryHandler(
        commands.request_list,
        pattern=f"^{URLPREFIX}$",
    ),
    CallbackQueryHandler(
        request_action,
        pattern=f"^{URLPREFIX}/{constants.ACCESSREQUSTS}"
        "/(?P<request_id>\d+)\?action=(?P<action>\w+)$",
    ),
    CallbackQueryHandler(
        request,
        pattern=f"^{URLPREFIX}/{constants.ACCESSREQUSTS}/(?P<request_id>\d+)$",
    ),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            request,
            pattern=f"^{URLPREFIX}/{constants.ACCESSREQUSTS}/(?P<request_id>\d+)$",
        ),
        CallbackQueryHandler(
            request_action,
            pattern=f"^{URLPREFIX}/{constants.ACCESSREQUSTS}/(?P<request_id>\d+)\?action=(?P<action>\w+)$",
        ),
    ]
}

requestmanagement_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.REQUEST_MANAGEMENT_,
    per_message=True,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
