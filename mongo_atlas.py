from pymongo import MongoClient, errors
from datetime import datetime, timezone

from pymongo import MongoClient, errors
from datetime import datetime, timezone


class OlxAdsRepository:
    def __init__(self, mongo_uri: str, db_name: str = "olx_db", collection_name: str = "ads"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index("ads_hash", unique=True)

    def upsert_ad(self, ad: dict) -> bool:
        """
        Створює нове оголошення, якщо такого ads_hash ще немає.
        Повертає True якщо вставлено новий документ, False якщо вже існував.
        """
        try:
            result = self.collection.update_one(
                {"ads_hash": ad["ads_hash"]},
                {"$setOnInsert": ad},
                upsert=True
            )
            return result.upserted_id is not None
        except errors.DuplicateKeyError:
            return False

    def get_ad_by_hash(self, ads_hash: str):
        return self.collection.find_one(
            {"ads_hash": ads_hash}
        )
