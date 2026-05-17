"""
routers/auth.py — Authentication endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
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
    id:        int
    username:  str
    full_name: Optional[str]
    email:     Optional[str]
    phone:     Optional[str]
    timezone:  Optional[str]
    role:      str
    team:      Optional[str]
    is_active: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """Fields any user can edit on themselves."""
    phone:    Optional[str] = Field(None, max_length=50)
    timezone: Optional[str] = Field(None, max_length=100)


class UserAdminUpdate(UserProfileUpdate):
    """Extra fields only admins can edit."""
    full_name: Optional[str] = Field(None, max_length=200)
    email:     Optional[str] = Field(None, max_length=200)


def _user_dict(user: User) -> dict:
    return {
        "id":         user.id,
        "username":   user.username,
        "full_name":  user.full_name,
        "email":      user.email,
        "phone":      user.phone,
        "timezone":   user.timezone,
        "role":       user.role,
        "team":       user.team_ref.name if user.team_ref else None,
        "is_active":  user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


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
        "token_type":   "bearer",
        "user":         _user_dict(user),
    }


@router.get("/me", response_model=UserOut, summary="Get current user profile")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


@router.patch("/me", response_model=UserOut, summary="Update own phone and timezone")
def update_me(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _user_dict(current_user)


@router.patch("/users/{user_id}", response_model=UserOut, summary="Admin: update any user")
def admin_update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _user_dict(user)

