import asyncio

from app.memory.redis_memory import RedisMemory


async def main():

    memory = RedisMemory()

    await memory.clear("patient_1")

    await memory.update(
        "patient_1",
        {
            "date": "tomorrow",
        },
    )

    await memory.update(
        "patient_1",
        {
            "doctor_id": "57",
        },
    )

    await memory.update(
        "patient_1",
        {
            "time": "09:00",
        },
    )

    data = await memory.get(
        "patient_1"
    )

    print(data)


asyncio.run(main())