import contextlib
import re

from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden

from src import constants, messages, queries
from src.customcontext import CustomContext
from src.database import Session as DBSession
from src.models import (
    Course,
    Enrollment,
    Material,
    ProgramSemester,
    ProgramSemesterCourse,
    RefFilesMixin,
    Review,
    SettingKey,
    SingleFile,
    User,
)
from src.utils import get_setting_value, session, user_locale


@session
async def handler(update: Update, context: CustomContext, session: Session, back):
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
    material = session.get(Material, material_id)
    course = material.course
    enrollment_id = context.match.group("enrollment_id")
    enrollment = session.get(Enrollment, enrollment_id)
    _ = context.gettext

    if isinstance(material, RefFilesMixin) and len(material.files) == 0:
        await query.answer(_("Can't publish no files"))
        return constants.ONE

    material_title = messages.material_title_text(context.match, material, context)

    if material.published:
        await query.answer(_("Already published").format(material_title))
        return constants.ONE
    if url.startswith(constants.CONETENT_MANAGEMENT_):
        material.published = True
        await query.answer(_("Success! {} published").format(material_title))
        return await back.__wrapped__(update, context, session)

    # TODO: decide if we want to allow puplishing on non active years
    # for now we allow it but without sending notifications.
    most_recent_year = queries.academic_year(session, most_recent=True)
    if enrollment.academic_year != most_recent_year:
        material.published = True
        await query.answer(_("Success! {} published").format(material_title))
        return await back.__wrapped__(update, context, session)

    if notify is None:
        await query.answer()
        keyboard = [
            [
                context.buttons.with_notification(url),
                context.buttons.without_notification(url),
            ],
            [context.buttons.back(url, pattern=rf"/{constants.PUBLISH}")],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            messages.title(context.match, session, context)
            + "\n"
            + _("t-symbol")
            + "─ "
            + course.get_name(context.language_code)
            + "\n"
            + messages.material_type_text(context.match, context=context)
            + ("\n" if isinstance(material, SingleFile) else "")
            + messages.material_message_text(
                context.match, session, material=material, context=context
            )
            + "\n\n"
            + _("Publishing Options").format(material_title)
        )

        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    elif notify == "0":
        material.published = True
        session.flush()
        await query.answer(_("Success! {} published").format(material_title))
        return await back.__wrapped__(update, context, session)
    elif notify == "1":
        # TODO handle publishing logic
        material.published = True
        session.flush()
        await query.answer(_("Success! {} published").format(material_title))
        await register_jobs.__wrapped__(update, context, session)
        return await back.__wrapped__(update, context, session)
    return None


def remove_job_if_exists(name: str, context: CustomContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


@session
async def register_jobs(update: Update, context: CustomContext, session: Session):
    material_id = context.match.group("material_id")
    material = session.get(Material, material_id)

    enrollment_id = context.match.group("enrollment_id")
    enrollment = session.get(Enrollment, enrollment_id)
    academic_year_id = enrollment.academic_year_id
    users = session.scalars(
        select(User)
        .select_from(Enrollment)
        .join(User)
        .join(ProgramSemester)
        .join(
            ProgramSemesterCourse,
            and_(
                ProgramSemester.program_id == ProgramSemesterCourse.program_id,
                ProgramSemester.semester_id == ProgramSemesterCourse.semester_id,
            ),
        )
        .join(Course, ProgramSemesterCourse.course_id == Course.id)
        .filter(
            Enrollment.academic_year_id == academic_year_id,
            Course.id == material.course_id,
        )
    ).all()

    setting_key = None
    for sk in SettingKey:
        if material.type in sk.key:
            setting_key = sk

    if setting_key is None:
        raise ValueError(
            f"no notification setting key found for material of type {material.type}"
        )

    for i, user in enumerate(users):
        user_setting = get_setting_value(
            session, user_id=user.id, setting_key=setting_key
        )

        if bool(user_setting) is False:
            return

        JOBNAME = (
            str(context.user_data["telegram_id"])
            + "_NOTIFY_"
            + str(user.telegram_id)
            + "_M_"
            + str(material.id)
        )
        remove_job_if_exists(JOBNAME, context)

        session.expunge_all()
        is_last = i == len(users) - 1
        is_first = i == 0
        when = i * 2
        context.job_queue.run_once(
            send_notification,
            when=when,
            name=JOBNAME,
            data={
                "user": user,
                "material": material,
                "is_last": is_last,
                "is_first": is_first,
            },
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
        )


async def send_notification(context: CustomContext) -> None:
    """Send the notification message."""
    job = context.job

    user: User = job.data["user"]
    material: Material = job.data["material"]
    is_first: bool = job.data["is_first"]
    is_last: bool = job.data["is_last"]

    # Get language for user to be notified
    translation = user_locale(user.language_code)

    if is_first:
        await context.bot.send_message(
            job.chat_id, text=context.gettext("Started sending notifications")
        )

    with DBSession.begin() as session:
        session.add_all([material, user])
        with contextlib.suppress(Forbidden):
            message = (
                translation.gettext("t-symbol")
                + "─ 🔔 "
                + material.course.get_name(user.language_code)
                + "\n│ "
                + translation.gettext("corner-symbol")
                + "── "
                + (
                    messages.material_title_text(context.match, material, context)
                    if not isinstance(material, SingleFile)
                    else translation.gettext(material.type)
                )
            )

            keyboard = [
                [
                    context.buttons.show_more(
                        f"{constants.NOTIFICATION_}/{material.type}/{material.id}"
                    )
                ]
            ]
            if isinstance(material, (Review, SingleFile)):
                keyboard = [
                    [
                        context.buttons.material(
                            f"{constants.NOTIFICATION_}/{material.type}", material
                        )
                    ]
                ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                user.chat_id, text=message, reply_markup=reply_markup
            )

    if is_last:
        await context.bot.send_message(
            job.chat_id, text=context.gettext("Done sending notifications")
        )
