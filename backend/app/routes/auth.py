"""Register, log in, who am I, delete my account."""
from fastapi import APIRouter, Depends, HTTPException, Request

from .. import db
from ..config import get_settings
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut
from ..security import DUMMY_HASH, create_token, current_user, hash_password, throttle, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _out(user: dict) -> UserOut:
    return UserOut(id=user["id"], email=user["email"], display_name=user["display_name"], created_at=user["created_at"])


def _issue(user: dict) -> AuthResponse:
    return AuthResponse(access_token=create_token(user["id"]), user=_out(user))


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(req: RegisterRequest) -> AuthResponse:
    if not get_settings().allow_registration:
        raise HTTPException(403, "Registration is closed on this server.")
    name = req.display_name.strip() or req.email.split("@")[0]
    user = db.create_user(req.email, name, hash_password(req.password))
    if user is None:
        raise HTTPException(409, "An account with that email already exists. Try logging in.")
    return _issue(user)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request) -> AuthResponse:
    key = f"{req.email}|{request.client.host if request.client else '?'}"
    throttle.check(key)
    user = db.get_user_by_email(req.email)
    ok = verify_password(req.password, user["password_hash"] if user else DUMMY_HASH)
    if not user or not ok:
        throttle.fail(key)
        raise HTTPException(401, "Wrong email or password.")
    throttle.clear(key)
    return _issue(user)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> UserOut:
    return _out(user)


@router.delete("/me", status_code=204)
def delete_me(user: dict = Depends(current_user)) -> None:
    """Deletes the account and everything it owns: drafts, runs, reactions and verdicts."""
    db.delete_user(user["id"])
