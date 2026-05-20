from graphs.patient.tools.appointments.executor import PatientAppointmentsExecutor


class PatientAppointmentsTool:
    name = "appointments"

    def __init__(self):
        self.executor = PatientAppointmentsExecutor()

    async def run(self, state):
        return await self.executor.execute(state)
