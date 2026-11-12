from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import User
from ..security import CurrentUser, DbSession, create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }


@router.post("/login")
def login(payload: LoginIn, db: DbSession):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_access_token(user), "user": user_public(user)}


@router.get("/me")
def me(user: CurrentUser):
    return user_public(user)
