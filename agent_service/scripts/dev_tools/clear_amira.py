import asyncio
from app.memory.redis_memory import RedisMemory

async def main():
    memory = RedisMemory()

    await memory.clear("patient:7698")

    print("Redis session cleared")

asyncio.run(main())