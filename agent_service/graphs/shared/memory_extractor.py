from graphs.shared.llm_router import LLMRouter


class MemoryExtractor:
    def __init__(self):
        self.llm = LLMRouter()

    async def extract(self, message: str, current_memory: dict) -> dict:
        prompt = (
            "Extract durable conversational memory from multilingual clinical admin chat. "
            "Return JSON only. Useful keys: patient_name, patient_id, doctor_id, "
            "reservation_id, date, time, day. Use snake_case."
        )
        result = await self.llm.complete_json(prompt, f"memory={current_memory}\nmessage={message}")
        if result:
            return result
        return self._fallback(message)

    def _fallback(self, message: str) -> dict:
        words = message.replace("'", " ").replace(",", " ").split()
        for index, word in enumerate(words):
            if word.lower() in {"show", "affiche", "voir", "cancel", "annuler"} and index + 1 < len(words):
                candidate = words[index + 1].strip(".")
                if candidate and candidate[0].isupper():
                    return {"patient_name": candidate}
        return {}
