import asyncio

from app.memory.redis_memory import RedisMemory
from graphs.shared.memory_extractor import MemoryExtractor


memory = RedisMemory()
extractor = MemoryExtractor()

SESSION_ID = "test-session"


async def process_message(message: str):
    print(f"\nUSER: {message}")

    current = await memory.get(SESSION_ID)

    extracted = await extractor.extract(
        message,
        current,
    )

    updated = await memory.update(
        SESSION_ID,
        extracted,
    )

    print("MEMORY:")
    print(updated)


async def main():

    # Clear old session
    await memory.clear(SESSION_ID)

    # Message 1
    await process_message(
        "I need a dermatologist"
    )

    # Message 2
    await process_message(
        "tomorrow"
    )

    # Message 3
    await process_message(
        "5 pm"
    )


if __name__ == "__main__":
    asyncio.run(main())