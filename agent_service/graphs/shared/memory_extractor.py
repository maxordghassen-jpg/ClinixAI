import re
from typing import Any


class MemoryExtractor:

    SPECIALTIES = [
        "cardiologist",
        "dermatologist",
        "neurologist",
        "dentist",
        "psychiatrist",
        "orthopedic",
    ]

    DAYS = [
        "today",
        "tomorrow",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    BOOKING_KEYWORDS = [
        "book",
        "appointment",
        "schedule",
    ]

    async def extract(
        self,
        message: str,
        current_memory: dict[str, Any],
    ) -> dict[str, Any]:

        lowered = message.lower()

        memory: dict[str, Any] = {}

        # -------------------------
        # Geo Search Intent
        # -------------------------

        if "nearby" in lowered:
            memory["intent"] = "geo_search"

        if "near me" in lowered:
            memory["intent"] = "geo_search"

        if "pharmacy" in lowered:
            memory["place_type"] = "pharmacy"

        if "clinic" in lowered:
            memory["place_type"] = "clinic"

        # -------------------------
        # Doctor Specialty Extraction
        # -------------------------

        for specialty in self.SPECIALTIES:

            if specialty in lowered:

                memory["specialty"] = specialty

                # Doctor search flow
                if not any(
                    keyword in lowered
                    for keyword in self.BOOKING_KEYWORDS
                ):

                    memory["intent"] = (
                        "doctor_search"
                    )

        # -------------------------
        # Booking Intent
        # -------------------------

        if any(
            keyword in lowered
            for keyword in self.BOOKING_KEYWORDS
        ):

            memory["intent"] = "booking"

        # -------------------------
        # Cancel Intent
        # -------------------------

        if "cancel" in lowered:
            memory["intent"] = "cancel"

        # -------------------------
        # Confirm Intent
        # -------------------------

        if "confirm" in lowered:
            memory["intent"] = "confirm"
        # -------------------------
        # Doctor Selection
        # -------------------------

        if (
            lowered.isdigit()
            and current_memory.get("step")
            == "selecting_doctor"
        ):

            memory[
                "selected_doctor_index"
            ] = int(lowered)

            memory["intent"] = "booking"

            memory["step"] = (
                "doctor_selected"
            )
        # -------------------------
        # Date Extraction
        # -------------------------

        for day in self.DAYS:

            if day in lowered:
                memory["date"] = day
        # -------------------------
        # Time Extraction
        # -------------------------

        current_step = current_memory.get(
            "step"
        )

        # Only extract time
        # when awaiting_time
        if current_step == "awaiting_time":

            time_match = re.search(
                r"\b\d{1,2}\s?(am|pm)\b",
                lowered,
            )

            if time_match:

                memory["time"] = (
                    time_match.group()
                )

        # -------------------------
        # Current + Previous Memory
        # -------------------------

        intent = memory.get(
            "intent",
            current_memory.get("intent"),
        )

        specialty = memory.get(
            "specialty",
            current_memory.get("specialty"),
        )

        date = memory.get(
            "date",
            current_memory.get("date"),
        )

        time = memory.get(
            "time",
            current_memory.get("time"),
        )

        # -------------------------
        # Doctor Search Workflow
        # -------------------------

        if intent == "doctor_search":

            memory["intent"] = (
                "doctor_search"
            )

            if specialty:
                memory["specialty"] = specialty

            memory["step"] = (
                "selecting_doctor"
            )

        # -------------------------
        # Booking Workflow
        # -------------------------

        if intent == "booking":

            memory["intent"] = "booking"

            if specialty:
                memory["specialty"] = specialty

            if date:
                memory["date"] = date

            if time:
                memory["time"] = time

            if not specialty:

                memory["step"] = (
                    "awaiting_specialty"
                )

            elif not date:

                memory["step"] = (
                    "awaiting_date"
                )

            elif not time:

                memory["step"] = (
                    "awaiting_time"
                )

            else:

                memory["step"] = (
                    "ready_to_book"
                )

        # -------------------------
        # Geo Search Workflow
        # -------------------------

        if intent == "geo_search":

            memory["step"] = (
                "searching_places"
            )

        # -------------------------
        # Cancel Workflow
        # -------------------------

        if intent == "cancel":

            memory["step"] = (
                "ready_to_cancel"
            )

        # -------------------------
        # Confirm Workflow
        # -------------------------

        if intent == "confirm":

            memory["step"] = "confirmed"

        return memory