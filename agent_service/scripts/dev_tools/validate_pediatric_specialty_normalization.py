"""
Pediatric specialty normalization validation — SPECIALTY_NORMALIZATION fix in
IntentNode (agent_service/graphs/shared/nodes/intent_node.py).

Scenario:
    The LLM may return the specialty entity in different scripts/languages
    for a pediatrician request, including the observed regression value
    "پدیاتری" (Farsi). SPECIALTY_NORMALIZATION must map all of these to the
    same canonical value ("pédiatre") so DoctorSearchService always searches
    with a value that case-insensitively matches MongoDB's "Pédiatre".

Cases (raw LLM "specialty" value -> expected normalized value):
    "pediatrician"   -> "pédiatre"   (English)
    "pediatric doctor" -> "pédiatre" (English)
    "child doctor"   -> "pédiatre"   (English)
    "pediatrics"     -> "pédiatre"   (English)
    "pédiatre"       -> "pédiatre"   (French, already canonical)
    "pédiatrie"      -> "pédiatre"   (French)
    "طبيب أطفال"     -> "pédيatre"   (Arabic)  [see note below]
    "طب أطفال"       -> "pédiatre"   (Arabic)
    "أطفال"          -> "pédiatre"   (Arabic)
    "پدیاتری"        -> "pédiatre"   (Farsi — the reproduced regression value)

Each case is run through IntentNode.run() with the Groq client mocked to
return {"intent":"doctor_search","specialty":<raw>,"language":<lang>} for
the corresponding user message, then asserts
state.memory["specialty"] == "pédiatre".

Finally, SpecialtyNormalizer.normalize("pédiatre") is checked to confirm the
value DoctorSearchService passes to search_places() case-insensitively
matches MongoDB's "Pédiatre" specialty field (regex match, $options: "i").
"""
import asyncio
import json
import re
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import graphs.shared.nodes.intent_node as intent_node_module  # noqa: E402
from graphs.shared.nodes.intent_node import IntentNode  # noqa: E402
from graphs.shared.normalizers.specialty_normalizer import SpecialtyNormalizer  # noqa: E402
from graphs.shared.schemas import AgentState  # noqa: E402


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, *args, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def _mock_llm(extracted: dict) -> None:
    intent_node_module.client = _FakeClient(json.dumps(extracted, ensure_ascii=False))


CASES = [
    ("I need a pediatrician",     "pediatrician",      "english"),
    ("I need a pediatric doctor", "pediatric doctor",  "english"),
    ("I need a child doctor",     "child doctor",      "english"),
    ("I need pediatrics care",    "pediatrics",        "english"),
    ("Je cherche un pédiatre",    "pédiatre",          "french"),
    ("Je cherche un médecin de pédiatrie", "pédiatrie", "french"),
    ("أبحث عن طبيب أطفال",         "طبيب أطفال",        "arabic"),
    ("أحتاج طب أطفال",             "طب أطفال",          "arabic"),
    ("أبحث عن دكتور أطفال",        "أطفال",             "arabic"),
    # Reproduced regression: LLM returns a Farsi specialty string regardless
    # of the input language.
    ("I need a pediatrician",     "پدیاتری",           "english"),
    ("أبحث عن طبيب أطفال",         "پدیاتری",           "arabic"),
]


async def main() -> None:
    ok = True

    for message, raw_specialty, language in CASES:
        state = AgentState(
            role="patient",
            message=message,
            session_id="validation-pediatric-specialty",
            memory={"step": "idle"},
        )

        _mock_llm({
            "intent": "doctor_search",
            "specialty": raw_specialty,
            "language": language,
        })

        await IntentNode().run(state)

        normalized = state.memory.get("specialty")
        status = "OK" if normalized == "pédiatre" else "FAIL"
        if normalized != "pédiatre":
            ok = False
        print(f"[{status}] message={message!r:35s} raw_specialty={raw_specialty!r:18s} "
              f"-> normalized={normalized!r}")

    print()

    # Confirm the canonical value resolves to something that case-insensitively
    # matches MongoDB's "Pédiatre" specialty field via $regex/$options:"i".
    query = SpecialtyNormalizer.normalize("pédiatre")
    print(f"SpecialtyNormalizer.normalize('pédiatre') -> {query!r}")
    matches_mongo_value = bool(re.search(query, "Pédiatre", re.IGNORECASE))
    print(f"Case-insensitive regex match against MongoDB 'Pédiatre': {matches_mongo_value}")
    if not matches_mongo_value:
        ok = False
        print("FAIL: normalized specialty would not match MongoDB 'Pédiatre' via $regex/i")

    print()
    if ok:
        print("PASS: all specialty variants (English/French/Arabic/Farsi) normalize to "
              "'pédiatre', which case-insensitively matches MongoDB's 'Pédiatre'")
    else:
        print("SOME FAILED")
        sys.exit(1)


asyncio.run(main())
