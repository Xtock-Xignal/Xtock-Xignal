from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import auth_service


class UserSignup(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserForgot(BaseModel):
    email: str


class UserChangePassword(BaseModel):
    email: str
    current_password: str
    new_password: str


def create_auth_router(get_user_collection, get_password_hash, verify_password):
    router = APIRouter()

    @router.post("/api/register")
    def register_user(user: UserSignup):
        users_col = get_user_collection()
        return auth_service.register_user(users_col, user, get_password_hash)

    @router.post("/api/login")
    def login_user(user: UserLogin):
        users_col = get_user_collection()
        return auth_service.login_user(users_col, user, verify_password)

    @router.post("/api/forgot-password")
    def forgot_password(user: UserForgot):
        users_col = get_user_collection()
        return auth_service.issue_temp_password(users_col, user, get_password_hash, temp_password="xtock1234")

    @router.post("/api/change-password")
    def change_password(req: UserChangePassword):
        users_col = get_user_collection()
        return auth_service.change_password(users_col, req, verify_password, get_password_hash)

    return router
