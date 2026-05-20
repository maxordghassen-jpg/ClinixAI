from graphs.patient.tools.appointments.tool import PatientAppointmentsTool
from graphs.patient.tools.availability.tool import PatientAvailabilityTool
from graphs.patient.tools.medical_places.tool import MedicalPlacesTool
from graphs.patient.tools.medical_profile.tool import MedicalProfileTool


class ToolsRegistry:
    def __init__(self):
        self.tools = {
            "appointments": PatientAppointmentsTool(),
            "availability": PatientAvailabilityTool(),
            "medical_places": MedicalPlacesTool(),
            "medical_profile": MedicalProfileTool(),
        }

    def get(self, name: str):
        return self.tools.get(name)
