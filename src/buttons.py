import calendar
import random
import re
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Union

from babel.dates import format_date
from telegram import InlineKeyboardButton
from telegram.ext import ContextTypes

from src import constants
from src.constants import LEVELS
from src.models import (
    AcademicYear,
    AccessRequest,
    Course,
    Department,
    Enrollment,
    File,
    HasNumber,
    Material,
    MaterialType,
    Program,
    ProgramSemester,
    ProgramSemesterCourse,
    Review,
    Semester,
    SettingKey,
    SingleFile,
    Status,
)
from src.models.material import REVIEW_TYPES, get_review_type_name
from src.utils import build_menu, user_locale

calendar.setfirstweekday(6)


class Buttons:
    def __init__(self, language_code: Union[constants.AR, constants.EN]) -> None:
        self._language_code = language_code
        self._gettext = user_locale(language_code).gettext

    def __setattr__(self, key: str, value: object) -> None:
        """Overrides :meth:`object.__setattr__` to prevent the overriding of attributes.

        Raises:
            :exc:`AttributeError`
        """
        # protected attributes can always be set for convenient internal use
        if key[0] == "_":
            super().__setattr__(key, value)
            return
        raise AttributeError(
            f"Attribute `{key}` of class `{self.__class__.__name__}` can't be set!"
        )

    def __delattr__(self, key: str) -> None:
        """Overrides :meth:`object.__delattr__` to prevent the deletion of attributes.

        Raises:
            :exc:`AttributeError`
        """
        # protected attributes can always be deleted for convenient internal use
        if key[0] == "_":
            super().__delattr__(key)
            return
        raise AttributeError(
            f"Attribute `{key}` of class `{self.__class__.__name__}` can't be deleted!"
        )

    def optional_courses(self, url: str) -> InlineKeyboardButton:
        _ = self._gettext
        return InlineKeyboardButton(
            text="[" + _("Optional Courses") + "]", callback_data=url
        )

    def new_access_request(
        self, enrollment: Enrollment, url: str
    ) -> InlineKeyboardButton:
        _ = self._gettext
        semester = enrollment.program_semester.semester
        level = (semester.number // 2 + (semester.number % 2)) - 1
        text = _(LEVELS[level])
        return InlineKeyboardButton(
            f"{text} [" + _("Request Access") + "]",
            callback_data=url,
        )

    def new_enrollment(self, year: AcademicYear, url: str) -> InlineKeyboardButton:
        _ = self._gettext
        return InlineKeyboardButton(
            f"{year.start} - {year.end} [" + _("Enroll Now") + "]",
            callback_data=url,
        )

    def access_requests_list(
        self, access_requests: List[AccessRequest], url: str
    ) -> List[InlineKeyboardButton]:
        """Builds a list of :class:`InlineKeyboardButton` for model
        :class:`AccessRequest` with
            * `InlineKeyboardButton.text = access_request.year.start -
                access_request.year.end`
            * `InlineKeyboardButton.callback_data = {url}/{access_request.id}`

        Args:
            access_requests (Sequence[:obj:`AccessRequest`]): A list of
                :obj:`AccessRequest` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
        """
        buttons = []
        _ = self._gettext
        for request in access_requests:
            enrollment = request.enrollment
            semester = enrollment.program_semester.semester
            level = (semester.number // 2 + (semester.number % 2)) - 1
            text = _(LEVELS[level])
            ispending = request.status == Status.PENDING
            buttons.append(
                InlineKeyboardButton(
                    f"{text}" + (" [" + _("Pending") + "]" if ispending else ""),
                    callback_data=f"{url}/{enrollment.id}",
                )
            )
        return buttons

    async def access_requests_list_chat_name(
        self,
        access_requests: List[AccessRequest],
        url: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> List[InlineKeyboardButton]:
        """Builds a list of :class:`InlineKeyboardButton` for model
        :class:`AccessRequest` with
            * `InlineKeyboardButton.text = access_request.year.start -
                access_request.year.end`
            * `InlineKeyboardButton.callback_data = {url}/{access_request.id}`

        Args:
            access_requests (Sequence[:obj:`AccessRequest`]): A list of
                :obj:`AccessRequest` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            context (:obj:`ContextTypes`): A `telegram.ext.ContextTypes` instance.
        """
        buttons = []
        for request in access_requests:
            enrollment = request.enrollment
            user = enrollment.user
            chat = await context.bot.get_chat(user.chat_id)
            buttons.append(
                InlineKeyboardButton(
                    f"{chat.first_name}"
                    + (f" {l_name}" if (l_name := chat.last_name) else "")
                    + (f" @{u}" if (u := chat.username) else ""),
                    callback_data=f"{url}/{request.id}",
                )
            )
        return buttons

    def semester_list(
        self,
        semesters: Sequence[Semester],
        url: str,
        sep: str = "/",
        selected_ids: Optional[Union[int, Sequence[int]]] = None,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model
        :class:`Semester` with
        `InlineKeyboardButton.text = Semester <semester-number>` and
        `InlineKeyboardButton.callback_data = {url}{sep}{semester.id}`

        Args:
            semesters (Sequence[:obj:`Semester`]): A list of :obj:`Semester` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (:obj:`int`, optional): An id of a semester in
                :paramref:`semesters` to mark as selected. This will produce a
                green checkmark next to the button title.
        """
        if isinstance(selected_ids, int):
            selected_ids = (selected_ids,)
        _ = self._gettext
        return [
            InlineKeyboardButton(
                _("Semester")
                + f" {semester.number}"
                + (" ✅" if selected_ids and semester.id in selected_ids else ""),
                callback_data=f"{url}{sep}{semester.id}",
            )
            for semester in semesters
        ]

    def program_semesters_list(
        self,
        program_semesters: List[ProgramSemester],
        url: str,
        selected_ids: Optional[Union[int, Sequence[int]]] = None,
        sep: str = "/",
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model
        :class:`ProgramSemester` with
        `InlineKeyboardButton.text = Semester <semester-number>` and
        `InlineKeyboardButton.callback_data = {url}{sep}{program_semester.id}`

        Args:
            program_semesters (Sequence[:obj:`ProgramSemester`]): A list of
                :obj:`ProgramSemester` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (:obj:`int`, optional): An id of a program_semester in
                :paramref:`program_semesters` to mark as selected. This will produce
                a green checkmark next to the button
                title.
        """
        if isinstance(selected_ids, int):
            selected_ids = (selected_ids,)
        _ = self._gettext
        return [
            InlineKeyboardButton(
                _("Semester")
                + f" {ps.semester.number}"
                + (" ✅" if selected_ids and ps.id in selected_ids else ""),
                callback_data=f"{url}{sep}{ps.id}",
            )
            for ps in program_semesters
        ]

    def program_levels_list(
        self,
        program_semesters: List[ProgramSemester],
        url: str,
        sep: str = "/",
    ):
        """Builds a list of :class:`InlineKeyboardButton` from
        :class:`ProgramSemester`s with:
        * `InlineKeyboardButton.text = [First |  Second | ...] Year`
        * `InlineKeyboardButton.callback_data =
        {url}{sep}{program_semester.semester.id}`

        Args:
            program_semesters (Sequence[:obj:`ProgramSemester`]): A list of
                :obj:`ProgramSemester` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
        """
        buttons = []
        _ = self._gettext
        for program_semester in program_semesters:
            semester = program_semester.semester
            if semester.number % 2 == 1 and program_semester.available:
                level = (semester.number // 2 + (semester.number % 2)) - 1
                text = _(LEVELS[level])
                buttons.append(
                    InlineKeyboardButton(
                        f"{text}",
                        callback_data=f"{url}{sep}{program_semester.id}",
                    )
                )
        return buttons

    def departments_list(
        self,
        departments: List[Department],
        url: str,
        sep: str = "/",
        selected_id: Optional[int] = None,
        include_none_department: bool = True,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model
        :class:`Department` with
        `InlineKeyboardButton.text = Department.{ar/en}_name` and
        `InlineKeyboardButton.callback_data = {url}{sep}{department.id}`

        Args:
            departments (Sequence[:obj:`Department`]): A list of
                :obj:`Department` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (:obj:`int`, optional): An id of a department in
                :paramref:`departments` to mark as selected. This will produce a
                green checkmark next to the button title.

        """
        buttons = [
            InlineKeyboardButton(
                department.get_name(self._language_code)
                + (" ✅" if department.id == selected_id else ""),
                callback_data=f"{url}{sep}{department.id}",
            )
            for department in departments
        ]

        _ = self._gettext
        if include_none_department:
            buttons += [
                InlineKeyboardButton(
                    _("General Department") + (" ✅" if selected_id == 0 else ""),
                    callback_data=f"{url}{sep}0",
                ),
            ]

        return buttons

    def programs_list(
        self,
        programs: Sequence[Program],
        url: str,
        sep: str = "/",
        selected_id: Optional[int] = None,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model :class:`Program`
        with `InlineKeyboardButton.text = Program.{ar/en}_name` and
        `InlineKeyboardButton.callback_data = {url}/{program.id}`

        Args:
            programs (Sequence[:obj:`Program`]): A list of :obj:`Program`
                objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (:obj:`int`, optional): An id of a program in
                :paramref:`programs` to mark as selected. This will produce a
                green checkmark next to the button title.
        """
        return [
            InlineKeyboardButton(
                program.get_name(self._language_code)
                + (" ✅" if program.id == selected_id else ""),
                callback_data=f"{url}{sep}{program.id}",
            )
            for program in programs
        ]

    def years_list(
        self,
        academic_years: Sequence[AcademicYear],
        url: str,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for
        model :class:`AcademicYear` with `InlineKeyboardButton.text =
        {AcademicYear.start} - {AcademicYear.end}` and
        `InlineKeyboardButton.callback_data = {url}/{academic_year.id}`

        Args:
            academic_years (Sequence[:obj:`AcademicYear`]): A list
                of :obj:`AcademicYear` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
        """
        return [
            InlineKeyboardButton(
                f"{year.start} - {year.end}",
                callback_data=f"{url}/{year.id}",
            )
            for year in academic_years
        ]

    def courses_list(
        self,
        courses: List[Course],
        url: str,
        sep: str = "/",
        end: str = "",
        selected_ids: Optional[List[int]] = None,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model :class:`Course` with
        `InlineKeyboardButton.text = Course.{ar/en}_name` and
        `InlineKeyboardButton.callback_data = {url}/{course.id}{end}`

        Args:
            courses (Sequence[:obj:`Course`]): A list of :obj:`Course` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            end (:obj:`str`, optional): some further :paramref:`callback_data` to append
                after `/{Course.id}`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (List[:obj:`int`], optional): An id of a course
                n :paramref:`courses` to mark as selected. This will produce a green
                checkmark next to the button title.
        """
        return [
            InlineKeyboardButton(
                course.get_name(self._language_code)
                + (" ✅" if selected_ids and course.id in selected_ids else ""),
                callback_data=f"{url}{sep}{course.id}{end}",
            )
            for course in courses
        ]

    def program_courses(
        self,
        courses: List[Course],
        url: str,
        course_semester: Dict[int, int],
        sep: str = "/",
        end: str = "",
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model :class:`Course` with
        `InlineKeyboardButton.text = Course.{ar/en}_name` and
        `InlineKeyboardButton.callback_data = {url}/{course.id}{end}`

        Args:
            courses (Sequence[:obj:`Course`]): A list of :obj:`Course` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            end (:obj:`str`, optional): some further :paramref:`callback_data` to append
                after `/{Course.id}`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (List[:obj:`int`], optional): An id of a course
                n :paramref:`courses` to mark as selected. This will produce a green
                checkmark next to the button title.
        """
        return [
            InlineKeyboardButton(
                (
                    f"[{course_semester[course.id]}] "
                    if course.id in course_semester
                    else ""
                )
                + f"{course.get_name(self._language_code)}",
                callback_data=f"{url}{sep}{course.id}",
            )
            for course in courses
        ]

    def update_to_semester(self, url: str, semester_number: int):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Update to Semeter {}").format(semester_number), callback_data=url
        )

    def program_semester_courses_list(
        self,
        program_semester_courses: List[ProgramSemesterCourse],
        url: str,
        sep: str = "/",
        end: Union[str, Callable[[ProgramSemesterCourse], str]] = "",
        selected_ids: Optional[List[int]] = None,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model :class:`Course` with
        `InlineKeyboardButton.text = Course.{ar/en}_name` and
        `InlineKeyboardButton.callback_data = {url}/{program_semester_course.id}{end}`

        Args:
            courses (Sequence[:obj:`Course`]): A list of :obj:`Course` objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
            end (:obj:`str`, optional): some further :paramref:`callback_data` to append
                after `/{Course.id}`.
            sep (:obj:`str`): String to append  to :paramref:`url`. Defaults to `"\\"`
            selected_id (List[:obj:`int`], optional): An id of a course
                n :paramref:`courses` to mark as selected. This will produce a green
                checkmark next to the button title.
        """
        buttons = []
        for psc in program_semester_courses:
            end_ = end(psc) if end and callable(end) else end
            buttons.append(
                InlineKeyboardButton(
                    psc.course.get_name(self._language_code)
                    + (" ✅" if selected_ids and psc.id in selected_ids else ""),
                    callback_data=f"{url}{sep}{psc.id}{end_}",
                )
            )
        return buttons

    def enrollments_list(
        self,
        enrollments: Sequence[Enrollment],
        url: str,
    ):
        """Builds a list of :class:`InlineKeyboardButton` for model :class:`Enrollment`
        with:
        * `text = {enrollment.academic_year.start} - {enrollment.academic_year.end}`
        * `callback_data = {url}/{enrollment.id}`

        Args:
            enrollments (Sequence[:obj:`Program`]): A list of :obj:`Enrollment`
                objects
            url (:obj:`str`): Callback data to be passed to
                `InlineKeyboardButton.callback_data`.
        """
        return [
            InlineKeyboardButton(
                f"{enrollment.academic_year.start} - {enrollment.academic_year.end}",
                callback_data=f"{url}/{enrollment.id}",
            )
            for enrollment in enrollments
        ]

    # TODO: add docs
    def material(self, url: str, material: Material):
        _ = self._gettext
        type_: str = material.type
        text: str = None
        if isinstance(material, HasNumber):
            text = _(type_) + " " + str(material.number)
        elif isinstance(material, SingleFile):
            text = material.file.name
        elif isinstance(material, Review):
            text = material.get_name(self._language_code) + (
                " " + str(d.year) if (d := material.date) else ""
            )
        return InlineKeyboardButton(
            text,
            callback_data=f"{url}/{material.id}",
        )

    # TODO: add docs
    def material_list(self, url: str, materials: List[Material]):
        return [self.material(url, m) for m in materials]

    # TODO: add docs
    def material_groups(
        self, url: str, groups: List[MaterialType]
    ) -> List[List[InlineKeyboardButton]]:
        _ = self._gettext
        keyboard: List[List[InlineKeyboardButton]] = []
        first_row = []
        second_row = []
        third_row = []
        for group in groups:
            if group in [
                MaterialType.LECTURE,
                MaterialType.TUTORIAL,
                MaterialType.LAB,
            ]:
                first_row.append(
                    InlineKeyboardButton(
                        _(f"{group}s"),
                        callback_data=f"{url}/{group}",
                    )
                )
            if group in [
                MaterialType.REFERENCE,
                MaterialType.SHEET,
                MaterialType.TOOL,
            ]:
                second_row.append(
                    InlineKeyboardButton(
                        _(f"{group}s"),
                        callback_data=f"{url}/{group}",
                    )
                )
            if group == MaterialType.ASSIGNMENT:
                third_row.append(
                    InlineKeyboardButton(
                        _(f"{group}s"),
                        callback_data=f"{url}/{group}",
                    )
                )
            if group == MaterialType.REVIEW:
                title = f"{group}s" if self._language_code == constants.AR else group
                third_row.append(
                    InlineKeyboardButton(
                        _(title),
                        callback_data=f"{url}/{group}",
                    )
                )
        first_row and keyboard.append(first_row)
        second_row and keyboard.append(second_row)
        third_row and keyboard.append(third_row)
        for row in keyboard:
            if self._language_code == constants.AR:
                row.reverse()
        return keyboard

    def files_list(self, url: str, files: List[File]):
        return [
            InlineKeyboardButton(
                f"{file.name}",
                callback_data=f"{url}/{file.id}",
            )
            for file in files
        ]

    def disenroll(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Disenroll"), callback_data=url)

    def arabic(self, url: str, selected: bool):
        return InlineKeyboardButton(
            "العربية" + (" ✅" if selected else ""), callback_data=url
        )

    def english(self, url: str, selected: bool):
        return InlineKeyboardButton(
            "English" + (" ✅" if selected else ""), callback_data=url
        )

    def notification_setting_item(
        self, setting_key: SettingKey, url: str, selected: bool
    ):
        _ = self._gettext
        key: str = setting_key.value[0]
        type_ = key.replace(SettingKey.NOTIFICATION_PREFIX.value, "")
        return InlineKeyboardButton(
            _(type_) + (" ✅" if selected else ""),
            callback_data=url,
        )

    def disable_all(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Disable All"), callback_data=url)

    def submit_proof(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Submit Proof"), callback_data=url)

    def contact_support(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Contact"),
            url=url,
        )

    def grant_access(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Grant Access"), callback_data=url)

    def reject(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Reject"), callback_data=url)

    def unlink_course(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Unlink Course"), callback_data=url)

    def link_course(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Link Course"), callback_data=url)

    def optional(self, url: str, selected: bool):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Optional") + (" ✅" if selected else ""), callback_data=url
        )

    def required(self, url: str, selected: bool):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Required") + (" ✅" if selected else ""), callback_data=url
        )

    def next_page(self, callback_data: str):
        """Create an :class:`InlineKeyboardButton` with text `>>`.

        Args:
            callback_data (:obj:`str`): the :paramref:`callback_data` of the button

        Returns:
            :class:`InlineKeyboardButton`
        """
        _ = self._gettext
        return InlineKeyboardButton(
            _("next-page-symbol"),
            callback_data=callback_data,
        )

    def previous_page(self, callback_data: str):
        """Create an :class:`InlineKeyboardButton` with text  `<<`.

        Args:
            callback_data (:obj:`str`): the :paramref:`callback_data` of the button

        Returns:
            :class:`InlineKeyboardButton`
        """
        _ = self._gettext
        return InlineKeyboardButton(
            _("prev-page-symbol"),
            callback_data=callback_data,
        )

    def add(self, callback_data: str, text: str):
        """Create an :class:`InlineKeyboardButton` with text  `Add <something>`,
        and append `/constants.ADD` to the :paramref:`callback_data`.

        Args:
            callback_data (:obj:`str`): the :paramref:`callback_data` of the button
            text (:obj:`str`): The thing to edit. This will appear in the button text.

        Returns:
            :class:`InlineKeyboardButton`
        """
        _ = self._gettext
        return InlineKeyboardButton(
            _("Add {}").format(text),
            callback_data=f"{callback_data}/{constants.ADD}",
        )

    def edit(self, callback_data: str, text: str, end: str = ""):
        """Create an :class:`InlineKeyboardButton` with text  `Edit <something>`,
        and append `/constants.EDIT` to the :paramref:`callback_data`.

        Args:
            callback_data (:obj:`str`): the :paramref:`callback_data` of the button
            text (:obj:`str`): The thing to edit. This will appear in the button text.
            end (:obj:`str`, optional): some further :paramref:`callback_data` to append
                after `/constants.EDIT`.

        Returns:
            :class:`InlineKeyboardButton`
        """
        _ = self._gettext
        return InlineKeyboardButton(
            _("Edit {}").format(text),
            callback_data=f"{callback_data}/{constants.EDIT}{end}",
        )

    def delete(self, callback_data: str, text: str = ""):
        """Create an :class:`InlineKeyboardButton` with text  `Delete <something>`,
        and append `/constants.DELETE` to the :paramref:`callback_data`.

        Args:
            callback_data (:obj:`str`): the :paramref:`callback_data` of the button
            text (:obj:`str`, optional): The thing to edit. This will appear
                in the button text.

        Returns:
            :class:`InlineKeyboardButton`
        """
        _ = self._gettext
        title = _("Delete") if not text else _("Delete {}").format(text)
        return InlineKeyboardButton(
            title,
            callback_data=f"{callback_data}/{constants.DELETE}",
        )

    def publish(self, callback_data: str):
        """Create an :class:`InlineKeyboardButton` with text  `Publish`,
        and append `/constants.PUBLISH` to the :paramref:`callback_data`.

        Args:
            callback_data (:obj:`str`): the :paramref:`callback_data` of the button

        Returns:
            :class:`InlineKeyboardButton`
        """
        _ = self._gettext
        return InlineKeyboardButton(
            _("Publish"),
            callback_data=f"{callback_data}/{constants.PUBLISH}",
        )

    def source(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Source"), url=url)

    # TODO: come here
    def review_types(self, url: str):
        return [
            InlineKeyboardButton(
                get_review_type_name(t, self._language_code),
                callback_data=f"{url}?t={key}",
            )
            for key, t in REVIEW_TYPES.items()
        ]

    def carriculum(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Carriculam"),
            callback_data=url,
        )

    def activate(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Activate"), callback_data=url)

    def deactivate(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Deactivate"), callback_data=url)

    def send_all(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Get All"),
            callback_data=f"{url}/{constants.ALL}",
        )

    def view_source(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Source"), url=url)

    def language(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Language"), callback_data=url)

    def notifications(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Notifications"), callback_data=url)

    def with_notification(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Notify"), callback_data=f"{url}?n=1")

    def without_notification(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(_("Don't Notify"), callback_data=f"{url}?n=0")

    def revoke(self, url: str):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Revoke Access"), callback_data=f"{url}/{constants.REVOKE}"
        )

    def back(
        self,
        url: Optional[str] = None,
        pattern: Optional[str] = None,
        text: str = "",
        absolute_url: Optional[str] = None,
    ):
        if absolute_url and url:
            raise RuntimeError("can't set both url and absolute_url")
        if not url and not absolute_url:
            raise RuntimeError(
                "must provide either url (with pattern) or an absolute_url"
            )

        data = absolute_url or re.sub(pattern, "", url)
        _ = self._gettext
        if text.startswith("ال"):
            text = text[1:]
        title = _("Back") if not text else _("Back to {}").format(text)
        return InlineKeyboardButton(
            title,
            callback_data=data,
        )

    def add_file(self, url: str):
        _ = self._gettext
        return self.add(url, _("File"))

    # TODO: come here
    def view_added(
        self,
        id: Optional[int | str] = None,
        url: Optional[str] = None,
        text: str = "",
        absolute_url: Optional[str] = None,
    ):
        if absolute_url and url:
            raise RuntimeError("can't set both url and absolute_url")
        if not url and not absolute_url:
            raise RuntimeError(
                "must provide either url (with pattern) or an absolute_url"
            )

        data = absolute_url or re.sub(rf"/{constants.ADD}$", f"/{id}", url)
        return InlineKeyboardButton(
            f"View{(' ' + text) if text else ''}",
            callback_data=data,
        )

    def display(self, callback_data: str):
        _ = self._gettext
        return InlineKeyboardButton(
            _("Display"), callback_data=f"{callback_data}/{constants.DISPLAY}"
        )

    def show_more(self, callback_data: str):
        _ = self._gettext
        return InlineKeyboardButton(
            "⇣ " + _("Show More"),
            callback_data=callback_data,
        )

    def show_less(self, callback_data: str):
        _ = self._gettext
        return InlineKeyboardButton(
            "⇡ " + _("Show Less"),
            callback_data=callback_data,
        )

    def file_menu(self, url: str, can_publish: bool = False):
        _ = self._gettext
        buttons = [
            self.display(url),
            self.delete(callback_data=url),
            self.edit(f"{url}/{constants.SOURCE}", _("Source")),
        ]
        if can_publish:
            buttons.insert(1, self.publish(callback_data=url))
        return buttons

    def delete_group(self, url: str):
        _ = self._gettext
        d_type = re.search(f"{constants.DELETE}|{constants.REVOKE}", url).group()
        buttons = [
            InlineKeyboardButton(
                (_("Yes that's correct")),
                callback_data=f"{url}?c=0",
            ),
            InlineKeyboardButton(
                _("Nope"),
                callback_data=re.sub(rf"/{d_type}", "", url),
            ),
            InlineKeyboardButton(
                _("No"),
                callback_data=re.sub(rf"/{d_type}", "", url),
            ),
        ]
        random.shuffle(buttons)
        buttons += [self.back(pattern=rf"/{d_type}", url=url)]
        return buttons

    def confirm_delete_group(self, url: str):
        _ = self._gettext
        d_type = re.search(f"{constants.DELETE}|{constants.REVOKE}", url).group()
        buttons = [
            InlineKeyboardButton(
                _("Yes, I'm 100% sure!"),
                callback_data=f"{url}?c=1",
            ),
            InlineKeyboardButton(
                _("No"),
                callback_data=re.sub(rf"/{d_type}", "", url),
            ),
            InlineKeyboardButton(
                _("Hell no"),
                callback_data=re.sub(rf"/{d_type}", "", url),
            ),
        ]
        random.shuffle(buttons)
        buttons += [self.back(pattern=rf"/{d_type}", url=url)]
        return buttons

    class Picker(NamedTuple):
        keyboard: List[List[InlineKeyboardButton]]
        date_time: Optional[datetime]

    def datepicker(self, match: re.Match, selected: Optional[date] = None) -> Picker:
        url = re.search(
            rf".*/{constants.EDIT}/{constants.DEADLINE}", match.group()
        ).group()

        year, month, day = (
            int(y) if (y := match.group("y")) else None,
            int(m) if (m := match.group("m")) else None,
            int(d) if (d := match.group("d")) else None,
        )
        today = date.today()
        if not year and not month and not day:
            if not selected:
                year, month = today.year, today.month
            elif selected:
                year, month = selected.year, selected.month

        keyboard: List[List[InlineKeyboardButton]] = None
        date_time: datetime = None
        _ = self._gettext
        if year and month and not day:
            currentmonth = date(year, month, 15)
            nextmonth = currentmonth + timedelta(days=31)
            prevmonth = currentmonth - timedelta(days=31)
            monthcalendar = calendar.monthcalendar(year, month)
            weekdays = [
                _("Sun"),
                _("Mon"),
                _("Tue"),
                _("Wed"),
                _("Thu"),
                _("Fri"),
                _("Sat"),
            ]
            keyboard = build_menu(
                [
                    InlineKeyboardButton(
                        _("prev-page-symbol"),
                        callback_data=f"{url}?y={prevmonth.year}&m={prevmonth.month}",
                    ),
                    InlineKeyboardButton(
                        format_date(currentmonth, "MMM Y", locale=self._language_code),
                        callback_data=f"{url}?y={year}",
                    ),
                    InlineKeyboardButton(
                        _("next-page-symbol"),
                        callback_data=f"{url}?y={nextmonth.year}&m={nextmonth.month}",
                    ),
                ],
                3,
                reverse=self._language_code == constants.AR,
            )
            keyboard += build_menu(
                [
                    InlineKeyboardButton(
                        day,
                        callback_data=f"{url}/{constants.IGNORE}",
                    )
                    for day in weekdays
                ],
                7,
                reverse=self._language_code == constants.AR,
            )
            for week in monthcalendar:
                keyboard += build_menu(
                    [
                        InlineKeyboardButton(
                            (
                                str(day)
                                + (
                                    " " + "⚪️"
                                    if date(year, month, day) == today
                                    else ""
                                )
                                + (
                                    " " + "✅"
                                    if date(year, month, day) == selected
                                    else ""
                                )
                                if day
                                else " "
                            ),
                            callback_data=(
                                f"{url}?y={year}&m={month}&d={day}"
                                if day
                                else f"{url}/{constants.IGNORE}"
                            ),
                        )
                        for day in week
                    ],
                    7,
                    reverse=self._language_code == constants.AR,
                )
        elif year and not month and not day:
            menu = [
                InlineKeyboardButton(
                    month,
                    callback_data=f"{url}?y={year}&m={i+1}",
                )
                for i, month in enumerate(
                    [
                        _("January"),
                        _("February"),
                        _("March"),
                        _("April"),
                        _("May"),
                        _("June"),
                        _("July"),
                        _("August"),
                        _("September"),
                        _("October"),
                        _("November"),
                        _("December"),
                    ]
                )
            ]
            keyboard = build_menu(menu, 3, reverse=self._language_code == constants.AR)
            keyboard += build_menu(
                [
                    InlineKeyboardButton(
                        _("prev-page-symbol"),
                        callback_data=f"{url}?y={year-1}",
                    ),
                    InlineKeyboardButton(
                        year,
                        callback_data=f"{url}?y={year}&m={1}",
                    ),
                    InlineKeyboardButton(
                        _("next-page-symbol"),
                        callback_data=f"{url}?y={year+1}",
                    ),
                ],
                3,
                reverse=self._language_code == constants.AR,
            )
        if day:
            date_time = datetime(year, month, day)
        return self.Picker(keyboard=keyboard, date_time=date_time)


en_buttons = Buttons(constants.EN)
ar_buttons = Buttons(constants.AR)
