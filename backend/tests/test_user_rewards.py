from bson import ObjectId

import main


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def find_one(self, query, projection=None):
        for row in self.rows:
            if self._matches(row, query):
                result = row.copy()
                if projection and projection.get("_id") == 0:
                    result.pop("_id", None)
                return result
        return None

    def find(self, query, projection=None):
        rows = [row.copy() for row in self.rows if self._matches(row, query)]
        if projection and projection.get("_id") == 0:
            for row in rows:
                row.pop("_id", None)
        return rows

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
        for index, row in enumerate(self.rows):
            if self._matches(row, query):
                self.rows.pop(index)
                return

    def delete_many(self, query):
        self.rows = [row for row in self.rows if not self._matches(row, query)]

    def _matches(self, row, query):
        return all(row.get(key) == value for key, value in query.items())


class FakeDb:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        self.collections.setdefault(name, FakeCollection())
        return self.collections[name]


class FakeMongoClient:
    def __init__(self):
        self.dbs = {}

    def __getitem__(self, name):
        self.dbs.setdefault(name, FakeDb())
        return self.dbs[name]

    def close(self):
        return None


def test_user_rewards_and_attendance_are_saved_per_user(client, monkeypatch):
    users = FakeCollection(
        [{"_id": ObjectId(), "username": "tester", "email": "tester@example.com"}]
    )
    monkeypatch.setattr(main, "get_user_collection", lambda: users)

    first_attendance = client.post(
        "/api/user/attendance/check",
        json={"email": "tester@example.com", "date": "2026-06-01", "amount": 30},
    ).json()
    second_attendance = client.post(
        "/api/user/attendance/check",
        json={"email": "tester@example.com", "date": "2026-06-01", "amount": 30},
    ).json()
    quiz = client.post(
        "/api/user/rewards/quiz",
        json={"email": "tester@example.com", "amount": 50},
    ).json()
    loaded = client.post(
        "/api/user/rewards/get",
        json={"email": "tester@example.com"},
    ).json()

    assert first_attendance["checked"] is True
    assert second_attendance["checked"] is False
    assert quiz["rewards"]["quiz_reward_cash"] == 50
    assert loaded["rewards"]["attendance_reward_cash"] == 30
    assert loaded["rewards"]["attendance_last_date"] == "2026-06-01"


def test_user_delete_removes_simulation_collections(client, monkeypatch):
    user_id = ObjectId()
    sim_user_id = ObjectId()
    users = FakeCollection(
        [
            {
                "_id": user_id,
                "username": "tester",
                "email": "tester@example.com",
                "password": "hashed",
            }
        ]
    )
    simulation_states = FakeCollection([{"email": "tester@example.com"}])
    fake_mongo = FakeMongoClient()
    sim_db = fake_mongo["xtock_db"]
    sim_db["simulation_users"].rows.append(
        {"_id": sim_user_id, "email": "tester@example.com"}
    )
    sim_db["simulation_portfolios"].rows.append({"user_id": str(sim_user_id)})
    sim_db["simulation_transactions"].rows.append({"user_id": str(sim_user_id)})
    sim_db["simulation_auto_trades"].rows.append({"user_id": str(sim_user_id)})

    monkeypatch.setattr(main, "get_user_collection", lambda: users)
    monkeypatch.setattr(main, "get_simulation_collection", lambda: simulation_states)
    monkeypatch.setattr(main, "mongo_client", fake_mongo)
    monkeypatch.setattr(main, "verify_password", lambda plain, hashed: True)

    response = client.post(
        "/api/user/delete",
        json={"email": "tester@example.com", "current_password": "pw"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert users.rows == []
    assert simulation_states.rows == []
    assert sim_db["simulation_users"].rows == []
    assert sim_db["simulation_portfolios"].rows == []
    assert sim_db["simulation_transactions"].rows == []
    assert sim_db["simulation_auto_trades"].rows == []
