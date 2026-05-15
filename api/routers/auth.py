"""
routers/auth.py — Authentication endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from api.auth import verify_password, create_access_token, get_current_user
from api.database import get_db
from api.logger import get_logger
from api.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])
log = get_logger(__name__)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    role: str
    team: Optional[str]

    model_config = {"from_attributes": True}


@router.post("/login", response_model=TokenResponse, summary="Login and get JWT token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        log.warning("Failed login attempt", extra={"username": form_data.username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token({"sub": user.username})
    log.info("User logged in", extra={"username": user.username, "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id":        user.id,
            "username":  user.username,
            "full_name": user.full_name,
            "role":      user.role,
            "team":      user.team_ref.name if user.team_ref else None,
        },
    }


@router.get("/me", response_model=UserOut, summary="Get current user info")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id":        current_user.id,
        "username":  current_user.username,
        "full_name": current_user.full_name,
        "role":      current_user.role,
        "team":      current_user.team_ref.name if current_user.team_ref else None,
    }
