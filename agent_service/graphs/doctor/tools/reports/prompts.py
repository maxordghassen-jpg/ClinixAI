REPORTS_PROMPT = """

Tool: report
Role: handle doctor requests to open, view, or retrieve pre-consultation reports.

Choose only one action:

* open_report — open or view a pre-consultation report for a patient

Entities to extract:

* patient_name   — patient's full or partial name (use when the doctor asks by name)
* appointment_id — exact appointment ID string (use when the doctor provides an ID)

Trigger phrases (all map to open_report):

* "open report for <name>"
* "show me the report for <name>"
* "view pre-consultation report for <name>"
* "open a report for <name>"
* "get report for <name>"
* "rapport pré-consultation pour <name>"
* "ouvre le rapport de <name>"

Important:

* Whenever the doctor mentions "report", "pre-consultation", "rapport", or "compte-rendu"
  combined with a patient name or ID → use tool=report, action=open_report.
* Extract the patient name exactly as spoken — do not infer or substitute.
"""
