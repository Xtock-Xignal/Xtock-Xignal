from bson import ObjectId

import simulation.service as simulation_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self):
        self.rows = []

    def find_one(self, query):
        for row in self.rows:
            if self._matches(row, query):
                return row.copy()
        return None

    def insert_one(self, doc):
        row = doc.copy()
        row.setdefault("_id", ObjectId())
        self.rows.append(row)
        return FakeInsertResult(row["_id"])

    def update_one(self, query, update, upsert=False):
        for row in self.rows:
            if self._matches(row, query):
                row.update(update.get("$set", {}))
                return
        if upsert:
            row = query.copy()
            row.update(update.get("$set", {}))
            row.setdefault("_id", ObjectId())
            self.rows.append(row)

    def delete_one(self, query):
        self.rows = [row for row in self.rows if not self._matches(row, query)]

    def delete_many(self, query):
        self.rows = [row for row in self.rows if not self._matches(row, query)]

    def find(self, query, projection=None):
        rows = [row.copy() for row in self.rows if self._matches(row, query)]
        if projection and projection.get("_id") == 0:
            for row in rows:
                row.pop("_id", None)
        return rows

    def _matches(self, row, query):
        return all(row.get(key) == value for key, value in query.items())


def install_fake_simulation_db(monkeypatch):
    users = FakeCollection()
    portfolio = FakeCollection()
    transactions = FakeCollection()
    auto_trade = FakeCollection()
    monkeypatch.setattr(simulation_service, "users_col", users)
    monkeypatch.setattr(simulation_service, "portfolio_col", portfolio)
    monkeypatch.setattr(simulation_service, "transactions_col", transactions)
    monkeypatch.setattr(simulation_service, "auto_trade_col", auto_trade)
    return users, portfolio, transactions


def test_simulation_account_route_creates_and_resets_account(client, monkeypatch):
    install_fake_simulation_db(monkeypatch)

    first = client.post(
        "/api/simulation/account",
        json={
            "nickname": "tester",
            "email": "tester@example.com",
            "pin": "0000",
            "initial_cash": 5000,
        },
    )
    second = client.post(
        "/api/simulation/account",
        json={
            "nickname": "tester",
            "email": "tester@example.com",
            "pin": "0000",
            "initial_cash": 7000,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["_id"] == second.json()["data"]["_id"]
    assert second.json()["data"]["virtual_cash"] == 7000


def test_simulation_buy_uses_supplied_chart_price_and_updates_portfolio(client, monkeypatch):
    install_fake_simulation_db(monkeypatch)
    monkeypatch.setattr(
        simulation_service,
        "get_current_stock_price",
        lambda symbol: {
            "symbol": symbol.upper(),
            "company_name": symbol.upper(),
            "current_price": 100,
        },
    )

    account = client.post(
        "/api/simulation/account",
        json={
            "nickname": "tester",
            "email": "buyer@example.com",
            "pin": "0000",
            "initial_cash": 5000,
        },
    ).json()["data"]

    response = client.post(
        "/api/simulation/buy",
        json={
            "user_id": account["_id"],
            "symbol": "tsla",
            "quantity": 2,
            "pin": "0000",
            "price": 123,
        },
    )
    portfolio = client.get(f"/api/simulation/portfolio/{account['_id']}").json()["data"]

    assert response.status_code == 200
    assert response.json()["data"]["price"] == 123
    assert portfolio["cash"] == 4754
    assert portfolio["portfolios"][0]["symbol"] == "TSLA"
    assert portfolio["portfolios"][0]["quantity"] == 2
