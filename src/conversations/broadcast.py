"""Contains callbacks and handlers for the /broadcast conversaion"""

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import constants, jobs, queries
from src.constants import COMMANDS
from src.customcontext import CustomContext
from src.models import Enrollment, RoleName, User
from src.utils import build_menu, roles, session

URLPREFIX = constants.BROADCAST_
"""used as a prefix for all `callback data` in this conversation"""

DATA_KEY = constants.BROADCAST_
"""used as a key for read/wirte operations on `chat_data`, `user_data`, `bot_data`"""


# ------------------------------- entry_points ---------------------------
@roles(RoleName.ROOT)
async def broadcast(
    update: Update,
    context: CustomContext,
    lang: Optional[dict] = None,
):
    """Runs with Message.text `/broadcast`"""

    query: None | CallbackQuery = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    has_arabic, has_english = 0, 0
    if lang is not None:
        has_arabic, has_english = int(lang[constants.AR]), int(lang[constants.EN])
    elif query is not None:
        has_arabic, has_english = int(context.match.group("has_arabic")), int(
            context.match.group("has_english")
        )

    url = f"{URLPREFIX}"
    _ = context.gettext

    keyboard = build_menu(
        [
            context.buttons.arabic(
                url=f"{url}/{constants.AR}?en={has_english}",
                selected=bool(has_arabic),
            ),
            context.buttons.english(
                url=f"{url}/{constants.EN}?ar={has_arabic}",
                selected=bool(has_english),
            ),
        ],
        2,
        footer_buttons=(
            InlineKeyboardButton(
                _("Next"), callback_data=f"{url}?ar={has_arabic}&en={has_english}"
            )
            if any((has_arabic, has_english))
            else None
        ),
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        _("Select message language")
        if lang is None
        else (
            _("Would you like to provide a translation in an another language")
            if not all((has_arabic, has_english))
            else _("All set.")
        )
    )

    if query:
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return constants.ONE


# -------------------------- states callbacks ---------------------------


async def message(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}/(?P<lang_code>{constants.AR}|{constants.EN})$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    context.chat_data.setdefault(DATA_KEY, {})["url"] = url

    _ = context.gettext
    lang_code = context.match.group("lang_code")
    language = _("Arabic") if lang_code == constants.AR else _("English")
    message = _("Type message in {}").format(language)
    await query.message.reply_text(
        message,
    )

    return constants.LANGUAGE


async def receive_message(update: Update, context: CustomContext):
    """Runs on `Message.text` matching ^(\d+)$"""

    context.chat_data.setdefault(DATA_KEY, {})["text"] = update.message.text_html

    url = context.chat_data[DATA_KEY]["url"]
    match: re.Match[str] | None = re.search(
        f"^{URLPREFIX}/(?P<lang_code>{constants.AR}|{constants.EN})"
        "\?(?:ar=(?P<has_arabic>0|1)|en=(?P<has_english>0|1))$",
        url,
    )

    lang_code = match.group("lang_code")
    other_code = constants.EN if lang_code == constants.AR else constants.AR
    context.chat_data.setdefault(DATA_KEY, {})[
        f"{lang_code}_message_id"
    ] = update.message.id
    lang = {
        lang_code: True,
        other_code: bool(int(match.group("has_english") or match.group("has_arabic"))),
    }
    return await broadcast.__wrapped__(update, context, lang=lang)


@session
async def target(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}\?(?:ar=(?P<has_arabic>0|1)|en=(?P<has_english>0|1))$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    has_arabic = int(context.match.group("has_arabic"))
    has_english = int(context.match.group("has_english"))
    program_id = (
        int(program_id) if (program_id := context.match.group("program_id")) else None
    )
    _ = context.gettext

    if "&p_id=" not in url:
        message = _("Select group to braodcast to")
        keyboard = build_menu(
            [
                InlineKeyboardButton(
                    _("All Enrolled Students"),
                    callback_data=f"{URLPREFIX}?ar={has_arabic}&en={has_english}&t=enrolled",
                ),
                InlineKeyboardButton(
                    _("Students Missing Publishers"),
                    callback_data=f"{URLPREFIX}?ar={has_arabic}&en={has_english}&t=missing",
                ),
                InlineKeyboardButton(
                    _("Specific Batch"),
                    callback_data=f"{URLPREFIX}?ar={has_arabic}&en={has_english}&p_id=",
                ),
            ],
            1,
            footer_buttons=context.buttons.back(
                absolute_url=f"{URLPREFIX}/{constants.LANGUAGE}?ar={has_arabic}&en={has_english}"
            ),
        )
    elif program_id is None:
        programs = queries.programs(session)
        program_buttons = context.buttons.programs_list(programs, url=f"{url}", sep="")
        keyboard = build_menu(
            program_buttons,
            1,
            footer_buttons=context.buttons.back(url, pattern="&p_id="),
        )
        message = _("Select program")
    else:
        program_semesters = queries.program_semesters(session, program_id=program_id)
        levels_button = context.buttons.program_levels_list(
            program_semesters=program_semesters,
            url=f"{URLPREFIX}?ar={has_arabic}&en={has_english}&p_id={program_id}",
            sep="&t=",
        )
        keyboard = build_menu(
            levels_button,
            1,
            footer_buttons=context.buttons.back(url, pattern="\d+$"),
        )
        message = _("Select level")

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

    return constants.ONE


