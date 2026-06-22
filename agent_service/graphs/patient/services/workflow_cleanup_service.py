from app.memory.redis_memory import RedisMemory
from graphs.shared.trace import trace


class WorkflowCleanupService:

    TEMPORARY_KEYS = [

        # Workflow lifecycle
        "step",
        "intent",
        "workflow_started_at",
        "pending_action",

        # Doctor selection
        "selected_doctor_index",
        "doctor_results",
        "doctor_id",
        "doctor_name",
        "specialty",

        # Geo search result list (cleared after place selection or end of workflow)
        "place_results",

        # Booking context
        "date",
        "time",
        "suggested_slots",    # alternative slots stored after 409; cleared on selection
        "recovery_context",   # stored when booking fails with no available slots

        # Appointment retrieval / cancel / reschedule
        "appointment_list",
        "appointment_period",
        "selected_appointment_index",
        "selected_appointment_id",
        "selected_appointment_doctor",
        "selected_appointment_doctor_id",
        "selected_appointment_date",
        "selected_appointment_time",
        "new_date",
        "new_time",

        # Reminder preference (session-scoped; stored in profile after write)
        "reminder_hours",

        # Preconsultation questionnaire (all fields are session-scoped)
        "preconsultation_done",
        "symptom_chief_complaint",
        "symptom_duration",
        "symptom_severity",
        "symptom_associated",
        "recommended_specialty",
        "preconsultation_summary",

    ]

    def __init__(self):
        self.memory = RedisMemory()

    async def clear_workflow(
        self,
        session_id: str,
    ):
        trace("CLEANUP", session_id,
              f"clearing {len(self.TEMPORARY_KEYS)} workflow keys: {self.TEMPORARY_KEYS}")

        await self.memory.delete_keys(
            session_id,
            self.TEMPORARY_KEYS,
        )

        trace("CLEANUP", session_id, "workflow state cleared")
