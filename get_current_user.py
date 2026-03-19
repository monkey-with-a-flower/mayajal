from fastapi import Depends, HTTPException,status
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.users import User


def get_current_user(db:Session = Depends(get_db)):


    try:
        current_user: User = db.query(User).first()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    yield current_user
    