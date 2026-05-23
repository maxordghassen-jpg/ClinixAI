import time


class WorkflowGuardService:

    EXPIRATION_SECONDS = 1800

    def is_expired(
        self,
        memory: dict,
    ) -> bool:

        workflow_started_at = memory.get(
            "workflow_started_at"
        )

        if not workflow_started_at:

            return False

        return (
            time.time()
            - workflow_started_at
        ) > self.EXPIRATION_SECONDS