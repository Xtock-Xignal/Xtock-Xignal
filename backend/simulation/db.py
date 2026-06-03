import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "xtock")

mongo_client = MongoClient(MONGODB_URI) if MONGODB_URI else None
db = mongo_client[MONGODB_DB_NAME] if mongo_client is not None else None

users_col = db["simulation_users"] if db is not None else None
portfolio_col = db["simulation_portfolios"] if db is not None else None
transactions_col = db["simulation_transactions"] if db is not None else None
auto_trade_col = db["simulation_auto_trades"] if db is not None else None