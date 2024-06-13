"""Contains callbacks and handlers for the /enrollments conversaion"""

import re
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ConversationHandler

from src import commands, constants, messages, queries
from src.conversations.course import usercourses_
from src.customcontext import CustomContext
from src.messages import bold
from src.models import Course, Enrollment, RoleName, Status
from src.utils import build_menu, session, set_my_commands

# ------------------------- Callbacks -----------------------------

URLPREFIX = constants.ENROLLMENT_
"""Used as a prefix for all `callback_data` s in this conversation module"""


@session
async def enrollments_add(
    update: Update, context: CustomContext, session: Session
) -> None:
    """Runs on callback_data
    ^{URLPREFIX}/{constants.ENROLLMENTS}/{constants.ADD}
    \?year_id=(?P<y_id>\d+)(?:&program_id=(?P<p_id>\d+))?(?:&program_semester_id=(?P<p_s_id>\d+))?$
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    year_id, program_id, program_semester_id = (
        int(y) if (y := context.match.group("y_id")) else None,
        int(y) if (y := context.match.group("p_id")) else None,
        int(y) if (y := context.match.group("p_s_id")) else None,
    )

    message: str
    _ = context.gettext

    if program_id is None:
        message = _("Select {}").format(_("Program"))
        programs = queries.programs(session)
        menu = build_menu(
            context.buttons.programs_list(programs, url, sep="&program_id="),
            1,
            footer_buttons=context.buttons.back(url, f"/{constants.ENROLLMENTS}.*"),
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
        user_id=context.user_data["id"],
        academic_year_id=year_id,
        program_semester_id=program_semester.id,
    )

    try:
        user = queries.user(session, context.user_data["id"])
        user.enrollments.append(enrollment_obj)
        is_only_enrollment = len(user.enrollments) == 1
        session.flush()
        success = await query.delete_message()
        if success:
            await query.message.reply_html(_("You have been enrolled"))
            if is_only_enrollment:
                user.roles.append(queries.role(session, RoleName.STUDENT))
                await set_my_commands(context.bot, user)
                help_message = messages.help(
                    user_roles={role.name for role in user.roles},
                    language_code=context.language_code,
                    new=RoleName.STUDENT,
                )
                await query.message.reply_html(
                    _("Your commands have been Updated")
                    + "\n"
                    + f"{'\n'.join(help_message.splitlines()[1:])}"
                )
            return None
    # enrollment creation has faild because user alread enrolled from another message
    except IntegrityError:
        await query.message.reply_html(_("Already enrolled"))
        return constants.ONE


@session
async def enrollment(
    update: Update,
    context: CustomContext,
    session: Session,
    enrollment_id: Optional[int] = None,
) -> None:
    """Runs on
    ^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)
    (/{constants.EDIT}\?program_semester_id=(?P<edit_p_s_id>\d+))?(/{constants.COURSES})?$
    """

    query = update.callback_query

    enrollment_id = enrollment_id or int(context.match.group("enrollment_id"))
    url = f"{URLPREFIX}/{constants.ENROLLMENTS}/{enrollment_id}"

    enrollment_obj = queries.enrollment(session, enrollment_id)
    edit_p_s_id = (
        int(y) if (y := context.match.groupdict().get("edit_p_s_id")) else None
    )

    if edit_p_s_id is not None:
        if edit_p_s_id == enrollment_obj.program_semester_id:
            await query.answer()
            return constants.ONE
        pair_program_semester = queries.program_semester(
            session, program_semester_id=edit_p_s_id
        )
        enrollment_obj.program_semester = pair_program_semester
        session.flush()
        await query.answer()

    await query.answer()
    level = enrollment_obj.semester.number // 2 + (enrollment_obj.semester.number % 2)
    program_semesters = queries.program_semesters(
        session, enrollment_obj.program.id, level=level
    )
    message = messages.enrollment_text(enrollment=enrollment_obj, context=context)

    user_courses = queries.user_courses(
        session,
        program_id=enrollment_obj.program.id,
        semester_id=enrollment_obj.semester.id,
        user_id=context.user_data["id"],
        sort_attr=(
            Course.ar_name if context.language_code == constants.AR else Course.en_name
        ),
    )

    semester_buttons = context.buttons.program_semesters_list(
        program_semesters,
        url,
        selected_ids=enrollment_obj.program_semester.id,
        sep=f"/{constants.EDIT}?program_semester_id=",
    )
    courses_url = f"{url}/{constants.COURSES}"
    courses_buttons = context.buttons.courses_list(
        user_courses,
        url=courses_url,
    )
    has_optional_courses = queries.has_optional_courses(
        session,
        program_id=enrollment_obj.program.id,
        semester_id=enrollment_obj.semester.id,
    )
    courses_buttons += (
        [
            context.buttons.optional_courses(f"{courses_url}/{constants.OPTIONAL}"),
        ]
        if has_optional_courses
        else []
    )
    keyboard = build_menu(
        courses_buttons,
        1,
        header_buttons=semester_buttons,
        footer_buttons=[
            context.buttons.back(url, f"/{constants.ENROLLMENTS}.*"),
            context.buttons.disenroll(f"{url}/{constants.DELETE}"),
        ],
        reverse=context.language_code == constants.AR,
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return constants.ONE


@session
async def enrollment_delete(update: Update, context: CustomContext, session: Session):
    """runs on ^{URLPREFIX}/{ENROLLMENTS}/(\d+)/{DELETE}$"""

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    enrollment_id = context.match.groups()[0]
    enrollment = queries.enrollment(session, enrollment_id)
    year = enrollment.academic_year
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: list
    message: str
    _ = context.gettext

    if has_confirmed is None:
        menu_buttons = context.buttons.delete_group(url=url)
        message = _("Delete warning {}").format(
            bold(_("Enrollment {} - {}").format(year.start, year.end))
        )
    elif has_confirmed == "0":
        menu_buttons = context.buttons.confirm_delete_group(url=url)
        message = _("Confirm delete warning {}").format(
            bold(_("Enrollment {} - {}").format(year.start, year.end))
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
                url, text=_("Your enrollments"), pattern=rf"/{constants.ENROLLMENTS}.*"
            )
        ]
        message = (
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


# ------------------------- ConversationHander -----------------------------

entry_points = [
    CallbackQueryHandler(
        enrollments_add,
        pattern=f"^{URLPREFIX}/{constants.ENROLLMENTS}/{constants.ADD}"
        f"\?year_id=(?P<y_id>\d+)"
        f"(?:&program_id=(?P<p_id>\d+))?(?:&program_semester_id=(?P<p_s_id>\d+))?$",
    ),
    CallbackQueryHandler(
        enrollment,
        pattern=f"^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
        f"(/{constants.EDIT}\?program_semester_id=(?P<edit_p_s_id>\d+))?(/{constants.COURSES})?$",
    ),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(commands.list_enrollments, pattern=f"^{URLPREFIX}$"),
        CallbackQueryHandler(
            enrollment_delete,
            pattern=f"^{URLPREFIX}/{constants.ENROLLMENTS}/(?P<enrollment_id>\d+)"
            f"/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
        usercourses_,
    ]
}

enrolments_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.ENROLLMENT_,
    per_message=True,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
