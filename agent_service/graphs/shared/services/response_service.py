class ResponseService:

    RESPONSES = {

        "english": {

            "found_places":
            "I found nearby",

            "book_question":
            "Would you like to book an appointment?",

            "select_from_results":
            "Which one would you like to book with?",

            "no_results":
            "No nearby results found.",
        },

        "french": {

            "found_places":
            "J'ai trouvé à proximité",

            "book_question":
            "Voulez-vous prendre un rendez-vous ?",

            "select_from_results":
            "Avec lequel souhaitez-vous prendre rendez-vous ?",

            "no_results":
            "Aucun résultat trouvé à proximité.",
        },

        "arabic": {

            "found_places":
            "لقد وجدت بالقرب منك",

            "book_question":
            "هل تريد حجز موعد؟",

            "select_from_results":
            "مع أيهم تريد حجز موعد؟",

            "no_results":
            "لم يتم العثور على نتائج قريبة.",
        },
    }

    def get(
        self,
        language: str,
        key: str,
    ):

        language = (
            language or "english"
        ).lower()

        return (
            self.RESPONSES
            .get(
                language,
                self.RESPONSES[
                    "english"
                ],
            )
            .get(
                key,
                key,
            )
        )

    def translate_query(
        self,
        language: str,
        query: str,
    ):

        translations = {

            "arabic": {

                "pharmacy": "صيدلية",
                "hospital": "مستشفى",
                "clinic": "عيادة",
                "doctor": "طبيب",
                "dermatologist": "طبيب جلد",
            },

            "french": {

                "pharmacy": "pharmacie",
                "hospital": "hôpital",
                "clinic": "clinique",
                "doctor": "médecin",
                "dermatologist": "dermatologue",
            },
        }

        return (
            translations
            .get(language, {})
            .get(query, query)
        )