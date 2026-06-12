import datetime as dt
from typing import Optional
import yfinance as yf
from bson import ObjectId
from fastapi import HTTPException
from .db import users_col, portfolio_col, transactions_col, auto_trade_col
from .utils import (
    calculate_profit_rate,
    calculate_evaluation_amount,
    hash_pin,
    verify_pin,
)

def get_current_stock_price(symbol: str):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="1d", interval="1m")

    if hist.empty:
        raise HTTPException(status_code=404, detail="주가 데이터를 찾을 수 없습니다.")

    current_price = float(hist["Close"].dropna().iloc[-1])

#    return {
#       "symbol": symbol.upper(),
#       "company_name": symbol.upper(),
#       "current_price": current_price,
#    }

    return {
        "symbol": symbol.upper(),
        "company_name": symbol.upper(),
        "current_price": current_price,
    }


def _serialize_user(doc):
    if not doc:
        return None
    return {
        "_id": str(doc["_id"]),
        "nickname": doc.get("nickname", ""),
        "email": doc.get("email"),
        "virtual_cash": doc.get("virtual_cash", 0),
        "initial_seed_money": doc.get("initial_seed_money", 0),
    }


def create_account(nickname: str, email: Optional[str], pin: str, initial_cash: float = 10000000):
    if users_col is None:
        raise HTTPException(status_code=500, detail="MongoDB가 설정되지 않았습니다.")

    if email:
        existing = users_col.find_one({"email": email})
        if existing:
            user_id = str(existing["_id"])
            portfolio_col.delete_many({"user_id": user_id})
            transactions_col.delete_many({"user_id": user_id})
            users_col.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "nickname": nickname,
                        "virtual_cash": initial_cash,
                        "initial_seed_money": initial_cash,
                        "pin_hash": hash_pin(pin),
                    }
                },
            )
            return _serialize_user(users_col.find_one({"_id": existing["_id"]}))

    doc = {
        "nickname": nickname,
        "email": email,
        "virtual_cash": initial_cash,
        "initial_seed_money": initial_cash,
        "pin_hash": hash_pin(pin),
    }
    result = users_col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    # 응답에는 pin_hash 안 보여주기
    doc.pop("pin_hash", None)
    return doc


def get_account_by_email(email: str):
    if users_col is None:
        raise HTTPException(status_code=500, detail="MongoDB가 설정되지 않았습니다.")

    user = users_col.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return _serialize_user(user)


def buy_stock(user_id: str, symbol: str, quantity: int, pin: str, price: Optional[float] = None):
    if users_col is None:
        raise HTTPException(status_code=500, detail="MongoDB가 설정되지 않았습니다.")

    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

    if not verify_pin(pin, user.get("pin_hash", "")):
        raise HTTPException(status_code=403, detail="PIN 번호가 올바르지 않습니다.")

    stock = (
        {"symbol": symbol.upper(), "company_name": symbol.upper(), "current_price": float(price)}
        if price
        else get_current_stock_price(symbol)
    )
    price = float(price or stock["current_price"])

    fee_rate = 0.0005
    total_amount = price * quantity
    fee = int(total_amount * fee_rate)
    total_cost = total_amount + fee

    if user["virtual_cash"] < total_cost:
        raise HTTPException(status_code=400, detail="가상머니가 부족합니다.")

    portfolio = portfolio_col.find_one({
        "user_id": user_id,
        "symbol": stock["symbol"]
    })

    if not portfolio:
        portfolio = {
            "user_id": user_id,
            "symbol": stock["symbol"],
            "company_name": stock["company_name"],
            "quantity": 0,
            "avg_price": 0.0,
        }

    new_total_quantity = portfolio["quantity"] + quantity
    new_avg_price = (
        (portfolio["quantity"] * portfolio["avg_price"]) + total_amount
    ) / new_total_quantity

    portfolio["quantity"] = new_total_quantity
    portfolio["avg_price"] = new_avg_price
    portfolio["last_price"] = price

    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"virtual_cash": user["virtual_cash"] - total_cost}},
    )

    portfolio_col.update_one(
        {"user_id": user_id, "symbol": stock["symbol"]},
        {"$set": portfolio},
        upsert=True,
    )

    transactions_col.insert_one({
        "user_id": user_id,
        "symbol": stock["symbol"],
        "company_name": stock["company_name"],
        "type": "BUY",
        "quantity": quantity,
        "price": price,
        "total_amount": total_amount,
        "fee": fee,
        "created_at": dt.datetime.utcnow().isoformat(),
    })

    return {
        "symbol": stock["symbol"],
        "price": price,
        "quantity": quantity,
        "fee": fee,
    }


