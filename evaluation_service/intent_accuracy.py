"""
intent_accuracy.py — Intent detection accuracy for ClinixAI.

Calls Groq directly with the exact same prompt used by agent_service's
IntentNode — no agent_service import needed, avoids Python path conflicts.

Metrics: overall accuracy, per-intent precision / recall / F1,
         per-language accuracy, confusion matrix.

Run:
    cd evaluation_service
    ..\venv\Scripts\python.exe intent_accuracy.py
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from groq import AsyncGroq
from app.config.settings import settings          # eval_service settings (has GROQ_API_KEY)
from datasets.eval_scenarios import SCENARIOS

# ── Groq client ───────────────────────────────────────────────────────────────
_MODEL = "llama-3.3-70b-versatile"
_client: AsyncGroq | None = None

def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client

# ── Exact IntentNode prompt (copied from agent_service/graphs/shared/nodes/intent_node.py) ──

_INTENT_PROMPT = """\
You are an AI medical assistant.

Your job:
- detect intent
- extract entities
- detect language

Return ONLY valid JSON with no markdown, no explanation.

Allowed intents:
- doctor_search          (find a doctor by specialty)
- booking                (book an appointment with a doctor)
- check_availability     (check if a SPECIFIC named doctor has free slots on a date)
- cancel_appointment     (cancel an existing appointment)
- reschedule_appointment (move an existing appointment to a new date/time)
- view_appointments      (list the patient's upcoming or recent appointments)
- set_reminder           (set a notification preference before appointments)
- geo_search             (find nearby clinics, pharmacies, hospitals)
- select_doctor          (patient is choosing a doctor from a list, e.g. "1" or "2")
- select_appointment     (patient is choosing an appointment from a list, e.g. "1" or "2")
- preconsultation        (patient wants to describe symptoms before a consultation)
- none

INTENT DISAMBIGUATION:
- check_availability: use ONLY when a specific doctor name is mentioned ("Is Dr. X available?",
  "Does Dr. Y have openings?", "Can I see Dr. Z on Friday?")
- booking: use when the patient wants to BOOK an appointment (not just check slots)
- doctor_search: use when looking for doctors BY SPECIALTY with no specific doctor named

Languages: english | french | arabic

Entity fields (include only what applies):
  specialty               - normalized specialty name
  doctor_id               - explicit doctor ID if the user says "doctor ID: xxx" or "ID: xxx"
  doctor_name             - doctor's name if mentioned (e.g. "Dr. Smith")
  date                    - date string (as said by user)
  time                    - time string (as said by user)
  new_date                - new date for reschedule
  new_time                - new time for reschedule
  selected_doctor_index   - integer (1-based) when intent=select_doctor
  selected_appointment_index - integer (1-based) when intent=select_appointment
  appointment_period      - "today" | "week" | "next_week" | "all" for view_appointments
  reminder_hours          - integer for set_reminder (e.g. 2 for "2 hours before")
  query                   - search query for geo_search
  urgency                 - "high" ONLY when the user explicitly signals urgency

IMPORTANT: Return ONLY valid JSON. No text before or after the JSON object."""

# ── Mapping: expected_workflow  →  IntentNode intent label ──────────────────
WORKFLOW_TO_INTENT: dict[str, str] = {
    "book_appointment":   "booking",
    "cancel_appointment": "cancel_appointment",
    "check_availability": "check_availability",
    "find_medical_place": "geo_search",
    "view_schedule":      "view_appointments",
    "update_availability":"update_availability",  # doctor-side; IntentNode may return none
    "preconsultation":    "preconsultation",
}

# Normalise detected intent aliases
_ALIASES: dict[str, str] = {
    "book_appointment":       "booking",
    "find_medical_place":     "geo_search",
    "view_schedule":          "view_appointments",
    "availability":           "update_availability",
}


async def detect_intent(message: str) -> str:
    """
    Call Groq using system + user message format.
    Auto-retries on 429 (rate limit) with exponential backoff up to 5 minutes.
    """
    import re
    for attempt in range(12):                       # up to ~10 min total wait
        try:
            resp = await _get_client().chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": _INTENT_PROMPT},
                    {"role": "user",   "content": message},
                ],
                temperature=0.0,
                max_tokens=128,
            )
            raw = (resp.choices[0].message.content or "").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data   = json.loads(raw)
            intent = str(data.get("intent", "none")).lower().strip()
            return _ALIASES.get(intent, intent)

        except json.JSONDecodeError:
            snippet = (resp.choices[0].message.content or "")[:80]
            print(f"\n    [WARN] JSON parse error — raw: {snippet!r}", file=sys.stderr)
            return "none"

        except Exception as exc:
            msg = str(exc)
            # Rate limit — parse "try again in Xm Ys" or default to 65 s
            if "429" in msg or "rate_limit" in msg:
                # Extract wait time from error message
                m = re.search(r"in\s+(\d+)m(\d+)", msg)
                if m:
                    wait = int(m.group(1)) * 60 + int(m.group(2)) + 5
                else:
                    m2 = re.search(r"in\s+(\d+)s", msg)
                    wait = int(m2.group(1)) + 5 if m2 else 65
                wait = min(wait, 300)       # cap at 5 min
                print(f"\n    [RATE LIMIT] waiting {wait}s before retry …",
                      flush=True)
                await asyncio.sleep(wait)
                continue
            print(f"\n    [WARN] Groq error: {exc}", file=sys.stderr)
            return "none"

    print("\n    [ERROR] Max retries exceeded", file=sys.stderr)
    return "none"


# ── Metric helpers ─────────────────────────────────────────────────────────────

def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    eval_scenarios = [s for s in SCENARIOS if s.expected_workflow]

    print(f"\n{'='*74}")
    print(f"  ClinixAI — Intent Detection Accuracy")
    print(f"  Model  : {_MODEL}")
    print(f"  Scenes : {len(eval_scenarios)}  (scenarios with expected_workflow)")
    print(f"  Sleep  : 3 s between calls (Groq TPM guard)")
    print(f"{'='*74}\n")

    rows: list[dict] = []

    HDR = "{:<16} {:<9} {:<8} {:<24} {:<24} {}"
    SEP = "-" * 86
    print(HDR.format("Scenario", "Language", "Role", "Expected", "Detected", ""))
    print(SEP)

    for idx, s in enumerate(eval_scenarios):
        expected = WORKFLOW_TO_INTENT.get(s.expected_workflow, s.expected_workflow)
        detected = await detect_intent(s.user_message)
        correct  = (detected == expected)

        rows.append({
            "id":       s.id,
            "language": s.language,
            "role":     s.role,
            "expected": expected,
            "detected": detected,
            "correct":  correct,
        })

        mark = "OK" if correct else "MISS"
        print(HDR.format(
            s.id[:16], s.language[:9], s.role[:8],
            expected[:24], detected[:24], mark,
        ))

        if idx < len(eval_scenarios) - 1:
            await asyncio.sleep(3)

    # ── Overall accuracy ───────────────────────────────────────────────────────
    total   = len(rows)
    correct = sum(1 for r in rows if r["correct"])
    acc     = correct / total if total else 0.0

    print()
    print(f"{'='*74}")
    print(f"  OVERALL ACCURACY : {correct}/{total}  =  {acc:.1%}")
    print(f"{'='*74}\n")

    # ── Per-intent precision / recall / F1 ────────────────────────────────────
    expected_intents = sorted(set(r["expected"] for r in rows))
    all_detected     = sorted(set(r["detected"] for r in rows))
    all_intents      = sorted(set(expected_intents + all_detected))

    MHDR = "{:<26} {:>7} {:>6} {:>8} {:>8} {:>8}"
    print(MHDR.format("Intent", "Correct", "Total", "Prec", "Recall", "F1"))
    print("-" * 67)

    per_intent: dict[str, dict] = {}
    for intent in all_intents:
        tp = sum(1 for r in rows if r["expected"] == intent and r["detected"] == intent)
        fp = sum(1 for r in rows if r["expected"] != intent and r["detected"] == intent)
        fn = sum(1 for r in rows if r["expected"] == intent and r["detected"] != intent)
        p, rec, f1 = precision_recall_f1(tp, fp, fn)
        n = tp + fn                        # how many times it appeared as expected
        per_intent[intent] = {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": rec, "f1": f1, "n": n}
        if n > 0:
            print(MHDR.format(intent[:26], tp, n, f"{p:.2f}", f"{rec:.2f}", f"{f1:.2f}"))

    # Macro averages (only intents that appear as expected)
    exp_only = [i for i in all_intents if per_intent[i]["n"] > 0]
    mac_p  = sum(per_intent[i]["p"]   for i in exp_only) / len(exp_only)
    mac_r  = sum(per_intent[i]["r"]   for i in exp_only) / len(exp_only)
    mac_f1 = sum(per_intent[i]["f1"]  for i in exp_only) / len(exp_only)
    print("-" * 67)
    print(MHDR.format("Macro average", correct, total, f"{mac_p:.2f}", f"{mac_r:.2f}", f"{mac_f1:.2f}"))

    # ── Per-language accuracy ──────────────────────────────────────────────────
    print()
    print(f"{'='*74}")
    print("  ACCURACY BY LANGUAGE")
    print(f"{'='*74}")
    LHDR = "{:<12} {:>8} {:>8} {:>12}"
    print(LHDR.format("Language", "Correct", "Total", "Accuracy"))
    print("-" * 44)
    for lang in sorted(set(r["language"] for r in rows)):
        sub = [r for r in rows if r["language"] == lang]
        c   = sum(1 for r in sub if r["correct"])
        n   = len(sub)
        print(LHDR.format(lang, c, n, f"{c/n:.1%}"))

    # ── Confusion matrix ───────────────────────────────────────────────────────
    print()
    print(f"{'='*74}")
    print("  CONFUSION MATRIX  (rows = expected, cols = detected)")
    print(f"{'='*74}")

    matrix: dict[str, dict[str, int]] = {
        e: {d: 0 for d in all_detected} for e in expected_intents
    }
    for r in rows:
        if r["detected"] in matrix.get(r["expected"], {}):
            matrix[r["expected"]][r["detected"]] += 1

    # Column widths
    col_w = max(len(d) for d in all_detected) + 2
    row_w = max(len(e) for e in expected_intents) + 2

    hdr_label = "Expected / Detected"
    header = f"  {hdr_label:<{row_w}}"
    for d in all_detected:
        header += f"{d:>{col_w}}"
    print(header)
    print("  " + "-" * (row_w + col_w * len(all_detected)))

    for e in expected_intents:
        row_str = f"  {e:<{row_w}}"
        for d in all_detected:
            v    = matrix[e].get(d, 0)
            cell = f"[{v}]" if (e == d and v > 0) else (str(v) if v > 0 else ".")
            row_str += f"{cell:>{col_w}}"
        print(row_str)

    print()
    print("  Legend: [n] = correct (diagonal)  |  . = 0")
    print()
    print(f"  Overall accuracy : {acc:.1%}  ({correct}/{total})")
    print(f"  Macro F1         : {mac_f1:.3f}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
