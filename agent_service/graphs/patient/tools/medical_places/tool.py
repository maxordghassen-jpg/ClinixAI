from graphs.patient.tools.medical_places.executor import MedicalPlacesExecutor


class MedicalPlacesTool:
    name = "medical_places"

    def __init__(self):
        self.executor = MedicalPlacesExecutor()

    async def run(self, state):
        return await self.executor.execute(state)
