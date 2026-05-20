from graphs.patient.tools.availability.executor import PatientAvailabilityExecutor


class PatientAvailabilityTool:
    name = "availability"

    def __init__(self):
        self.executor = PatientAvailabilityExecutor()

    async def run(self, state):
        return await self.executor.execute(state)
