from graphs.doctor.tools.appointments.tool import AppointmentsTool
from graphs.doctor.tools.availability.tool import AvailabilityTool


class ToolsRegistry:
    def __init__(self):
        self.tools = {
            "appointments": AppointmentsTool(),
            "availability": AvailabilityTool(),
        }

    def get(self, name: str):
        return self.tools.get(name)
