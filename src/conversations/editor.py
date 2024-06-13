"""Contains callbacks and handlers for the /editorship conversaion"""

import re

from sqlalchemy.orm import Session
from telegram import CallbackQuery, Document, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import constants, messages, queries
from src.config import Config
from src.conversations.updatematerial import updatematerials_
from src.customcontext import CustomContext
from src.messages import bold, underline
from src.models import AccessRequest, Course, File, RoleName, Status
from src.utils import build_menu, roles, session, set_my_commands

# ------------------------- Callbacks -----------------------------

URLPREFIX = constants.EDITOR_
"""Used as a prefix for all `callback_data` s in this conversation module"""

DATA_KEY = constants.EDITOR_
"""Used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


@roles(RoleName.STUDENT)
@session
async def list_accesses(
    update: Update, context: CustomContext, session: Session
) -> None:
    """Runs with Message.text `/editor`"""

    query: None | CallbackQuery = None
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    user = queries.user(session, context.user_data["id"])
    message: str
    keyboard = []
    _ = context.gettext

    if len(user.enrollments) == 0:
        return None
    message = underline(_("Editor Access"))
    requests = queries.user_access_requests(
        session,
        user_id=context.user_data["id"],
        status=[
            Status.GRANTED,
            Status.PENDING,
        ],
    )
    buttons_list = context.buttons.access_requests_list(
        access_requests=requests, url=f"{URLPREFIX}/{constants.ENROLLMENTS}"
    )
    most_recent_enrollment = queries.user_most_recent_enrollment(
        session, user_id=context.user_data["id"]
    )
    if most_recent_enrollment not in [r.enrollment for r in requests]:
        buttons_list.insert(
            0,
            context.buttons.new_access_request(
                most_recent_enrollment,
                url=f"{URLPREFIX}/{constants.ENROLLMENTS}"
                f"/{most_recent_enrollment.id}/{constants.ADD}",
            ),
        )
    keyboard = build_menu(buttons_list, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_html(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def access_add(update: Update, context: CustomContext, session: Session) -> None:
    """Runs on callback_data
    `^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.ADD}$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    keyboard = []
    enrollment_text = messages.enrollment_text(context.match, session, context=context)
    _ = context.gettext

    message = enrollment_text + "\n" + _("How editing works")
    keyboard = [
        [
            context.buttons.submit_proof(url=f"{url}/{constants.ID}"),
            context.buttons.contact(
                url="https://t.me/skulebotsupport"
                "?text=" + _("No id intro message {}").format(enrollment_text)
            ),
        ],
    ]
    keyboard += [[context.buttons.back(url, f"/{constants.ENROLLMENTS}.*")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def send_id(update: Update, context: CustomContext, session: Session) -> None:
    """Run on callback_data
    `^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)
    /{constants.ADD}/{constants.ID}$`
    """

    query = update.callback_query
    await query.answer()

    most_recent_enrollment = queries.user_most_recent_enrollment(
        session, user_id=context.user_data["id"]
    )
    if most_recent_enrollment.access_request:
        message = context.gettext("Already applied for access")
        await query.message.reply_text(message)
        return constants.ONE

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url
    message = context.gettext("Send me your proof")
    await query.message.reply_text(message)
    return constants.ADD


@session
async def receive_id_file(update: Update, context: CustomContext, session: Session):
    """Runs with Message.photo"""

    url = context.chat_data[DATA_KEY]["url"]

    match: re.Match[str] | None = re.search(
        f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)", url
    )
    message = update.message
    user = update.effective_user
    attachment = message.effective_attachment
    file_id = (
        attachment.file_id
        if isinstance(attachment, Document)
        else message.photo[-1].file_id
    )
    enrollment_id = int(match.group("enrollment_id"))

    enrollment = queries.enrollment(session, enrollment_id)

    request = AccessRequest(
        status=Status.PENDING,
        enrollment=enrollment,
        verification_photo=File(
            telegram_id=file_id,
            name=user.full_name + "_verification",
            type="document" if isinstance(attachment, Document) else "photo",
            uploader=queries.user(session, context.user_data["id"]),
        ),
    )
    session.add(request)

    _ = context.gettext
    caption = _("Admin call for action {fullname} {mention} {enrollment}").format(
        fullname=user.full_name,
        mention=user.mention_html(),
        enrollment=messages.enrollment_text(enrollment=enrollment, context=context),
    )
    url = f"{constants.REQUEST_MANAGEMENT_}/{constants.ACCESSREQUSTS}/{request.id}"
    keyboard = [
        [
            context.buttons.grant_access(f"{url}?action={Status.GRANTED.value}"),
            context.buttons.reject(f"{url}?action={Status.REJECTED.value}"),
        ],
        [context.buttons.contact(url=f"tg://user?id={user.id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    sender = (
        context.bot.send_document
        if isinstance(attachment, Document)
        else (context.bot.send_photo)
    )
    for id_ in Config.ROOTIDS:
        await sender(
            id_,
            file_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )

    message = _("Thanks for applying {}").format(constants.COMMANDS.editor1.command)
    await update.message.reply_text(message)
    return constants.ONE


@session
async def access(update: Update, context: CustomContext, session: Session) -> None:
    """Runs on callback_data
    `^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)
    (/{constants.EDIT}\?program_semester_id=(?P<edit_p_s_id>\d+))?(/{constants.COURSES})?$`
    """

    query = update.callback_query
    await query.answer()

    # path is recalculated becase of uery params
    url = re.search(rf".*/{constants.ENROLLMENTS}/\d+", context.match.group()).group()
    enrollment_id = int(context.match.group("enrollment_id"))
    enrollment = queries.enrollment(session, enrollment_id)
    request = enrollment.access_request
    _ = context.gettext

    if request is None:
        await update.effective_message.delete()
        return None

    if request.status == Status.PENDING:
        message = messages.enrollment_text(enrollment=enrollment, context=context)
        message += "\n\n" + _("Your request is pending")
        keyboard = [[context.buttons.back(url, f"/{constants.ENROLLMENTS}.*")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
        return constants.ONE

    if request.status != Status.GRANTED:
        return constants.ONE

    edit_p_s_id = (
        int(y) if (y := context.match.groupdict().get("edit_p_s_id")) else None
    )

    if edit_p_s_id is not None:
        if edit_p_s_id == enrollment.program_semester_id:
            await query.answer()
            return constants.ONE
        enrollment.program_semester = queries.program_semester(
            session, program_semester_id=edit_p_s_id
        )
        session.flush()
        await query.answer()

    user_courses = queries.user_courses(
        session,
        program_id=enrollment.program.id,
        semester_id=enrollment.semester.id,
        user_id=context.user_data["id"],
        sort_attr=(
            Course.ar_name if context.language_code == constants.AR else Course.en_name
        ),
    )
    courses_url = f"{url}/{constants.COURSES}"
    courses_buttons = context.buttons.courses_list(
        user_courses,
        url=courses_url,
    )
    has_optional_courses = queries.has_optional_courses(
        session,
        program_id=enrollment.program.id,
        semester_id=enrollment.semester.id,
    )
    courses_buttons += (
        [context.buttons.optional_courses(f"{courses_url}/{constants.OPTIONAL}")]
        if has_optional_courses
        else []
    )
    level = enrollment.semester.number // 2 + (enrollment.semester.number % 2)
    program_semesters = queries.program_semesters(
        session, enrollment.program.id, level=level
    )
    semester_buttons = context.buttons.program_semesters_list(
        program_semesters,
        url,
        selected_ids=enrollment.program_semester.id,
        sep=f"/{constants.EDIT}?program_semester_id=",
    )
    keyboard = build_menu(
        courses_buttons,
        1,
        header_buttons=semester_buttons,
        footer_buttons=[
            context.buttons.back(url, f"/{constants.ENROLLMENTS}.*"),
            context.buttons.revoke(url),
        ],
        reverse=context.language_code == constants.AR,
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        underline(_("Editor Access"))
        + "\n\n"
        + messages.enrollment_text(enrollment=request.enrollment, context=context)
    )

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


@session
async def revoke_access(update: Update, context: CustomContext, session: Session):
    """Runs with callback_data
    `^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)
    /{constants.REVOKE}(?:\?c=(?P<has_confirmed>1|0))?$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.REVOKE}", context.match.group()).group()

    enrollment_id = int(context.match.group("enrollment_id"))
    enrollment = queries.enrollment(session, enrollment_id)
    year = enrollment.academic_year
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: list
    message: str
    _ = context.gettext

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message = (
            _("Revoke {}")
            .format(bold(_("Access for year {}")))
            .format(f"{year.start} - {year.end}")
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message = (
            _("Confirm revoke {}")
            .format(bold(_("Access for year {}")))
            .format(f"{year.start} - {year.end}")
        )
    elif has_confirmed == "1":
        del enrollment.access_request
        session.flush()
        user = enrollment.user
        has_granted_accessess = len(
            [
                e
                for e in user.enrollments
                if e.access_request
                and enrollment.access_request.status == Status.GRANTED
            ]
        )
        if not has_granted_accessess:
            user.roles.remove(queries.role(session, role_name=RoleName.EDITOR))
            await set_my_commands(context.bot, user)
        menu_buttons = [
            context.buttons.back(
                url, text=_("Editor Access"), pattern=rf"/{constants.ENROLLMENTS}.*"
            )
        ]
        message = (
            _("Success! {} revoked")
            .format(_("Access for year {}"))
            .format(f"{year.start} - {year.end}")
        )

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


# ------------------------- ConversationHander -----------------------------

cmd = constants.COMMANDS
entry_points = [
    CommandHandler(cmd.editor1.command, list_accesses),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            access,
            pattern=f"^{URLPREFIX}"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
            f"(/{constants.EDIT}\?program_semester_id=(?P<edit_p_s_id>\d+))?(/{constants.COURSES})?$",
        ),
        CallbackQueryHandler(
            access_add,
            pattern=f"^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.ADD}$",
        ),
        CallbackQueryHandler(
            send_id,
            pattern=f"^{URLPREFIX}/{constants.ENROLLMENTS}"
            f"/(?P<enrollment_id>\d+)/{constants.ADD}/{constants.ID}$",
        ),
        CallbackQueryHandler(
            revoke_access,
            pattern=f"^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
            f"/{constants.REVOKE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
        CallbackQueryHandler(list_accesses, pattern=f"^{URLPREFIX}$"),
        updatematerials_,
    ]
}
states.update(
    {
        constants.ADD: states[constants.ONE]
        + [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_id_file)]
    }
)

editor_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.EDITOR_,
    per_user=True,
    per_chat=True,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
