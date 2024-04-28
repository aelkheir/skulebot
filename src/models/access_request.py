from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enum import StringEnum

from .base import Base

if TYPE_CHECKING:
    from .enrollment import Enrollment
    from .file import File


class Status(StringEnum):
    PENDING = "pending"
    GRANTED = "granted"
    REVOKED = "revoked"
    REJECTED = "rejected"


class AccessRequest(Base):
    __tablename__ = "access_request"

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollment.id"), unique=True, nullable=False, default=None
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=None)
    verification_photo_id: Mapped[int] = mapped_column(
        ForeignKey("file.id"), nullable=True, default=None
    )

    enrollment: Mapped["Enrollment"] = relationship(
        default=None, back_populates="access_request"
    )
    verification_photo: Mapped["File"] = relationship(default=None)

    def __repr__(self) -> str:
        return (
            f"AccessRequest(id={self.id!r}, enrollment={self.enrollment_id!r},"
            f" status={self.status!r}) "
        )
