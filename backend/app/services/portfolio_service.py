from __future__ import annotations

import datetime as dt


def get_portfolio(users_col, email: str):
    user = users_col.find_one({"email": email})
    if not user:
        return {"success": False, "portfolio": []}
    return {"success": True, "portfolio": user.get("portfolio", [])}


def add_portfolio_item(users_col, email: str, symbol: str, price: float, quantity: int):
    user = users_col.find_one({"email": email})
    if not user:
        return {"success": False, "msg": "User not found"}

    portfolio = user.get("portfolio", [])
    symbol_upper = symbol.upper()
    new_item = {
        "symbol": symbol_upper,
        "price": price,
        "quantity": quantity,
        "date": dt.datetime.now().strftime("%Y-%m-%d"),
    }

    portfolio = [p for p in portfolio if p.get("symbol") != symbol_upper]
    portfolio.append(new_item)
    users_col.update_one({"email": email}, {"$set": {"portfolio": portfolio}})
    return {
        "success": True,
        "msg": "포트폴리오에 추가되었습니다.",
        "portfolio": portfolio,
    }


def remove_portfolio_item(users_col, email: str, symbol: str):
    users_col.update_one(
        {"email": email},
        {"$pull": {"portfolio": {"symbol": symbol.upper()}}},
    )
    return {"success": True, "msg": "삭제되었습니다."}
