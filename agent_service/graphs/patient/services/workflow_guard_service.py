import logging
import time

logger = logging.getLogger(__name__)


class WorkflowGuardService:

    EXPIRATION_SECONDS = 1800

    def is_expired(self, memory: dict) -> bool:
        workflow_started_at = memory.get("workflow_started_at")

        if not workflow_started_at:
            return False

        current_time     = time.time()
        elapsed_seconds  = current_time - workflow_started_at

        if elapsed_seconds > self.EXPIRATION_SECONDS:
            logger.warning(
                "[WORKFLOW_GUARD] EXPIRED | "
                "workflow_started_at=%.0f current_time=%.0f "
                "elapsed_seconds=%.0f limit=%d",
                workflow_started_at,
                current_time,
                elapsed_seconds,
                self.EXPIRATION_SECONDS,
            )
            return True

        return False