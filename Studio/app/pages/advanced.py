"""Advanced tools hub for technical operators."""

from __future__ import annotations

from app.pages.hub_page import HubPage


class AdvancedPage(HubPage):
    page_id = "advanced"
    page_title = "Advanced"
    page_subtitle = "Technical tools for connections, imports, and deep configuration"
    page_help = "These screens are for station operators and technical staff. Day-to-day programming does not require them."

    hub_links = (
        ("platform_manager", "Platform Manager", "Set and test every production folder path used by Studio."),
        ("connection", "Connection Setup", "Link Studio to station computers and import live settings."),
        ("livedj", "LiveDJ Tools", "Import, validate, and publish LiveDJ configuration."),
        ("automation", "Automation Manager", "Legacy automation controls, service health, and module logs."),
        ("news", "Live News Integration", "Import, publish, and restore the live news automation configuration."),
        ("settings", "Settings", "Station preferences, themes, and operation mode."),
    )