def sell_stock(user_id: str, symbol: str, quantity: int, pin: str, price: Optional[float] = None):
    if users_col is None:
        raise HTTPException(status_code=500, detail="MongoDB가 설정되지 않았습니다.")

    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

    if not verify_pin(pin, user.get("pin_hash", "")):
        raise HTTPException(status_code=403, detail="PIN 번호가 올바르지 않습니다.")

    stock = (
        {"symbol": symbol.upper(), "company_name": symbol.upper(), "current_price": float(price)}
        if price
        else get_current_stock_price(symbol)
    )
    price = float(price or stock["current_price"])

    portfolio = portfolio_col.find_one({
        "user_id": user_id,
        "symbol": stock["symbol"]
    })

    if not portfolio:
        raise HTTPException(status_code=404, detail="보유 중인 종목이 없습니다.")

    if portfolio["quantity"] < quantity:
        raise HTTPException(status_code=400, detail="매도 수량이 보유 수량보다 많습니다.")

    fee_rate = 0.0005
    total_amount = price * quantity
    fee = int(total_amount * fee_rate)
    final_received = total_amount - fee

    new_quantity = portfolio["quantity"] - quantity

    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"virtual_cash": user["virtual_cash"] + final_received}},
    )

    if new_quantity == 0:
        portfolio_col.delete_one({"_id": portfolio["_id"]})
    else:
        portfolio_col.update_one(
            {"_id": portfolio["_id"]},
            {"$set": {"quantity": new_quantity, "last_price": price}},
        )

    transactions_col.insert_one({
        "user_id": user_id,
        "symbol": stock["symbol"],
        "company_name": stock["company_name"],
        "type": "SELL",
        "quantity": quantity,
        "price": price,
        "total_amount": total_amount,
        "fee": fee,
        "created_at": dt.datetime.utcnow().isoformat(),
    })

    return {
        "symbol": stock["symbol"],
        "price": price,
        "quantity": quantity,
        "fee": fee,
    }


def get_portfolio(user_id: str):
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

    portfolios = list(portfolio_col.find({"user_id": user_id}))

    total_stock_value = 0
    result = []

    for item in portfolios:
        try:
            stock = get_current_stock_price(item["symbol"])
            current_price = stock["current_price"]
        except HTTPException:
            current_price = item.get("last_price") or item.get("avg_price") or 0
        evaluation_amount = calculate_evaluation_amount(item["quantity"], current_price)
        profit_rate = calculate_profit_rate(item["avg_price"], current_price)
        profit_amount = evaluation_amount - (item["quantity"] * item["avg_price"])
        total_stock_value += evaluation_amount

        result.append({
            "symbol": item["symbol"],
            "company_name": item.get("company_name", ""),
            "quantity": item["quantity"],
            "avg_price": item["avg_price"],
            "current_price": current_price,
            "evaluation_amount": evaluation_amount,
            "profit_amount": profit_amount,
            "profit_rate": profit_rate,
        })

    total_asset = user["virtual_cash"] + total_stock_value
    total_profit = total_asset - user["initial_seed_money"]
    total_profit_rate = (total_profit / user["initial_seed_money"]) * 100

    return {
        "cash": user["virtual_cash"],
        "total_stock_value": total_stock_value,
        "total_asset": total_asset,
        "total_profit": total_profit,
        "total_profit_rate": total_profit_rate,
        "portfolios": result,
    }


def get_transaction_history(user_id: str):
    history = list(transactions_col.find({"user_id": user_id}, {"_id": 0}))
    return history


def create_auto_trade(user_id: str, symbol: str, trade_type: str, target_price: float, quantity: int):
    doc = {
        "user_id": user_id,
        "symbol": symbol.upper(),
        "type": trade_type,
        "target_price": target_price,
        "quantity": quantity,
        "status": "PENDING",
    }
    result = auto_trade_col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


def get_auto_trades(user_id: str):
    rows = list(auto_trade_col.find({"user_id": user_id}))
    for row in rows:
        row["_id"] = str(row["_id"])
    return rows
