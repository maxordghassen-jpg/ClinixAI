"""
Backfill separate thesis metric collections from existing evaluation_results.

Usage from evaluation_service:
  python migrations/001_split_framework_metrics.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "clinixai")
SOURCE_COLLECTION = "evaluation_results"
METRIC_COLLECTIONS = {
    "workflow_metrics": "workflow_metrics",
    "intent_metrics": "intent_metrics",
    "memory_metrics": "memory_metrics",
    "llm_judge_metrics": "llm_judge_metrics",
    "multilingual_metrics": "multilingual_metrics",
    "performance_metrics": "performance_metrics",
}


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]
    cursor = db[SOURCE_COLLECTION].find({})
    migrated = 0

    async for doc in cursor:
        result_id = str(doc["_id"])
        for field, collection in METRIC_COLLECTIONS.items():
            metrics = doc.get(field) or {}
            await db[collection].update_one(
                {"result_id": result_id},
                {
                    "$set": {
                        "result_id": result_id,
                        "scenario_id": doc.get("scenario_id"),
                        "evaluated_at": doc.get("evaluated_at"),
                        "metrics": metrics,
                    }
                },
                upsert=True,
            )
        migrated += 1

    print(f"Backfilled thesis metric collections for {migrated} evaluation result(s).")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
