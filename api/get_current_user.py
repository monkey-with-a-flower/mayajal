from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.users import User


def get_current_user(db: Session = Depends(get_db)):
    current_user = db.query(User).first()
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create a user before managing labs.",
        )
    return current_user
