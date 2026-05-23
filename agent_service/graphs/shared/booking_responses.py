class BookingResponses:

    _R = {
        "english": {
            # ── Booking ──────────────────────────────────────────────────────
            "ask_specialty":           "What type of doctor are you looking for?",
            "ask_date":                "What date would you like?",
            "ask_again_date":          "I didn't catch a date. What date would you like?",
            "ask_time":                "What time would you prefer?",
            "ask_again_time":          "I didn't catch a time. What time would you prefer?",
            "doctor_found":            "I found {name}.",
            "doctors_found":           "I found these doctors:",
            "doctor_prompt":           "Which doctor would you like?",
            "booking_success":         "Your appointment has been booked successfully.",
            "slot_unavailable":        "This time slot is unavailable.\n\nAvailable times:\n{slots}",
            "slot_unavailable_with_alternatives": "{requested_time} is not available.\n\nHere are the available times:\n\n{slots}\n\nWhich would you prefer?",
            "no_slots":                "No available slots were found for that date.",
            "no_slots_suggest_date":   "There are no available slots for that date. Would you like to try a different date?",
            # ── Availability exploration (MODE 1) ─────────────────────────────
            "next_available_slots":    "Here are the next available slots for {doctor_name}:\n\n{slots}\n\nWhich would you prefer?",
            "time_slots_for_date":     "Here are the available times for {date}:\n\n{slots}\n\nWhich would you prefer?",
            "no_next_available":       "No upcoming available slots found for this doctor. What date would you like to try?",
            "slot_reselect_prompt":    "Please choose one of the available times:\n\n{slots}",
            "invalid_selection":       "Invalid selection. Please choose a number from the list.",
            "invalid_date":            "I couldn't understand that date. Could you try again? (e.g. 'tomorrow', 'Friday', '22/05/2026')",
            "invalid_time":            "I couldn't understand that time. Could you try again? (e.g. '3 pm', '14:30', '9h30')",
            # ── Appointment retrieval ─────────────────────────────────────────
            "no_appointments":         "You have no upcoming appointments.",
            "appointments_header":     "Here are your appointments:",
            "appointment_line":        "• {index}. Dr. {doctor_name} — {date} at {time} ({status})",
            "select_appointment":      "Which appointment? Reply with its number.",
            "appointment_not_found":   "I couldn't find that appointment. Please choose a valid number.",
            # ── Cancellation ─────────────────────────────────────────────────
            "cancel_confirm_prompt":   "Cancel your appointment with {doctor_name} on {date} at {time}? Reply 'yes' to confirm.",
            "cancel_success":          "Your appointment with {doctor_name} on {date} has been cancelled.",
            "cancel_confirm":          "Your cancellation request has been received.",
            # ── Reschedule ───────────────────────────────────────────────────
            "reschedule_confirm_prompt":    "Reschedule your appointment with {doctor_name} on {date} at {time}? Reply 'yes' to proceed.",
            "reschedule_aborted":           "Reschedule cancelled. Is there anything else I can help you with?",
            "ask_reschedule_date":          "What new date would you like for your appointment?",
            "ask_reschedule_time":          "What new time would you prefer?",
            "reschedule_success":           "Your appointment has been rescheduled to {date} at {time}.",
            "reschedule_failed":            "Rescheduling failed. That slot may be unavailable. Please try another time.",
            "reschedule_slot_unavailable_with_alternatives": "{requested_time} is not available on that date.\n\nHere are available times:\n\n{slots}\n\nWhich would you prefer?",
            "reschedule_slot_reselect_prompt":              "Please choose one of the available times:\n\n{slots}",
            "reschedule_no_slots_for_date": "No available slots for {date}. What new date would you like?",
            "reschedule_next_available_slots": "The next available slots are on {date}:\n\n{slots}\n\nWhich would you prefer?",
            "reschedule_time_slots":          "Here are the available times for {date}:\n\n{slots}\n\nWhich would you prefer?",
            "reschedule_no_next_available":   "No upcoming availability found for this doctor. Please try a specific date.",
            # ── Reminder ─────────────────────────────────────────────────────
            "reminder_saved":          "Done. I'll remind you {hours} hour(s) before each appointment.",
            "reminder_invalid":        "Please tell me how many hours before your appointment you'd like a reminder (e.g. '2 hours before').",
            # ── Personalization ──────────────────────────────────────────────
            "suggest_usual_doctor":    "Would you like to book with {name} again, your usual {specialty}?",
            # ── Guided recovery (no-slots failure) ───────────────────────────
            "recovery_options": (
                "No appointments are available for {date} with {doctor_name}.\n\n"
                "What would you like to do?\n\n"
                "1. Try a different date\n"
                "2. See next available appointment\n"
                "3. Choose a different doctor\n"
                "4. Find nearby doctors"
            ),
            "recovery_try_date":           "What date would you like to try?",
            "recovery_searching_doctor":   "Let me find another {specialty} for you.",
            "recovery_searching_nearby":   "Let me search for nearby {specialty} options.",
            "recovery_next_available":          "The next available date with {doctor_name} is {date}.\n\nWhat time would you prefer?",
            "recovery_next_available_slots":    "The next available slots with {doctor_name} are:\n\n{slots}\n\nWhich would you prefer?",
            "recovery_no_next_available":  (
                "There are no upcoming available appointments with {doctor_name}.\n\n"
                "1. Try a different date\n"
                "3. Choose a different doctor\n"
                "4. Find nearby doctors"
            ),
            "recovery_choice_invalid": (
                "I didn't catch that. Please choose:\n\n"
                "1. Try a different date\n"
                "2. See next available appointment\n"
                "3. Choose a different doctor\n"
                "4. Find nearby doctors"
            ),
        },
        "french": {
            # ── Booking ──────────────────────────────────────────────────────
            "ask_specialty":           "Quel type de médecin recherchez-vous ?",
            "ask_date":                "Quelle date vous conviendrait ?",
            "ask_again_date":          "Je n'ai pas compris la date. Quelle date souhaitez-vous ?",
            "ask_time":                "À quelle heure préférez-vous ?",
            "ask_again_time":          "Je n'ai pas compris l'heure. À quelle heure préférez-vous ?",
            "doctor_found":            "J'ai trouvé {name}.",
            "doctors_found":           "J'ai trouvé ces médecins :",
            "doctor_prompt":           "Quel médecin souhaitez-vous choisir ?",
            "booking_success":         "Votre rendez-vous a été réservé avec succès.",
            "slot_unavailable":        "Ce créneau horaire n'est pas disponible.\n\nCréneaux disponibles :\n{slots}",
            "slot_unavailable_with_alternatives": "{requested_time} n'est pas disponible.\n\nVoici les créneaux disponibles :\n\n{slots}\n\nLequel préférez-vous ?",
            "no_slots":                "Aucun créneau disponible n'a été trouvé pour cette date.",
            "no_slots_suggest_date":   "Il n'y a pas de créneaux disponibles pour cette date. Souhaitez-vous essayer une autre date ?",
            # ── Exploration de disponibilité (MODE 1) ────────────────────────
            "next_available_slots":    "Voici les prochains créneaux disponibles pour {doctor_name} :\n\n{slots}\n\nLequel préférez-vous ?",
            "time_slots_for_date":     "Voici les créneaux disponibles le {date} :\n\n{slots}\n\nLequel préférez-vous ?",
            "no_next_available":       "Aucun créneau disponible à venir trouvé pour ce médecin. Quelle date souhaitez-vous essayer ?",
            "slot_reselect_prompt":    "Veuillez choisir parmi les créneaux disponibles :\n\n{slots}",
            "invalid_selection":       "Sélection invalide. Veuillez choisir un numéro dans la liste.",
            "invalid_date":            "Je n'ai pas pu comprendre cette date. Pouvez-vous réessayer ? (ex. 'demain', 'vendredi', '22/05/2026')",
            "invalid_time":            "Je n'ai pas pu comprendre cette heure. Pouvez-vous réessayer ? (ex. '15h00', '14:30', '9h30')",
            # ── Appointment retrieval ─────────────────────────────────────────
            "no_appointments":         "Vous n'avez aucun rendez-vous à venir.",
            "appointments_header":     "Voici vos rendez-vous :",
            "appointment_line":        "• {index}. Dr. {doctor_name} — {date} à {time} ({status})",
            "select_appointment":      "Quel rendez-vous ? Répondez avec son numéro.",
            "appointment_not_found":   "Je n'ai pas trouvé ce rendez-vous. Veuillez choisir un numéro valide.",
            # ── Cancellation ─────────────────────────────────────────────────
            "cancel_confirm_prompt":   "Annuler votre rendez-vous avec {doctor_name} le {date} à {time} ? Répondez 'oui' pour confirmer.",
            "cancel_success":          "Votre rendez-vous avec {doctor_name} le {date} a été annulé.",
            "cancel_confirm":          "Votre demande d'annulation a bien été reçue.",
            # ── Reschedule ───────────────────────────────────────────────────
            "reschedule_confirm_prompt":    "Reporter votre rendez-vous avec {doctor_name} le {date} à {time} ? Répondez 'oui' pour continuer.",
            "reschedule_aborted":           "Report annulé. Puis-je vous aider avec autre chose ?",
            "ask_reschedule_date":          "Quelle nouvelle date souhaitez-vous pour votre rendez-vous ?",
            "ask_reschedule_time":          "Quelle nouvelle heure préférez-vous ?",
            "reschedule_success":           "Votre rendez-vous a été reporté au {date} à {time}.",
            "reschedule_failed":            "Le report a échoué. Ce créneau est peut-être indisponible. Essayez une autre heure.",
            "reschedule_slot_unavailable_with_alternatives": "{requested_time} n'est pas disponible ce jour-là.\n\nVoici les créneaux disponibles :\n\n{slots}\n\nLequel préférez-vous ?",
            "reschedule_slot_reselect_prompt":              "Veuillez choisir parmi les créneaux disponibles :\n\n{slots}",
            "reschedule_no_slots_for_date": "Aucun créneau disponible le {date}. Quelle nouvelle date souhaitez-vous ?",
            "reschedule_next_available_slots": "Les prochains créneaux disponibles sont le {date} :\n\n{slots}\n\nLequel préférez-vous ?",
            "reschedule_time_slots":          "Voici les horaires disponibles le {date} :\n\n{slots}\n\nLequel préférez-vous ?",
            "reschedule_no_next_available":   "Aucune disponibilité à venir pour ce médecin. Veuillez essayer une date précise.",
            # ── Reminder ─────────────────────────────────────────────────────
            "reminder_saved":          "Bien noté. Je vous rappellerai {hours} heure(s) avant chaque rendez-vous.",
            "reminder_invalid":        "Combien d'heures avant votre rendez-vous souhaitez-vous être rappelé ? (ex. '2 heures avant')",
            # ── Personalization ──────────────────────────────────────────────
            "suggest_usual_doctor":    "Souhaitez-vous reprendre rendez-vous avec {name}, votre {specialty} habituel·le ?",
            # ── Récupération guidée (aucun créneau disponible) ───────────────
            "recovery_options": (
                "Aucun rendez-vous n'est disponible le {date} avec {doctor_name}.\n\n"
                "Que souhaitez-vous faire ?\n\n"
                "1. Essayer une autre date\n"
                "2. Voir le prochain rendez-vous disponible\n"
                "3. Choisir un autre médecin\n"
                "4. Trouver des médecins à proximité"
            ),
            "recovery_try_date":           "Quelle date souhaitez-vous essayer ?",
            "recovery_searching_doctor":   "Je recherche un autre {specialty} pour vous.",
            "recovery_searching_nearby":   "Je recherche des options {specialty} à proximité.",
            "recovery_next_available":          "Le prochain rendez-vous disponible avec {doctor_name} est le {date}.\n\nÀ quelle heure préférez-vous ?",
            "recovery_next_available_slots":    "Les prochains créneaux disponibles avec {doctor_name} sont :\n\n{slots}\n\nLequel préférez-vous ?",
            "recovery_no_next_available":  (
                "Aucun rendez-vous à venir n'est disponible avec {doctor_name}.\n\n"
                "1. Essayer une autre date\n"
                "3. Choisir un autre médecin\n"
                "4. Trouver des médecins à proximité"
            ),
            "recovery_choice_invalid": (
                "Je n'ai pas compris. Veuillez choisir :\n\n"
                "1. Essayer une autre date\n"
                "2. Voir le prochain rendez-vous disponible\n"
                "3. Choisir un autre médecin\n"
                "4. Trouver des médecins à proximité"
            ),
        },
        "arabic": {
            # ── Booking ──────────────────────────────────────────────────────
            "ask_specialty":           "ما نوع الطبيب الذي تبحث عنه؟",
            "ask_date":                "ما هو التاريخ الذي تفضله؟",
            "ask_again_date":          "لم أفهم التاريخ. ما هو التاريخ الذي تريده؟",
            "ask_time":                "ما هو الوقت الذي تفضله؟",
            "ask_again_time":          "لم أفهم الوقت. ما هو الوقت الذي تفضله؟",
            "doctor_found":            "لقد وجدت {name}.",
            "doctors_found":           "لقد وجدت هؤلاء الأطباء:",
            "doctor_prompt":           "أي طبيب تريد اختياره؟",
            "booking_success":         "تم حجز موعدك بنجاح.",
            "slot_unavailable":        "هذا الموعد غير متاح.\n\nالأوقات المتاحة:\n{slots}",
            "slot_unavailable_with_alternatives": "{requested_time} غير متاح.\n\nالأوقات المتاحة:\n\n{slots}\n\nأيها تفضل؟",
            "no_slots":                "لم يتم العثور على مواعيد متاحة لهذا التاريخ.",
            "no_slots_suggest_date":   "لا توجد مواعيد متاحة في هذا التاريخ. هل تريد تجربة تاريخ آخر؟",
            # ── استكشاف الإتاحة (النمط 1) ─────────────────────────────────────
            "next_available_slots":    "إليك أقرب المواعيد المتاحة لـ {doctor_name}:\n\n{slots}\n\nأيها تفضل؟",
            "time_slots_for_date":     "إليك الأوقات المتاحة بتاريخ {date}:\n\n{slots}\n\nأيها تفضل؟",
            "no_next_available":       "لم يتم العثور على مواعيد متاحة قادمة لهذا الطبيب. ما هو التاريخ الذي تريد تجربته؟",
            "slot_reselect_prompt":    "يرجى اختيار أحد الأوقات المتاحة:\n\n{slots}",
            "invalid_selection":       "اختيار غير صحيح. يرجى اختيار رقم من القائمة.",
            "invalid_date":            "لم أتمكن من فهم هذا التاريخ. هل يمكنك المحاولة مجدداً؟ (مثال: 'غداً'، 'الجمعة'، '22/05/2026')",
            "invalid_time":            "لم أتمكن من فهم هذا الوقت. هل يمكنك المحاولة مجدداً؟ (مثال: '3 مساء'، '14:30')",
            # ── Appointment retrieval ─────────────────────────────────────────
            "no_appointments":         "ليس لديك مواعيد قادمة.",
            "appointments_header":     "إليك مواعيدك:",
            "appointment_line":        "• {index}. د. {doctor_name} — {date} الساعة {time} ({status})",
            "select_appointment":      "أي موعد؟ أجب برقمه.",
            "appointment_not_found":   "لم أجد هذا الموعد. يرجى اختيار رقم صحيح.",
            # ── Cancellation ─────────────────────────────────────────────────
            "cancel_confirm_prompt":   "هل تريد إلغاء موعدك مع {doctor_name} بتاريخ {date} الساعة {time}؟ أجب بـ 'نعم' للتأكيد.",
            "cancel_success":          "تم إلغاء موعدك مع {doctor_name} بتاريخ {date}.",
            "cancel_confirm":          "تم استلام طلب الإلغاء.",
            # ── Reschedule ───────────────────────────────────────────────────
            "reschedule_confirm_prompt":    "هل تريد تأجيل موعدك مع {doctor_name} بتاريخ {date} الساعة {time}؟ أجب بـ 'نعم' للمتابعة.",
            "reschedule_aborted":           "تم إلغاء التأجيل. هل تحتاج إلى مساعدة في شيء آخر؟",
            "ask_reschedule_date":          "ما هو التاريخ الجديد الذي تريده لموعدك؟",
            "ask_reschedule_time":          "ما هو الوقت الجديد الذي تفضله؟",
            "reschedule_success":           "تم تأجيل موعدك إلى {date} الساعة {time}.",
            "reschedule_failed":            "فشل التأجيل. قد يكون هذا الوقت غير متاح. حاول وقتاً آخر.",
            "reschedule_slot_unavailable_with_alternatives": "{requested_time} غير متاح في ذلك اليوم.\n\nالأوقات المتاحة:\n\n{slots}\n\nأيها تفضل؟",
            "reschedule_slot_reselect_prompt":              "يرجى اختيار أحد الأوقات المتاحة:\n\n{slots}",
            "reschedule_no_slots_for_date": "لا توجد مواعيد متاحة في تاريخ {date}. ما هو التاريخ الجديد الذي تريده؟",
            "reschedule_next_available_slots": "المواعيد المتاحة التالية هي بتاريخ {date}:\n\n{slots}\n\nأيها تفضل؟",
            "reschedule_time_slots":          "إليك الأوقات المتاحة ليوم {date}:\n\n{slots}\n\nأيها تفضل؟",
            "reschedule_no_next_available":   "لا توجد مواعيد متاحة قادمة لهذا الطبيب. يرجى تحديد تاريخ محدد.",
            # ── Reminder ─────────────────────────────────────────────────────
            "reminder_saved":          "تم الحفظ. سأذكّرك قبل {hours} ساعة/ساعات من كل موعد.",
            "reminder_invalid":        "كم ساعة قبل موعدك تريد أن تُذكَّر؟ (مثال: 'ساعتان قبل')",
            # ── Personalization ──────────────────────────────────────────────
            "suggest_usual_doctor":    "هل تريد حجز موعد مع {name} مجدداً، طبيبك المعتاد في {specialty}؟",
            # ── الاسترداد الموجّه (لا مواعيد متاحة) ─────────────────────────
            "recovery_options": (
                "لا تتوفر مواعيد في تاريخ {date} مع {doctor_name}.\n\n"
                "ماذا تريد أن تفعل؟\n\n"
                "1. تجربة تاريخ آخر\n"
                "2. رؤية أقرب موعد متاح\n"
                "3. اختيار طبيب آخر\n"
                "4. البحث عن أطباء قريبين"
            ),
            "recovery_try_date":           "ما هو التاريخ الذي تريد تجربته؟",
            "recovery_searching_doctor":   "سأبحث عن {specialty} آخر لك.",
            "recovery_searching_nearby":   "سأبحث عن خيارات {specialty} قريبة منك.",
            "recovery_next_available":          "أقرب موعد متاح مع {doctor_name} هو بتاريخ {date}.\n\nما هو الوقت الذي تفضله؟",
            "recovery_next_available_slots":    "المواعيد المتاحة التالية مع {doctor_name} هي:\n\n{slots}\n\nأيها تفضل؟",
            "recovery_no_next_available":  (
                "لا توجد مواعيد قادمة متاحة مع {doctor_name}.\n\n"
                "1. تجربة تاريخ آخر\n"
                "3. اختيار طبيب آخر\n"
                "4. البحث عن أطباء قريبين"
            ),
            "recovery_choice_invalid": (
                "لم أفهم اختيارك. يرجى الاختيار:\n\n"
                "1. تجربة تاريخ آخر\n"
                "2. رؤية أقرب موعد متاح\n"
                "3. اختيار طبيب آخر\n"
                "4. البحث عن أطباء قريبين"
            ),
        },
    }

    @classmethod
    def get(cls, language: str, key: str, **kwargs) -> str:
        lang = (language or "english").lower()
        template = (
            cls._R
            .get(lang, cls._R["english"])
            .get(key, cls._R["english"].get(key, key))
        )
        return template.format(**kwargs) if kwargs else template