async def broadcast_options(update: Update, context: CustomContext):
    """Runs on callback_data
    `^{URLPREFIX}\?(?:ar=(?P<has_arabic>0|1)|en=(?P<has_english>0|1))$`"""

    query = update.callback_query
    await query.answer()

    url = context.match.group()
    target = context.match.group("target")
    _ = context.gettext

    if target == "missing":
        await update.effective_message.reply_text("This is currently not implemented!")
        return constants.ONE

    keyboard = build_menu(
        [
            InlineKeyboardButton(
                _("Send"),
                callback_data=f"{url}&o=send",
            ),
            InlineKeyboardButton(
                _("Send & Pin"),
                callback_data=f"{url}&o=pin",
            ),
        ],
        2,
        header_buttons=InlineKeyboardButton(
            _("Preview"), callback_data=f"{url}&o=preview"
        ),
        footer_buttons=context.buttons.back(url, pattern="&t=.*"),
    )

    message = _("Select action")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)
    return None


@session
async def action(update: Update, context: CustomContext, session: Session):
    """Runs on callback_data
    `^{URLPREFIX}\?(?:ar=(?P<has_arabic>0|1)|en=(?P<has_english>0|1))$`"""

    query = update.callback_query
    await query.answer()

    target = context.match.group("target")
    has_arabic = bool(int(context.match.group("has_arabic")))
    has_english = bool(int(context.match.group("has_english")))
    message_ids = []
    has_arabic and message_ids.append(context.chat_data[DATA_KEY]["ar_message_id"])
    has_english and message_ids.append(context.chat_data[DATA_KEY]["en_message_id"])

    option = context.match.group("option")
    if option == "preview":
        for m_id in message_ids:
            await context.bot.copy_message(
                update.effective_chat.id,
                from_chat_id=update.effective_chat.id,
                message_id=m_id,
            )
        return

    most_recent = queries.academic_year(session, most_recent=True)
    users = []
    if target.isnumeric():
        program_semester = queries.program_semester(session, target)
        level = program_semester.semester.number // 2 + (
            program_semester.semester.number % 2
        )
        program_semesters = queries.program_semesters(
            session, program_semester.program.id, level=level
        )
        users = session.scalars(
            select(User)
            .select_from(Enrollment)
            .join(User)
            .filter(
                Enrollment.program_semester_id.in_([ps.id for ps in program_semesters]),
                Enrollment.academic_year_id == most_recent.id,
            )
        ).all()
    elif target == "enrolled":
        users = session.scalars(
            select(User)
            .select_from(Enrollment)
            .join(User)
            .filter(
                Enrollment.academic_year_id == most_recent.id,
            )
        ).all()
    elif target == "missing":
        # TODO: Missing right now
        # program_semester_1 = aliased(ProgramSemester)
        # ids = session.scalars(
        #     select(program_semester_1.id)
        #     .select_from(Enrollment)
        #     .join(ProgramSemester)
        #     .join(Semester)
        #     .join(
        #         program_semester_1,
        #         and_(
        #             program_semester_1.program_id == ProgramSemester.program_id,
        #             program_semester_1.semester_id.in_(
        #                 [
        #                     Semester.number,
        #                     Semester.number
        #                     + case((Semester.number % 2 == 0, -1), else_=1),
        #                 ]
        #             ),
        #         ),
        #     )
        #     .join(AccessRequest)
        #     .filter(
        #         AccessRequest.status == Status.GRANTED,
        #         Enrollment.academic_year_id == most_recent.id,
        #     )
        #     .distinct(program_semester_1.id)
        # ).all()
        # users = session.scalars(
        #     select(User)
        #     .select_from(Enrollment)
        #     .join(User)
        #     .filter(
        #         Enrollment.academic_year_id == most_recent.id,
        #         Enrollment.program_semester_id.not_in(ids),
        #     )
        # ).all()
        pass

    success = await query.delete_message()
    if success:
        session.expunge_all()
        for i, user in enumerate(users):
            JOBNAME = (
                str(context.user_data["telegram_id"])
                + "_BROADCAST_TO_"
                + str(user.telegram_id)
            )
            jobs.remove_job_if_exists(JOBNAME, context)

            is_last = i == len(users) - 1
            is_first = i == 0
            when = i * 2
            context.job_queue.run_once(
                send_message,
                when=when,
                name=JOBNAME,
                data={
                    "user": user,
                    "option": option,
                    "is_last": is_last,
                    "is_first": is_first,
                    "has_arabic": has_arabic,
                    "has_english": has_english,
                },
                chat_id=update.effective_chat.id,
                user_id=update.effective_user.id,
            )

        if len(users) == 0:
            _ = context.gettext
            await context.bot.send_message(
                update.effective_chat.id, _("Done! No users to broadcast to")
            )


