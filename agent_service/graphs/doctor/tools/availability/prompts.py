AVAILABILITY_PROMPT = """

Tool: availability
Role: understand doctor availability and free slot requests in French,
English, Arabic, and noisy spelling.

Choose one action:

* view_available_slots
* view_today_availability
* view_tomorrow_availability
* view_week_availability
* view_next_week_availability
* view_availability
* create_availability
* update_availability
* block_availability
* unblock_availability
* delete_availability

Important:

* Availability is not an appointment.
  """
