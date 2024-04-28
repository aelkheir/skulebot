import re
from typing import List

from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import buttons, constants, messages, queries
from src.models import Program, RoleName
from src.models.course import Course
from src.models.program_semester import ProgramSemester
from src.models.program_semester_course import ProgramSemesterCourse
from src.utils import Pager, build_menu, roles, session

URLPREFIX = constants.PROGRAM_
"""Used as a prefix for all `callback_data` s in this conversation module"""

DATA_KEY = constants.PROGRAM_
"""Used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`
in this conversation"""

STATEONE = f"{constants.PROGRAM_} {constants.ONE}"
STATEADD = f"{constants.PROGRAM_} {constants.ADD}"
STATEEDIT = f"{constants.PROGRAM_} {constants.EDIT}"


# helperes
def carriculam_title():
    return "Carriculam\n\n"


# ------------------------------- entry_points ---------------------------


@roles(RoleName.ROOT)
@session
async def program_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs with Message.text `/programs`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    programs = queries.programs(session)
    program_buttons = buttons.programs_list(
        programs, url=f"{URLPREFIX}/{constants.PROGRAMS}"
    )

    keyboard = build_menu(
        program_buttons,
        1,
        footer_buttons=buttons.add(f"{URLPREFIX}/{constants.PROGRAMS}", "Program"),
    )

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "Programs"
    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return STATEONE


