from typing import Any


IGNORE_VALUES = {
    None,
    "",
}


class ContextMerger:

    @staticmethod
    def merge(
        current: dict[str, Any],
        incoming: dict[str, Any],
    ) -> dict[str, Any]:

        merged = current.copy()

        for key, value in incoming.items():

            # Ignore empty simple values
            if (
                isinstance(
                    value,
                    (str, type(None)),
                )
                and value in IGNORE_VALUES
            ):
                continue

            merged[key] = value

        return merged