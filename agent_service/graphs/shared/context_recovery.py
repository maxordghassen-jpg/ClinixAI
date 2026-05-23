class ContextRecovery:

    async def recover(
        self,
        message: str,
        memory: dict,
    ) -> dict:

        lowered = message.lower()

        recovered = {}

        step = memory.get("step")

        # =====================================================
        # CONTINUE BOOKING FLOW
        # =====================================================

        if step in [

            "awaiting_date",
            "awaiting_time",
            "ready_to_book",

        ]:

            recovered["intent"] = (
                "booking"
            )

        # =====================================================
        # CONTINUE DOCTOR SELECTION
        # =====================================================

        if step == "searching_doctors":

            recovered["intent"] = (
                "doctor_search"
            )

        if step == "doctor_selected":

            recovered["intent"] = (
                "booking"
            )

        # =====================================================
        # CONTINUE CANCEL FLOW
        # =====================================================

        if step == "ready_to_cancel":

            recovered["intent"] = (
                "cancel"
            )

        return recovered