from graphs.doctor.tools.availability.executor import AvailabilityExecutor


class AvailabilityTool:
    name = "availability"

    def __init__(self):
        self.executor = AvailabilityExecutor()

    async def run(self, state):
        return await self.executor.execute(state)