async def send_message(context: CustomContext) -> None:
    """Broadcast the message."""
    job = context.job

    user: User = job.data["user"]
    option: str = job.data["option"]
    has_arabic: bool = job.data["has_arabic"]
    has_english: bool = job.data["has_english"]
    is_first: bool = job.data["is_first"]
    is_last: bool = job.data["is_last"]

    if is_first:
        await context.bot.send_message(
            job.chat_id, text=context.gettext("Started Broadcasting the message")
        )

    message_id = None
    if user.language_code == constants.EN:
        if has_english:
            message_id = context.chat_data[DATA_KEY]["en_message_id"]
        else:
            message_id = context.chat_data[DATA_KEY]["ar_message_id"]
    elif user.language_code == constants.AR:
        if has_arabic:
            message_id = context.chat_data[DATA_KEY]["ar_message_id"]
        else:
            message_id = context.chat_data[DATA_KEY]["en_message_id"]

    message = await context.bot.copy_message(
        user.chat_id, from_chat_id=job.chat_id, message_id=message_id
    )
    if option == "pin":
        await context.bot.pin_chat_message(user.chat_id, message.message_id)

    if is_last:
        await context.bot.send_message(
            job.chat_id, text=context.gettext("Done broadcasting message")
        )


# ------------------------- ConversationHander -----------------------------

cmd = COMMANDS
entry_points = [
    CommandHandler(cmd.broadcast.command, broadcast),
    CallbackQueryHandler(
        broadcast,
        pattern=f"^{URLPREFIX}/{constants.LANGUAGE}\?ar=(?P<has_arabic>0|1)&en=(?P<has_english>0|1)$",
    ),
]

states = {
    constants.ONE: [
        CallbackQueryHandler(
            message,
            pattern=f"^{URLPREFIX}/(?P<lang_code>{constants.AR}|{constants.EN})"
            "\?(?:ar=(?P<has_arabic>0|1)|en=(?P<has_english>0|1))$",
        ),
        CallbackQueryHandler(
            target,
            pattern=f"^{URLPREFIX}"
            "\?ar=(?P<has_arabic>0|1)&en=(?P<has_english>0|1)"
            "(&p_id=)?(?P<program_id>\d+)?$",
        ),
        CallbackQueryHandler(
            broadcast_options,
            pattern=f"^{URLPREFIX}"
            "\?ar=(?P<has_arabic>0|1)&en=(?P<has_english>0|1)"
            "(&p_id=\d+)?&t=(?P<target>\w+)$",
        ),
        CallbackQueryHandler(
            action,
            pattern=f"^{URLPREFIX}"
            "\?ar=(?P<has_arabic>0|1)&en=(?P<has_english>0|1)"
            "(&p_id=\d+)?&t=(?P<target>\w+)&o=(?P<option>\w+)$",
        ),
    ]
}
states.update(
    {
        constants.LANGUAGE: states[constants.ONE]
        + [
            MessageHandler(filters.TEXT, receive_message),
        ]
    }
)

broadcast_ = ConversationHandler(
    entry_points=entry_points,
    states=states,
    fallbacks=[],
    name=constants.BROADCAST_,
    persistent=True,
    # allow_reentry must be set to true for the conversation
    # to work after pressing Back button
    allow_reentry=True,
)
