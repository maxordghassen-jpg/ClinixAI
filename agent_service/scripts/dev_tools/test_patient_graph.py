import asyncio

from graphs.patient.patient_graph import (
    build_patient_graph,
)

from graphs.shared.schemas import AgentState

from app.memory.redis_memory import RedisMemory

memory = RedisMemory()

await memory.clear(session_id)
graph = build_patient_graph()


async def run_message(
    session_id: str,
    message: str,
):

    state = AgentState(
        session_id=session_id,
        role="patient",
        message=message,
        memory={},
        response="",
        patient_id="patient-1",
    )
    result = await graph.ainvoke(state)

    print("\nUSER:", message)
    print("ASSISTANT:", result["response"])
    print("MEMORY:", result["memory"])


async def main():

    session_id = "patient-session"

    await run_message(
        session_id,
        "I need a dermatologist",
    )

    await run_message(
        session_id,
        "tomorrow",
    )

    await run_message(
        session_id,
        "5 pm",
    )


if __name__ == "__main__":
    asyncio.run(main())