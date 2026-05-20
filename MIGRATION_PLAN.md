# ClinixAI Backend Migration Plan

## Target Databases

Use only these MongoDB databases and collections:

- `disponibility.disponibilites`
- `appointment_reservation.reservations`

Do not use old `slots`, `appointments`, `availabilities`, or legacy `medical_tunisia_data` collections for booking or availability.

## Availability Shape

```json
{
  "_id": "ObjectId",
  "doctorId": "6637bfc9b72e65a3f0d74e22",
  "day": "lundi",
  "slots": [
    {"start": "08:00", "end": "12:00"},
    {"start": "14:00", "end": "17:00"}
  ],
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Slot `status` is optional. Missing status is treated as `available`; block/book operations set `status` on the embedded slot.

## Reservation Shape

```json
{
  "_id": "ObjectId",
  "doctorId": "55",
  "patientId": "1",
  "date": "ISODate",
  "time": "09:30",
  "status": "confirmed",
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

## Migration Steps

1. Back up all MongoDB databases.
2. Stop `availability_service`, `appointment_service`, and `agent_service`.
3. Ensure availability data is in `disponibility.disponibilites`.
4. Normalize availability fields to `doctorId`, `day`, `slots`, `createdAt`, `updatedAt`.
5. Convert old day names to French values: `lundi`, `mardi`, `mercredi`, `jeudi`, `vendredi`, `samedi`, `dimanche`.
6. Ensure each slot has at least `start` and `end`; keep `status` only when needed.
7. Ensure reservations are in `appointment_reservation.reservations`.
8. Normalize reservation fields to `doctorId`, `patientId`, `date`, `time`, `status`, `createdAt`, `updatedAt`.
9. Start `availability_service`; it creates the `doctorId/day` index on `disponibilites`.
10. Start `appointment_service`; it creates reservation date indexes.
11. Start `agent_service`; it uses `graphs/doctor` and `graphs/patient` custom orchestration.
12. Smoke test:
    - create availability
    - view free slots
    - create appointment
    - cancel appointment
    - doctor chat: “Show Ahmed appointments”
    - doctor chat: “Cancel his appointment”

## Architecture Notes

- API payloads use snake_case.
- MongoDB fields keep supervisor casing: `doctorId`, `patientId`, `createdAt`, `updatedAt`.
- Agent orchestration remains custom and lightweight.
- No LangGraph, `StateGraph`, `graph.compile()`, or external MCP protocol is used.
- MCP files are internal microservice HTTP clients using `httpx.AsyncClient`.
