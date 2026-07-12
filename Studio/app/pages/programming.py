"""Programming overview hub."""

from __future__ import annotations

from app.pages.hub_page import HubPage


class ProgrammingPage(HubPage):
    page_id = "programming"
    page_title = "Programming"
    page_subtitle = "Plan your station sound, hosts, and weekly schedule"
    page_help = "Use these screens to set who is on the air, which voices they use, and when each show runs."

    hub_links = (
        ("personalities", "Personalities", "Create and maintain your on-air host profiles."),
        ("voice_library", "Voice Library", "Assign station voices used by automation and announcements."),
        ("schedule", "Schedule", "Build the weekly show grid and music formats."),
        ("requests", "Requests", "Control when listeners can request songs."),
    )
