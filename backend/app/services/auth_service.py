from __future__ import annotations

from typing import Callable


def register_user(users_col, user_payload, password_hasher: Callable[[str], str]):
    """Register a user and return a API-style response dict."""
    if users_col.find_one({"email": user_payload.email}):
        return {"success": False, "msg": "이미 가입된 이메일입니다."}

    users_col.insert_one(
        {
            "username": user_payload.username,
            "email": user_payload.email,
            "password": password_hasher(user_payload.password),
            "created_at": __import__("datetime").datetime.now().isoformat(),
        }
    )
    return {"success": True, "msg": "회원가입 성공!"}


def login_user(users_col, user_payload, password_verifier: Callable[[str, str], bool]):
    """Verify user credentials."""
    user = users_col.find_one({"email": user_payload.email})
    if not user:
        return {"success": False, "msg": "존재하지 않는 이메일입니다."}

    if not password_verifier(user_payload.password, user["password"]):
        return {"success": False, "msg": "비밀번호가 일치하지 않습니다."}

    return {
        "success": True,
        "user": {
            "username": user["username"],
            "email": user["email"],
        },
    }


def issue_temp_password(users_col, payload, password_hasher: Callable[[str], str], temp_password: str):
    """Issue temporary password (simple deterministic default in this project)."""
    if not users_col.find_one({"email": payload.email}):
        return {"success": False, "msg": "등록되지 않은 이메일입니다."}

    users_col.update_one(
        {"email": payload.email},
        {"$set": {"password": password_hasher(temp_password)}},
    )
    return {
        "success": True,
        "msg": "임시 비밀번호가 발급되었습니다.",
        "temp_password": temp_password,
    }


def change_password(users_col, payload, password_verifier: Callable[[str, str], bool], password_hasher: Callable[[str], str]):
    user = users_col.find_one({"email": payload.email})
    if not user:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    if not password_verifier(payload.current_password, user["password"]):
        return {"success": False, "msg": "현재 비밀번호가 일치하지 않습니다."}

    users_col.update_one(
        {"email": payload.email},
        {"$set": {"password": password_hasher(payload.new_password)}},
    )
    return {"success": True, "msg": "비밀번호가 성공적으로 변경되었습니다."}
