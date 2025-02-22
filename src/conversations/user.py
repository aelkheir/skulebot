"""Contains callbacks and handlers for the /users conversaion"""

import contextlib
import re
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from telegram import (
    CallbackQuery,
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import constants, messages, queries
from src.constants import COMMANDS
from src.conversations.material import files
from src.customcontext import CustomContext
from src.models import RoleName
from src.models.access_request import AccessRequest, Status
from src.models.enrollment import Enrollment
from src.models.file import File
from src.models.user import User
from src.utils import Pager, build_menu, roles, session, set_my_commands

URLPREFIX = constants.USER_
"""used as a prefix for all `callback data` in this conversation"""

DATA_KEY = constants.USER_
"""used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


def user_header_info(user: User, gettext) -> str:
    user_data = user.user_data.data
    _ = gettext

    message = _("Full name") + f": {user_data.get('full_name')}"
    message += (
        ("\n" + _("Username") + f": @{username}")
        if (username := user_data.get("username"))
        else ""
    )
    message += "\n" + _("Telegram id") + f": {user.telegram_id}"
    return message


# ------------------------------- entry_points ---------------------------
@roles(RoleName.ROOT)
@session
async def user_list(
    update: Update,
    context: CustomContext,
    session: Session,
    search_query: Optional[str] = None,
):
    """Runs with messages.test `'/users'` or on callback_data
    `^{URLPREFIX}/{constants.USERS}
    (?:\?(p=(?P<page>\d+))?(?:&)?(?:q=(?P<query>\w+))?)?
    (?:/{constants.IGNORE})?$`
    """

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    url = f"{URLPREFIX}/{constants.USERS}"

    offset = 0
    if context.match:
        if context.match.group().endswith(constants.IGNORE):
            return constants.ONE

        offset = int(page) if (page := context.match.group("page")) else 0
        if search_query is None:
            search_query = context.match.group("query") or None
    users = queries.users(session, query=search_query)

    pager = Pager[User](users, offset, 30)

    user_button_list = await context.buttons.user_list(
        pager.items,
        url,
        context=context,
        end=f"?q={search_query}" if search_query else None,
    )
    keyboard = build_menu(
        user_button_list,
        3,
        reverse=context.language_code == constants.AR,
    )
    if pager.has_next or pager.has_previous:
        pager_keyboard = []
        keyboard.append(pager_keyboard)
        search_param = f"&q={search_query}" if search_query else ""
        if pager.has_previous:
            pager_keyboard.append(
                context.buttons.previous_page(
                    f"{url}?p={pager.previous_offset}{search_param}"
                )
            )
        pager_keyboard.append(
            context.buttons.current_page(
                pager.current_page, pager.number_of_pages, f"{url}/{constants.IGNORE}"
            )
        )
        if pager.has_next:
            pager_keyboard.append(
                context.buttons.next_page(f"{url}?p={pager.next_offset}{search_param}")
            )
        if context.language_code == constants.AR:
            pager_keyboard.reverse()

    if search_query is None:
        keyboard += [[context.buttons.search(f"{url}/{constants.SEARCH}")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    _ = context.gettext
    message = _("Results") if search_query is not None else _("Users")
    message += f" [{len(users)}]"

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------
@session
async def user(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)(?:\?q=(?P<query>\w+))?$`"""

    query = update.callback_query
    await query.answer()

    search_query = context.match.group("query")
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    _ = context.gettext

    search_param = ("?q=" + search_query) if search_query else ""
    keyboard = [
        [
            InlineKeyboardButton(
                _("Broadcast"),
                callback_data=f"{URLPREFIX}/{constants.USERS}/{user_id}/{constants.BROADCAST_}",
            ),
            InlineKeyboardButton(
                _("Enrollments"),
                callback_data=f"{URLPREFIX}/{constants.USERS}/{user_id}/{constants.ENROLLMENTS}",
            ),
        ],
        [
            context.buttons.back(
                absolute_url=f"{URLPREFIX}/{constants.USERS}{search_param}"
            ),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = user_header_info(user, context.gettext)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


async def send(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/\d+/{constants.BROADCAST_}$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url
    _ = context.gettext

    message = _("Type message")
    await query.message.reply_text(
        message,
    )

    return constants.BROADCAST_


@session
async def receive_message(update: Update, context: CustomContext, session: Session):
    """Runs on `Message.text` matching filters.ALL"""

    url = context.chat_data[DATA_KEY]["url"]
    context.chat_data.setdefault(DATA_KEY, {})["message_id"] = update.message.id

    _ = context.gettext
    keyboard = build_menu(
        [
            InlineKeyboardButton(
                _("Send"),
                callback_data=f"{url}?o=send",
            ),
            InlineKeyboardButton(_("Preview"), callback_data=f"{url}?o=preview"),
        ],
        2,
    )
    _ = context.gettext
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = _("Select action")
    await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


@session
async def action(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    ^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.BROADCAST_}?o=(?P<option>\w+)
    """

    query = update.callback_query
    await query.answer()

    option = context.match.group("option")
    message_id = context.chat_data[DATA_KEY]["message_id"]
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id)

    if option == "preview":
        await context.bot.copy_message(
            update.effective_chat.id,
            from_chat_id=update.effective_chat.id,
            message_id=message_id,
        )
        return

    success = await query.delete_message()
    if success:
        with contextlib.suppress(Forbidden):
            message = await context.bot.copy_message(
                user.chat_id,
                from_chat_id=update.effective_chat.id,
                message_id=message_id,
            )

            if message:
                await context.bot.send_message(
                    update.effective_chat.id,
                    text=context.gettext("Done broadcasting message"),
                )
                await set_my_commands(context.bot, user)


async def search(update: Update, context: CustomContext):
    """Runs on callback_data `^{URLPREFIX}/{constants.USERS}/{constants.SEARCH}$`"""

    query = update.callback_query
    await query.answer()

    _ = context.gettext
    message = _("Search users")
    await query.message.reply_text(
        message,
    )

    return constants.SEARCH


@session
async def receive_search(update: Update, context: CustomContext, session: Session):
    """Runs on `Message.text` matching ^(\d+)$"""

    search_query = update.message.text
    return await user_list.__wrapped__.__wrapped__(
        update, context, session, search_query
    )


@session
async def enrollments(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/\d+/{constants.ENROLLMENTS}$`"""

    query = update.callback_query
    await query.answer()

    _ = context.gettext
    # url here is calculated because this handler reenter with
    # from another callback: enrollments_add
    url = re.search(rf".*/{constants.ENROLLMENTS}", context.match.group()).group()
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    enrollments = queries.user_enrollments(session, user_id)
    years = queries.academic_years(session)
    can_add_enrollment = {y.id for y in years} != {
        e.academic_year.id for e in enrollments
    }
    menu = context.buttons.enrollments_list(enrollments, url)
    menu += [context.buttons.add(url, _("Enrollment"))] if can_add_enrollment else []
    keyboard = build_menu(
        menu,
        1,
        footer_buttons=context.buttons.back(url, pattern=f"/{constants.ENROLLMENTS}$"),
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = user_header_info(user, context.gettext)
    message += "\n\n" + "\n".join(
        [
            "- " + messages.enrollment_text(enrollment=e, context=context)
            for e in enrollments
        ]
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return constants.ONE


@session
async def enrollment(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/\d+/{constants.ENROLLMENTS}$`"""

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with
    # from another callback: receive_id_file
    url = re.search(rf".*/{constants.ENROLLMENTS}/\d+", context.match.group()).group()
    _ = context.gettext
    enrollment_id = context.match.group("enrollment_id")
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    enrollment = queries.enrollment(session, enrollment_id)
    has_access = bool(enrollment.access_request)

    menu = (
        [context.buttons.grant_access(f"{url}/{constants.ADD}")]
        if not has_access
        else (
            [context.buttons.revoke(url)]
            + (
                [context.buttons.display(f"{url}/{constants.FILES}/{photo.id}")]
                if (photo := enrollment.access_request.verification_photo)
                else []
            )
        )
    )

    keyboard = build_menu(
        menu,
        2,
        header_buttons=context.buttons.delete(url, text=_("Enrollment")),
        footer_buttons=context.buttons.back(url, pattern="/\d+$"),
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = user_header_info(user, context.gettext)
    message += (
        "\n\n" + "- " + messages.enrollment_text(enrollment=enrollment, context=context)
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def revoke_access(update: Update, context: CustomContext, session: Session):
    """Runs with callback_data
    `^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}
    /{constants.REVOKE}(?:\?c=(?P<has_confirmed>1|0))?$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.REVOKE}", context.match.group()).group()

    _ = context.gettext
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    enrollment_id = int(context.match.group("enrollment_id"))
    enrollment = queries.enrollment(session, enrollment_id)
    year = enrollment.academic_year
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: list
    message = user_header_info(user, context.gettext) + "\n\n"

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message += (
            _("Revoke {}")
            .format(messages.bold(_("Access for year {}")))
            .format(f"{year.start} - {year.end}")
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message += (
            _("Confirm revoke {}")
            .format(messages.bold(_("Access for year {}")))
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
                url, text=_("Enrollments"), pattern=rf"/{constants.REVOKE}.*"
            )
        ]
        message += (
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


@session
async def access_add(update: Update, context: CustomContext, session: Session) -> None:
    """Runs on callback_data
    `^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
    f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.ADD}$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)

    keyboard = []
    enrollment_text = messages.enrollment_text(context.match, session, context=context)
    _ = context.gettext

    message = (
        user_header_info(user, context.gettext)
        + "\n\n"
        + enrollment_text
        + "\n"
        + _("Select action")
    )
    keyboard = [
        [
            context.buttons.submit_proof(url=f"{url}/{constants.ID}"),
            context.buttons.grant_access(url=f"{url}/{constants.CONFIRM}"),
        ],
    ]
    keyboard += [[context.buttons.back(url, f"/{constants.ADD}$")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def grant_no_id(update: Update, context: CustomContext, session: Session) -> None:
    """Run on callback_data
    `^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
    /{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)
    /{constants.ADD}/{constants.CONFIRM}$`
    """

    query = update.callback_query
    await query.answer()

    enrollment_id = context.match.group("enrollment_id")
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id)

    enrollment_obj = queries.enrollment(session, enrollment_id)
    if enrollment_obj.access_request:
        message = context.gettext("Already applied for access")
        await query.message.reply_text(message)
        return constants.ONE

    request = AccessRequest(
        status=Status.GRANTED,
        enrollment=enrollment_obj,
    )

    session.add(request)
    session.flush()

    user_context = CustomContext(context.application, user.chat_id, user.telegram_id)
    user_gettext = user_context.gettext

    await context.bot.send_message(
        user.chat_id,
        user_gettext("Congratulations! New access"),
    )
    await context.bot.send_message(
        user.chat_id,
        user_gettext("publish-guide"),
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(
            url=constants.PUBLISH_GUIDE_URL,
            prefer_small_media=True,
            show_above_text=True,
        ),
    )
    if queries.role(session, RoleName.EDITOR) not in user.roles:
        user.roles.append(queries.role(session, RoleName.EDITOR))
        await set_my_commands(context.bot, user)
        help_message = messages.help(
            user_roles={role.name for role in user.roles},
            language_code=user.language_code,
            new=RoleName.EDITOR,
        )
        await context.bot.send_message(
            user.chat_id,
            user_gettext("Your commands have been Updated")
            + "\n"
            + f"{'\n'.join(help_message.splitlines()[1:])}",
            parse_mode=ParseMode.HTML,
        )

    return await enrollment.__wrapped__(update, context, session)


@session
async def send_id(update: Update, context: CustomContext, session: Session) -> None:
    """Run on callback_data
    `^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
    /{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)
    /{constants.ADD}/{constants.ID}$`
    """

    query = update.callback_query
    await query.answer()

    enrollment_id = context.match.group("enrollment_id")

    enrollment = queries.enrollment(session, enrollment_id)
    if enrollment.access_request:
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
        f"/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)",
        url,
    )
    _ = context.gettext
    message = update.message
    user_id = int(match.group("user_id"))
    user = queries.user(session, user_id)
    attachment = message.effective_attachment
    file_id = (
        attachment.file_id
        if isinstance(attachment, Document)
        else message.photo[-1].file_id
    )
    enrollment_id = int(match.group("enrollment_id"))
    enrollment_obj = queries.enrollment(session, enrollment_id)

    request = AccessRequest(
        status=Status.GRANTED,
        enrollment=enrollment_obj,
        verification_photo=File(
            telegram_id=file_id,
            name=user.user_data.data.get("full_name") + "_verification",
            type="document" if isinstance(attachment, Document) else "photo",
            uploader=queries.user(session, context.user_data["id"]),
        ),
    )
    session.add(request)
    session.flush()

    user_context = CustomContext(context.application, user.chat_id, user.telegram_id)
    user_gettext = user_context.gettext

    await context.bot.send_message(
        user.chat_id,
        user_gettext("Congratulations! New access"),
    )
    await context.bot.send_message(
        user.chat_id,
        user_gettext("publish-guide"),
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(
            url=constants.PUBLISH_GUIDE_URL,
            prefer_small_media=True,
            show_above_text=True,
        ),
    )
    if queries.role(session, RoleName.EDITOR) not in user.roles:
        user.roles.append(queries.role(session, RoleName.EDITOR))
        await set_my_commands(context.bot, user)
        help_message = messages.help(
            user_roles={role.name for role in user.roles},
            language_code=user.language_code,
            new=RoleName.EDITOR,
        )
        await context.bot.send_message(
            user.chat_id,
            user_gettext("Your commands have been Updated")
            + "\n"
            + f"{'\n'.join(help_message.splitlines()[1:])}",
            parse_mode=ParseMode.HTML,
        )
    keyboard = build_menu([context.buttons.back(url, f"/{constants.ADD}.*")], 1)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_html(_("Success!"), reply_markup=reply_markup)

    return constants.ONE


@session
async def enrollment_delete(update: Update, context: CustomContext, session: Session):
    """runs on ^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}
    /(?P<enrollment_id>\d+)/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$"""

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    _ = context.gettext
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    enrollment_id = context.match.group("enrollment_id")
    enrollment = queries.enrollment(session, enrollment_id)
    year = enrollment.academic_year
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: list
    message = user_header_info(user, context.gettext) + "\n\n"

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message += _("Delete warning {}").format(
            messages.bold(_("Enrollment {} - {}").format(year.start, year.end))
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message += _("Confirm delete warning {}").format(
            messages.bold(_("Enrollment {} - {}").format(year.start, year.end))
        )
    elif has_confirmed == "1":
        user = enrollment.user
        session.delete(enrollment)
        granted_accessess = [
            e
            for e in user.enrollments
            if e.access_request and e.access_request.status == Status.GRANTED
        ]
        if len(granted_accessess) == 0 and RoleName.EDITOR in [
            r.name for r in user.roles
        ]:
            user.roles.remove(queries.role(session, RoleName.EDITOR))
            await set_my_commands(context.bot, user)
        if len(user.enrollments) == 0:
            user.roles.remove(queries.role(session, RoleName.STUDENT))
            await set_my_commands(context.bot, user)
        menu_buttons = [
            context.buttons.back(
                url, text=_("Enrollments"), pattern=rf"/\d+/{constants.DELETE}.*"
            )
        ]
        message += (
            _("Success! {} deleted")
            .format(_("Enrollment {} - {}"))
            .format(year.start, year.end)
        )

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def enrollments_add(
    update: Update, context: CustomContext, session: Session
) -> None:
    """Runs on callback_data
    pattern=^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}/{constants.ADD}
    \?year_id=(?P<y_id>\d+)
    (?:&program_id=(?P<p_id>\d+))?(?:&program_semester_id=(?P<p_s_id>\d+))?$
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    user_id = context.match.group("user_id")
    user = queries.user(session, user_id=user_id)
    enrollments_list = user.enrollments
    enrolled_years = [e.academic_year_id for e in enrollments_list]

    year_id, program_id, program_semester_id = (
        int(y) if (y := context.match.group("y_id")) else None,
        int(y) if (y := context.match.group("p_id")) else None,
        int(y) if (y := context.match.group("p_s_id")) else None,
    )

    message: str
    _ = context.gettext

    if year_id is None:
        message = _("Select {}").format(_("Year"))
        years = queries.academic_years(session)
        available_years = [y for y in years if y.id not in enrolled_years]
        menu = build_menu(
            context.buttons.years_list(available_years, url, sep="?year_id="),
            1,
            footer_buttons=context.buttons.back(url, f"/{constants.ADD}.*"),
        )
        reply_markup = InlineKeyboardMarkup(menu)

        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
        return constants.ONE
    if program_id is None:
        message = _("Select {}").format(_("Program"))
        programs = queries.programs(session)
        menu = build_menu(
            context.buttons.programs_list(programs, url, sep="&program_id="),
            1,
            footer_buttons=context.buttons.back(url, "\?year_id.*"),
        )
        reply_markup = InlineKeyboardMarkup(menu)

        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
        return constants.ONE
    if program_semester_id is None:
        message = _("Select {}").format(_("Level"))
        program_semesters = queries.program_semesters(session, program_id)
        menu = build_menu(
            context.buttons.program_levels_list(
                program_semesters, url, sep="&program_semester_id="
            ),
            1,
            footer_buttons=context.buttons.back(url, "&program_id.*"),
        )
        reply_markup = InlineKeyboardMarkup(menu)

        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
        return constants.ONE
    program_semester = queries.program_semester(
        session, program_semester_id=program_semester_id
    )
    enrollment_obj = Enrollment(
        user_id=user_id,
        academic_year_id=year_id,
        program_semester_id=program_semester.id,
    )

    async def proceed_enrollment():
        user.enrollments.append(enrollment_obj)
        is_only_enrollment = len(user.enrollments) == 1
        session.flush()
        user_context = CustomContext(
            context.application, user.chat_id, user.telegram_id
        )
        user_gettext = user_context.gettext
        await context.bot.send_message(
            user.chat_id,
            user_gettext("You have been enrolled")
            + "\n\n"
            + messages.enrollment_text(
                enrollment=enrollment_obj,
                context=user_context,
            ),
            parse_mode=ParseMode.HTML,
        )
        if is_only_enrollment:
            user.roles.append(queries.role(session, RoleName.STUDENT))
            await set_my_commands(context.bot, user)
            help_message = messages.help(
                user_roles={role.name for role in user.roles},
                language_code=user_context.language_code,
                new=RoleName.STUDENT,
            )
            await context.bot.send_message(
                user.chat_id,
                user_gettext("Your commands have been Updated")
                + "\n"
                + f"{'\n'.join(help_message.splitlines()[1:])}",
                parse_mode=ParseMode.HTML,
            )

    try:
        await proceed_enrollment()
    # enrollment creation has faild because user alread enrolled from another message
    except IntegrityError:
        await query.message.reply_html(_("Already enrolled"))
    return await enrollments.__wrapped__(update, context, session)


# ------------------------- ConversationHander -----------------------------

cmd = COMMANDS
entry_points = [
    CommandHandler(cmd.users.command, user_list),
    CallbackQueryHandler(
        user_list,
        pattern=f"^{URLPREFIX}/{constants.USERS}"
        f"(?:\?(p=(?P<page>\d+))?(?:&)?(?:q=(?P<query>\w+))?)?(?:/{constants.IGNORE})?$",
    ),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            search, pattern=f"^{URLPREFIX}/{constants.USERS}/{constants.SEARCH}$"
        ),
        CallbackQueryHandler(
            user,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)(?:\?q=(?P<query>\w+))?$",
        ),
        CallbackQueryHandler(
            send,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.BROADCAST_}$",
        ),
        CallbackQueryHandler(
            enrollments,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}$",
        ),
        CallbackQueryHandler(
            enrollments_add,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}/{constants.ADD}"
            "(?:\?year_id=(?P<y_id>\d+))?"
            "(?:&program_id=(?P<p_id>\d+))?(?:&program_semester_id=(?P<p_s_id>\d+))?$",
        ),
        CallbackQueryHandler(
            enrollment,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)$",
        ),
        CallbackQueryHandler(
            access_add,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.ADD}$",
        ),
        CallbackQueryHandler(
            send_id,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.ADD}/{constants.ID}$",
        ),
        CallbackQueryHandler(
            grant_no_id,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)/{constants.ADD}/{constants.CONFIRM}$",
        ),
        CallbackQueryHandler(
            revoke_access,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}"
            f"/(?P<enrollment_id>\d+)/{constants.REVOKE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
        CallbackQueryHandler(
            enrollment_delete,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)/{constants.ENROLLMENTS}"
            f"/(?P<enrollment_id>\d+)/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
        CallbackQueryHandler(
            files.display,
            f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
            f"/{constants.FILES}/(?P<file_id>\d+)/{constants.DISPLAY}$",
        ),
        CallbackQueryHandler(
            action,
            pattern=f"^{URLPREFIX}/{constants.USERS}/(?P<user_id>\d+)"
            f"/{constants.BROADCAST_}\?o=(?P<option>\w+)$",
        ),
    ]
}
states.update(
    {
        constants.SEARCH: states[constants.ONE]
        + [
            MessageHandler(filters.TEXT, receive_search),
        ]
    }
)

states.update(
    {
        constants.ADD: states[constants.ONE]
        + [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_id_file)]
    }
)

states.update(
    {
        constants.BROADCAST_: states[constants.ONE]
        + [
            MessageHandler(filters.ALL, receive_message),
        ]
    }
)

user_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.USER_,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
