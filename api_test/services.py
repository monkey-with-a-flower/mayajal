from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api_test.models import Lab, LabAssignment, LabSession, Role, SessionStatus, User
from api_test.config import MAYAJAL_SESSION_MAX_MINUTES


def can_manage_lab(user: User, lab: Lab) -> bool:
    return user.role == Role.admin or lab.owner_id == user.id


def require_lab_manager(user: User, lab: Lab) -> None:
    if not can_manage_lab(user, lab):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lab owner or an administrator can manage this lab.")


def require_student_access(db: Session, user: User, lab: Lab) -> None:
    if user.role != Role.student:
        return
    assignment = db.query(LabAssignment).filter(LabAssignment.lab_id == lab.id, LabAssignment.student_id == user.id).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This lab is not assigned to you.")


def start_session(db: Session, lab: Lab, student: User, session_id: str | None = None) -> LabSession:
    existing = db.query(LabSession).filter(LabSession.lab_id == lab.id, LabSession.student_id == student.id, LabSession.status == SessionStatus.running).first()
    if existing:
        return existing
    expiry = datetime.now(timezone.utc) + timedelta(minutes=MAYAJAL_SESSION_MAX_MINUTES)
    session = LabSession(id=session_id, lab_id=lab.id, student_id=student.id, status=SessionStatus.running, expires_at=expiry) if session_id else LabSession(lab_id=lab.id, student_id=student.id, status=SessionStatus.running, expires_at=expiry)
    db.add(session)
    db.flush()
    session.access_url = f"https://labs.mayajal.local/sessions/{session.id}"
    db.commit()
    db.refresh(session)
    return session


def stop_session(db: Session, session: LabSession) -> LabSession:
    session.status = SessionStatus.stopped
    session.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session
