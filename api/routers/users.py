from fastapi import APIRouter, Depends, HTTPException,status
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.users import User
from api.schemes.users import ModifyUser
from api.get_current_user import get_current_user


router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
def createUser(payload:ModifyUser, db:Session = Depends(get_db)):
    if payload:
        user = User(
            name = payload.name,
            email = payload.email
        )
        try: 
            db.add(user)
            db.commit()
            db.refresh(user)
        except Exception as e:
            raise HTTPException(
                status_code= status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail= str(e)
            )
        return user
    else:
        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST
        )

@router.get("/")
def getUser(db: Session = Depends( get_db)):
    user=db.query(User).all()
    return user



@router.patch("/")
def updateUser(payload: ModifyUser , db: Session =Depends(get_db), current_user: User = Depends(get_current_user)):
    if payload:
        current_user.name = payload.name
        current_user.email =payload.email
        try:
            db.commit()
            db.refresh(current_user)
        except Exception as e:
            raise HTTPException(
                status_code= status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail= str(e)
            )   
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
        )
    return current_user
    
@router.delete("/{userId}")
def deleteUser(userId: str, db:Session = Depends(get_db), current_user = Depends(get_current_user)):
    if userId:
        user = db.query(User).filter(User.id == userId).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        try: 
            db.delete(user)
            db.commit()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    else:
        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST
        )
    return {"deleted": userId}
