import logging
from typing import Any

import httpx

from graphs.patient.mcp.tool_caller import ToolCaller
from graphs.shared.schemas import AgentState


logger = logging.getLogger(__name__)


CATEGORY_BY_ACTION = {
    "search_nearby_hospitals": "hospitals",
    "search_nearby_pharmacies": "pharmacies",
    "search_nearby_clinics": "clinics",
    "search_doctors_by_specialty": "doctors",
    "search_by_city": "doctors",
}


CATEGORY_KEYWORDS = {
    "hospital": "hospitals",
    "hospitals": "hospitals",
    "hopital": "hospitals",
    "hôpital": "hospitals",

    "pharmacy": "pharmacies",
    "pharmacies": "pharmacies",
    "pharmacie": "pharmacies",

    "clinic": "clinics",
    "clinics": "clinics",
    "clinique": "clinics",

    "doctor": "doctors",
    "doctors": "doctors",

    "dentist": "doctors",
    "cardiologist": "doctors",
}


SEARCH_NORMALIZATION = {
    # pharmacies
    "pharmacy": "pharmacies",
    "pharmacies": "pharmacies",
    "pharmacie": "pharmacies",
    "صيدلية": "pharmacies",

    # hospitals
    "hospital": "hospitals",
    "hospitals": "hospitals",
    "hopital": "hospitals",
    "hôpital": "hospitals",
    "مستشفى": "hospitals",

    # clinics
    "clinic": "clinics",
    "clinics": "clinics",
    "clinique": "clinics",
    "عيادة": "clinics",

    # doctors
    "doctor": "doctors",
    "doctors": "doctors",
    "médecin": "doctors",
    "طبيب": "doctors",

    # labs
    "lab": "analysis_labs",
    "laboratory": "analysis_labs",
    "مختبر": "analysis_labs",
}


class MedicalPlacesExecutor:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def execute(self, state: AgentState) -> Any:
        intent = state.intent
        entities = intent.entities if intent else {}

        action = intent.action if intent else "search_by_city"

        category = self._resolve_category(action, entities)

        try:
            # nearby search with coordinates
            if self._has_coordinates(entities):
                return await self.tool_caller.search_nearby_places(
                    {
                        "latitude": entities.get("latitude"),
                        "longitude": entities.get("longitude"),
                        "category": category,
                        "radius": entities.get("radius", 20),
                        "limit": entities.get("limit", 10),
                        "specialty": entities.get("specialty"),
                        "governorate": (
                            entities.get("governorate")
                            or entities.get("city")
                        ),
                    }
                )

            # manual search
            raw_query = (
                entities.get("query")
                or entities.get("category")
                or entities.get("specialty")
                or entities.get("city")
                or entities.get("location")
                or category
            )

            normalized_query = SEARCH_NORMALIZATION.get(
                str(raw_query).lower(),
                raw_query,
            )

            logger.info(
                "Medical search raw query: %s",
                raw_query,
            )

            logger.info(
                "Medical search normalized query: %s",
                normalized_query,
            )

            response = await self.tool_caller.search_places(
                {
                    "query": normalized_query,
                    "category": normalized_query,
                    "governorate": (
                        entities.get("governorate")
                        or entities.get("city")
                    ),
                    "specialty": entities.get("specialty"),
                    "limit": entities.get("limit", 10),
                }
            )

            logger.info(
                "Geo service response: %s",
                response,
            )

            return response

        except httpx.HTTPError as exc:
            logger.warning(
                "patient medical places request failed: %s",
                exc,
            )

            return {
                "message": (
                    "I could not search medical places right now. "
                    f"{exc}"
                )
            }

    def _resolve_category(
        self,
        action: str,
        entities: dict[str, Any],
    ) -> str:
        raw_category = str(
            entities.get("category", "")
        ).lower()

        if raw_category in CATEGORY_KEYWORDS:
            return CATEGORY_KEYWORDS[raw_category]

        return CATEGORY_BY_ACTION.get(
            action,
            "doctors",
        )

    def _has_coordinates(
        self,
        entities: dict[str, Any],
    ) -> bool:
        return (
            entities.get("latitude") is not None
            and entities.get("longitude") is not None
        )