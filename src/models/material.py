import gettext
from datetime import date as datetype
from datetime import datetime
from enum import unique
from typing import TYPE_CHECKING, ClassVar, Dict, List, Sequence, Type

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from telegram.constants import InputMediaType

from src import constants
from src.enum import StringEnum

from .base import Base

if TYPE_CHECKING:
    from .academic_year import AcademicYear
    from .course import Course
    from .file import File


@unique
class MaterialType(StringEnum):
    LECTURE = gettext.gettext("lecture")
    gettext.gettext("lectures")

    TUTORIAL = gettext.gettext("tutorial")
    gettext.gettext("tutorials")

    LAB = gettext.gettext("lab")
    gettext.gettext("labs")

    REFERENCE = gettext.gettext("reference")
    gettext.gettext("references")

    SHEET = gettext.gettext("sheet")
    gettext.gettext("sheets")

    TOOL = gettext.gettext("tool")
    gettext.gettext("tools")

    ASSIGNMENT = gettext.gettext("assignment")
    gettext.gettext("assignments")

    REVIEW = gettext.gettext("review")
    gettext.gettext("reviews")


class Material(Base):
    __tablename__ = "material"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    type: Mapped[str] = mapped_column(init=False)

    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_year.id"), nullable=False
    )
    published: Mapped[bool] = mapped_column(Boolean, nullable=False)

    course: Mapped["Course"] = relationship(init=False)
    academic_year: Mapped["AcademicYear"] = relationship(init=False)

    __mapper_args__: ClassVar[Dict[str, str]] = {
        "polymorphic_identity": "material",
        "polymorphic_on": "type",
    }

    MEDIA_TYPES: Sequence[InputMediaType]
    """This class property must be overwritten."""

    def __repr__(self) -> str:
        return (
            f"Material(id={self.id!r}, published={self.published!r}"
            " course={self.course!r}, academic_year={self.academic_year!r})"
        )


# Material subclass foreign key
class HasId:
    id: Mapped[int] = mapped_column(
        ForeignKey("material.id"), primary_key=True, init=False
    )


# number mixin
class HasNumber:
    number: Mapped[int] = mapped_column(Integer, nullable=False, default=None)


# files relationship mixin
class RefFilesMixin:
    @declared_attr
    def files(cls) -> Mapped[list["File"]]:
        return relationship(init=False, cascade="all, delete-orphan")


class Lecture(HasId, Material, HasNumber, RefFilesMixin):
    __tablename__ = "lecture"
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.LECTURE
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (
        InputMediaType.DOCUMENT,
        InputMediaType.VIDEO,
    )


class Tutorial(HasId, Material, HasNumber, RefFilesMixin):
    __tablename__ = "tutorial"
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.TUTORIAL
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (
        InputMediaType.DOCUMENT,
        InputMediaType.VIDEO,
    )


class Lab(HasId, Material, HasNumber, RefFilesMixin):
    __tablename__ = "lab"
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.LAB
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (
        InputMediaType.DOCUMENT,
        InputMediaType.VIDEO,
    )


class Assignment(HasId, Material, HasNumber, RefFilesMixin):
    __tablename__ = "assignment"
    deadline: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=None, sort_order=999
    )
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.ASSIGNMENT
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (
        InputMediaType.DOCUMENT,
        InputMediaType.PHOTO,
    )


# single file mixin
class SingleFile:
    file_id: Mapped[int] = mapped_column(
        ForeignKey("file.id"),
        default=None,
        unique=True,
        nullable=False,
    )

    @declared_attr
    def file(cls) -> Mapped["File"]:
        return relationship(default=None, cascade="all")


class Reference(HasId, Material, SingleFile):
    __tablename__ = "reference"
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.REFERENCE
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (InputMediaType.DOCUMENT,)


class Sheet(HasId, Material, SingleFile):
    __tablename__ = "sheet"
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.SHEET
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (InputMediaType.DOCUMENT,)


class Tool(HasId, Material, SingleFile):
    __tablename__ = "tool"
    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.TOOL
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (InputMediaType.DOCUMENT,)


REVIEW_TYPES = {
    "final": {"en_name": "Final", "ar_name": "نهائي"},
    "midterm": {"en_name": "Midterm", "ar_name": "نصفي"},
    "test": {"en_name": "Test", "ar_name": "اختبار"},
    "quiz": {"en_name": "Quiz", "ar_name": "كويز"},
}


def get_review_type_name(review_type: dict, language_code: str):
    return (
        review_type["ar_name"]
        if language_code == constants.AR
        else review_type["en_name"]
    )


class Review(HasId, Material, RefFilesMixin):
    __tablename__ = "review"
    en_name: Mapped[str] = mapped_column(
        String(30), nullable=False, default=None, sort_order=998
    )
    ar_name: Mapped[str] = mapped_column(
        String(30), nullable=False, default=None, sort_order=999
    )
    date: Mapped[datetype] = mapped_column(
        Date, nullable=True, default=None, sort_order=997
    )

    def get_name(self, language_code: str):
        return self.ar_name if language_code == constants.AR else self.en_name

    __mapper_args__: ClassVar[dict[str, MaterialType]] = {
        "polymorphic_identity": MaterialType.REVIEW
    }

    MEDIA_TYPES: Sequence[InputMediaType] = (
        InputMediaType.DOCUMENT,
        InputMediaType.PHOTO,
    )


__classes__: List[Type[Material]] = [
    Lecture,
    Tutorial,
    Lab,
    Reference,
    Sheet,
    Tool,
    Assignment,
    Review,
]


def get_material_class(m_type: MaterialType) -> Type[Material]:
    for cls in __classes__:
        if cls.__mapper_args__.get("polymorphic_identity") == m_type:
            return cls
    raise KeyError(f"{m_type} has no corresponding class")