# -------------------------- states callbacks ---------------------------
@session
async def program(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    """Runs on callback_query
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    program_id = int(context.match.group("program_id"))
    program = queries.program(
        session,
        program_id,
    )

    keyboard = [
        [
            buttons.edit(url, "Arabic Name", end=f"/{constants.AR}"),
            buttons.edit(url, "English Name", end=f"/{constants.EN}"),
        ],
        [
            buttons.carriculum(url=f"{url}/{constants.SEMESTERS}"),
            buttons.delete(url, "Program"),
        ],
        [buttons.back(url, "/\d+$")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = messages.multilang_names(ar=program.ar_name, en=program.en_name)
    await query.edit_message_text(message, reply_markup=reply_markup)

    return STATEONE


async def program_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on callback_data `^{URLPREFIX}/{constants.PROGRAMS}/({ADD})$`"""
    query = update.callback_query
    await query.answer()

    message = messages.type_name()
    await query.message.reply_text(
        message,
    )

    return STATEADD


@session
async def receive_name_new(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    en_name, ar_name = context.match.group("en_name"), context.match.group("ar_name")

    program = Program(
        en_name=en_name.strip(),
        ar_name=ar_name.strip(),
        duration=10,
    )
    session.add(program)
    session.flush()
    keyboard = [
        [
            buttons.view_added(
                text="Program",
                absolute_url=f"{URLPREFIX}/{constants.PROGRAMS}/{program.id}",
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = messages.success_created("Program")
    await update.message.reply_text(message, reply_markup=reply_markup)

    return STATEONE


async def program_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.match.group()
    lang_code = context.match.group("lang_code")
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    language = "Arabic" if lang_code == constants.AR else "English"
    message = messages.type_name_in_lang(language)
    await query.message.reply_text(
        message,
    )

    return STATEEDIT


@session
async def program_semester_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}$`
    """

    query = update.callback_query
    await query.answer()

    url = context.match.group()

    program_id = int(context.match.group("program_id"))
    program = queries.program(session, program_id)
    semesters = queries.semesters(session, program_id=program_id)
    semester_buttons = buttons.semester_list(
        semesters,
        url,
        selected_ids=[
            ps.semester.id
            for ps in program.program_semester_associations
            if ps.available
        ],
    )
    keyboard = build_menu(
        semester_buttons,
        2,
        footer_buttons=buttons.back(url, f"/{constants.SEMESTERS}"),
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = carriculam_title() + messages.first_list_level(program.en_name)
    await query.edit_message_text(message, reply_markup=reply_markup)

    return STATEONE


@session
async def semester_course_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runds on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)
    /{constants.SEMESTERS}/(?P<semester_id>\d+)$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler will be called from another
    # handler (`program_course_unlink`), and thus altering the url
    url = re.search(rf".*/{constants.SEMESTERS}/\d+", context.match.group()).group()

    program_id = int(context.match.group("program_id"))
    program = queries.program(session, program_id)

    semester_id = int(context.match.groups()[1])
    semester = queries.semester(session, semester_id)

    program_semester = queries.program_semester(
        session, program_id=program_id, semester_id=semester_id
    )
    available = program_semester and program_semester.available

    courses = queries.program_semester_courses(
        session, program_id=program_id, semester_id=semester_id
    )
    courses_buttons = buttons.program_semester_courses_list(
        courses, f"{url}/{constants.COURSES}"
    )
    keyboard = build_menu(
        courses_buttons,
        1,
        footer_buttons=[
            (
                buttons.deactivate(f"{url}/{constants.ACTIVATE}?a=0")
                if available
                else buttons.activate(f"{url}/{constants.ACTIVATE}?a=1")
            ),
            buttons.link_course(f"{url}/{constants.ADD}"),
        ],
    )
    keyboard += [[buttons.back(url, "/\d+$")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        carriculam_title()
        + messages.first_list_level(program.en_name)
        + messages.second_list_level(
            f"Semester {semester.number}" + (" ✅" if available else "")
        )
    )
    await query.edit_message_text(message, reply_markup=reply_markup)

    return STATEONE


@session
async def semester_activate(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runds on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}
    /(?P<semester_id>\d+)/{constants.ACTIVATE}\?a=(?P<activate>1|0)$`
    """

    query = update.callback_query
    await query.answer()

    program_id = int(context.match.group("program_id"))
    semester_id = int(context.match.group("semester_id"))
    program = queries.program(session, program_id)
    semester = queries.semester(session, semester_id)
    activate = int(context.match.group("activate"))

    # apply availabe to this program_semester
    program_semester = queries.program_semester(
        session, program_id=program_id, semester_id=semester_id
    )
    if not program_semester:
        program_semester = ProgramSemester(
            program=program, semester=semester, available=False
        )
        session.add(program_semester)
    if bool(program_semester.available) == bool(activate):
        return STATEONE
    program_semester.available = bool(activate)

    # apply availabe to the companion program_semester of the same level
    semester_number = semester.number
    pair_semester_number = (
        semester_number - 1 if semester_number % 2 == 0 else semester_number + 1
    )
    pair_semester = queries.semester(session, semester_number=pair_semester_number)
    pair_program_semester = queries.program_semester(
        session, program_id=program_id, semester_id=pair_semester.id
    )
    if not pair_program_semester:
        pair_program_semester = ProgramSemester(
            program=program, semester=pair_semester, available=False
        )
        session.add(pair_program_semester)
    pair_program_semester.available = bool(activate)

    session.flush()

    return await semester_course_list.__wrapped__(update, context, session)


@session
async def program_course(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}
    /(?P<semester_id>\d+)/{constants.COURSES}/(?P<course_id>\d+)
    (/{EDIT}\?o=(?P<optional>0|1))?$`
    """

    query = update.callback_query

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.COURSES}/\d+", context.match.group()).group()

    program_id = int(context.match.group("program_id"))
    semester_id = int(context.match.group("semester_id"))
    course_id = int(context.match.group("course_id"))

    psc = queries.program_semester_course(session, course_id)
    optional = bool(int(o)) if (o := context.match.group("optional")) else None
    if optional is not None and optional == psc.optional:
        await query.answer("Success! Course is set to optional")
        return STATEONE
    if optional is not None and optional != psc.optional:
        psc.optional = optional
        text = "optinoal" if optional else "required"
        await query.answer(f"Success! Course is set to {text}")

    await query.answer()

    program = psc.program
    semester = psc.semester
    course = psc.course

    program_semester = queries.program_semester(
        session, program_id=program_id, semester_id=semester_id
    )
    available = program_semester and program_semester.available

    keyboard = [
        [
            buttons.edit(url, "Semester"),
            buttons.unlink_course(f"{url}/{constants.DELETE}"),
        ],
        [
            buttons.required(f"{url}/{constants.EDIT}?o=0", selected=not psc.optional),
            buttons.optional(f"{url}/{constants.EDIT}?o=1", selected=psc.optional),
        ],
        [buttons.back(url, rf"/{constants.COURSES}/.*")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        carriculam_title()
        + messages.first_list_level(program.en_name)
        + messages.second_list_level(
            f"Semester {semester.number}" + (" ✅" if available else "")
        )
        + messages.third_list_level(course.get_name())
    )
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return STATEONE


@session
async def course_semester_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """
    Runs on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}
    /(?P<semester_id>\d+)/{constants.COURSES}
    /(?P<course_id>\d+)/{EDIT}(?:\?s_id=(?P<s_id>\d+))?$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.EDIT}", context.match.group()).group()

    program_id = int(context.match.group("program_id"))
    semester_id = int(context.match.group("semester_id"))
    course_id = int(context.match.group("course_id"))
    s_id = int(s) if (s := context.match.group("s_id")) else None

    program = queries.program(session, program_id)
    old_semester = queries.semester(session, semester_id)
    course = queries.program_semester_course(session, course_id).course

    message = carriculam_title() + messages.first_list_level(program.get_name())
    if s_id is None:
        semesters = queries.semesters(session, program_id=program_id)
        semester_buttons = buttons.semester_list(
            semesters, url, selected_ids=semester_id, sep="?s_id="
        )
        message += (
            messages.second_list_level(f"Semester {old_semester.number}")
            + messages.third_list_level(course.get_name())
            + "\nSelect semester"
        )
        keyboard = build_menu(
            semester_buttons,
            2,
            footer_buttons=buttons.back(url, rf"/{constants.EDIT}/.*"),
        )
    elif s_id:
        psc = queries.program_semester_course(session, course_id)
        psc.semester_id = s_id
        new_semester = queries.semester(session, s_id)
        message += (
            messages.second_list_level(f"Semester {new_semester.number}")
            + messages.third_list_level(course.get_name())
            + f"\n{messages.success_updated('Course semester')}"
        )
        course_url = url.replace(f"/{semester_id}/", f"/{s_id}/")
        keyboard = build_menu(
            [
                buttons.back(course_url, "", text="to Course"),
                buttons.back(
                    url,
                    rf"/{constants.COURSES}/.*",
                    text=f"to Semeter {old_semester.number}",
                ),
                buttons.back(
                    course_url,
                    rf"/{constants.COURSES}/.*",
                    text=f"to Semeter {new_semester.number}",
                ),
            ],
            1,
        )
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return STATEONE


@session
async def program_course_unlink(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}
    /(?P<semester_id>\d+)/{constants.COURSES}/(?P<course_id>\d+)/{constants.DELETE}$`
    """

    query = update.callback_query

    course_id = int(context.match.group("course_id"))

    psc = queries.program_semester_course(session, course_id)
    session.delete(psc)

    course = psc.course

    await query.answer(messages.success_unlinked(course.get_name()))
    return await semester_course_list.__wrapped__(update, context, session)


@session
async def course_link(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runds on callback_data
    ^{URLPREFIX}/{constants.PROGRAMS}/(\d+)/{constants.SEMESTERS}/(\d+)/{ADD}$
    """
    query: None | CallbackQuery = None

    query = update.callback_query

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.ADD}", context.match.group()).group()

    program_id = int(context.match.group("program_id"))
    semester_id = int(context.match.group("semester_id"))
    d_id, page, c_id = (
        int(d) if (d := context.match.group("d_id")) else None,
        int(p) if (p := context.match.group("page")) else None,
        int(c) if (c := context.match.group("c_id")) else None,
    )

    program = queries.program(session, program_id)
    semester = queries.semester(session, semester_id)

    keyboard: List
    message: str
    message = (
        carriculam_title()
        + messages.first_list_level(program.en_name)
        + messages.second_list_level(f"Semester {semester.number}")
    )

    if d_id is None:
        await query.answer()
        departments = queries.departments(session)
        menu = buttons.departments_list(
            departments, url, include_none_department=True, sep="?d_id="
        )
        menu += [
            buttons.back(url, f"/{constants.ADD}"),
        ]
        keyboard = build_menu(menu, 1)
        message += "\nSelect course"
    if d_id is not None and c_id is None:
        await query.answer()
        offset = int(page) if page else 0
        deptartment_courses = queries.department_courses(
            session, department_id=d_id if d_id != 0 else None
        )
        queries.program_semester_courses(session, program_id=program_id)
        p_courses = {
            psc.course_id: psc.semester.number
            for psc in queries.program_semester_courses(session, program_id=program_id)
        }
        pager = Pager[Course](deptartment_courses, offset, 12)

        menu = buttons.program_courses(
            courses=pager.items,
            course_semester=p_courses,
            url=url,
            sep=f"?d_id={d_id}&p={offset}&c_id=",
        )
        keyboard = build_menu(menu, 2)
        if pager.has_next or pager.has_previous:
            pager_keyboard = []
            keyboard.append(pager_keyboard)
            if pager.has_previous:
                pager_keyboard.append(
                    buttons.previous_page(
                        f"{url}?d_id={d_id}&p={pager.previous_offset}"
                    )
                )
            if pager.has_next:
                pager_keyboard.append(
                    buttons.next_page(f"{url}?d_id={d_id}&p={pager.next_offset}")
                )
        keyboard.extend([[buttons.back(url, pattern="\?.*")]])
        message += "\nSelect course"
    if c_id:
        course = queries.course(session, c_id)
        psc = queries.program_semester_course(
            session, program_id=program_id, course_id=c_id
        )
        should_update = context.match.group("should_update")
        if psc is None:
            psc = ProgramSemesterCourse(
                program_id=program_id,
                semester_id=semester_id,
                course_id=c_id,
                optional=False,
            )
            session.add(psc)
            await query.answer(messages.success_linked(course.get_name()))
            return await semester_course_list.__wrapped__(update, context, session)
        if psc and psc.semester.number == semester.number:
            await query.answer("Course is already present")
            return STATEONE
        if psc and psc.semester.number != semester.number and should_update != "1":
            message += f"\nCourse is already linked in Semester {psc.semester.number}"
            keyboard = [
                [
                    buttons.update_to_semester(
                        f"{url}?d_id={d_id}&p={page}&c_id={c_id}&u=1", semester.number
                    )
                ],
                [buttons.back(absolute_url=f"{url}?d_id={d_id}&p={page}")],
            ]
        else:
            psc.semester_id = semester_id
            await query.answer(messages.success_linked(course.get_name()))
            return await semester_course_list.__wrapped__(update, context, session)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return STATEONE


@session
async def receive_name_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    name = context.match.groups()[0].strip()

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<_id>\d+)"
        f"/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$",
        url,
    )

    program_id = int(match.group("program_id"))
    program = queries.program(
        session,
        program_id,
    )
    lang_code = match.group("lang_code")
    setattr(program, f"{lang_code}_name", name)

    keyboard = [
        [
            buttons.back(
                absolute_url=f"{URLPREFIX}/{constants.PROGRAMS}/{program_id}",
                text="to Program",
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    language = "Arabic" if lang_code == constants.AR else "English"
    message = messages.success_updated(f"{language} name")

    await update.message.reply_text(message, reply_markup=reply_markup)
    return STATEONE


@session
async def program_delete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session
):
    """Runs on callback_data
    `^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)
    /{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$`
    """

    query = update.callback_query
    await query.answer()

    # url here is calculated because this handler reenter with query params
    url = re.search(rf".*/{constants.DELETE}", context.match.group()).group()

    program_id = context.match.groups()[0]
    program = queries.program(session, program_id)
    has_confirmed = context.match.group("has_confirmed")

    menu_buttons: List
    message: str
    if has_confirmed is None:
        menu_buttons = buttons.delete_group(url=url)
        message = messages.delete_confirm(f"Program {program.en_name}")
    elif has_confirmed == "0":
        menu_buttons = buttons.confirm_delete_group(url=url)
        message = messages.delete_reconfirm(f"Program {program.en_name}")
    elif has_confirmed == "1":
        session.delete(program)
        menu_buttons = [
            buttons.back(url, text="to Programs", pattern=rf"/\d+/{constants.DELETE}")
        ]
        message = messages.success_deleted(f"Program {program.en_name}")

    keyboard = build_menu(menu_buttons, 1)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )

    return STATEONE


# ------------------------- ConversationHander -----------------------------

entry_points = [
    CommandHandler("programs", program_list),
]

states = {
    STATEONE: [
        CallbackQueryHandler(
            program, pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)$"
        ),
        CallbackQueryHandler(
            program_add, pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/({constants.ADD})$"
        ),
        CallbackQueryHandler(
            program_list, pattern=f"^{URLPREFIX}/{constants.PROGRAMS}$"
        ),
        CallbackQueryHandler(
            program_edit_name,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.EDIT}/(?P<lang_code>{constants.AR}|{constants.EN})$",
        ),
        CallbackQueryHandler(
            program_semester_list,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)/{constants.SEMESTERS}$",
        ),
        CallbackQueryHandler(
            semester_course_list,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)$",
        ),
        CallbackQueryHandler(
            semester_activate,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)/{constants.ACTIVATE}\?a=(?P<activate>1|0)$",
        ),
        CallbackQueryHandler(
            program_course,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)"
            f"(/{constants.EDIT}\?o=(?P<optional>0|1))?$",
        ),
        CallbackQueryHandler(
            course_semester_edit,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)"
            f"/{constants.COURSES}/(?P<course_id>\d+)/{constants.EDIT}(?:\?s_id=(?P<s_id>\d+))?$",
        ),
        CallbackQueryHandler(
            program_course_unlink,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)/{constants.COURSES}/(?P<course_id>\d+)/{constants.DELETE}$",
        ),
        CallbackQueryHandler(
            course_link,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.SEMESTERS}/(?P<semester_id>\d+)/{constants.ADD}(?:\?(?:d_id=(?P<d_id>\d+))?"
            f"(?:&p=(?P<page>\d+))?(?:&c_id=(?P<c_id>\d+))?(?:&u=(?P<should_update>1))?)?$",
        ),
        CallbackQueryHandler(
            program_delete,
            pattern=f"^{URLPREFIX}/{constants.PROGRAMS}/(?P<program_id>\d+)"
            f"/{constants.DELETE}(?:\?c=(?P<has_confirmed>1|0))?$",
        ),
    ],
}
states.update(
    {
        STATEADD: states[STATEONE]
        + [
            MessageHandler(
                filters.Regex(r"^(?P<en_name>(?:.)+?)\s*-\s*(?P<ar_name>(?:.)+?)$"),
                receive_name_new,
            ),
        ]
    }
)
states.update(
    {
        STATEEDIT: states[STATEONE]
        + [
            MessageHandler(filters.Regex(r"^(.+)$"), receive_name_edit),
        ]
    }
)


program_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.PROGRAM_,
    # allow_reentry must be set to true for the conversation to work
    # after pressing going back to an entry point
    allow_reentry=True,
)
