from fastapi import APIRouter, Depends, HTTPException

from ..models import User
from ..security import DbSession, require_roles
from ..seed import reset_demo

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset(db: DbSession, user: User = Depends(require_roles("manager"))):
    reset_demo()
    return {"ok": True, "message": "演示数据已重置，请使用 operator/manager 账号重新登录查看"}
