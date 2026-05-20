from graphs.doctor.tools.appointments.executor import AppointmentsExecutor


class AppointmentsTool:
    name = "appointments"

    def __init__(self):
        self.executor = AppointmentsExecutor()

    async def run(self, state):
        return await self.executor.execute(state)
