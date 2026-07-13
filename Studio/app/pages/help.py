"""Help — plain-English guide to Mo's Place Studio v2."""

from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.studio_info import APP_VERSION, APP_VERSION_LABEL, environment_mode
from app.pages.base_page import BasePage

MODULE_GUIDE = """
Station Manager — Start here. See what is on the air, service health, alerts, and quick actions.

Dashboard — Summary view of services, schedule, module status, and recent activity.

Platform Manager — Set and test every folder path used by Studio. All modules use these paths.

Programming Manager — Plan shows, formats, clocks, schedules, and programming validation.

Music Manager — Browse and organize your music library in read-only development mode.

Personalities — Manage on-air hosts, pictures, and show assignments.

Voice Library — Manage voice profiles used for announcements and automation.

Schedule — Weekly show schedule used across Studio modules.

Requests — Listener request settings (development copy only in this build).

Advertising Manager — Sponsors and campaigns stored in StationData.

Website & Audience Manager — Website content and audience planning (development only).

News & Content Manager — News personalities, feeds, schedules, and development output.

Inventory — Open Mo's Place Inventory and review scan reports (read-only).

Broadcasting — Monitor RadioDJ, Voicebox, automation watchers, audio output, and today's schedule.

Operations Manager — System status, backups, deployment packages, and migration staging.

Reports — Station reports and summaries.

Settings — Station name, theme, and operation mode. Keep Development Mode until cutover.

Advanced — Technical tools such as Connection Setup, LiveDJ, and legacy automation screens.
""".strip()

TODAY_CHECKLIST = """
What do I do today?
1. Open Station Manager and review alerts.
2. Open Platform Manager and validate all paths are green or yellow.
3. Check Dashboard module overview for schedule, backup, and inventory status.
4. Open Broadcasting to confirm RadioDJ, Voicebox, and watcher health.
5. Use Programming, Music, and News managers to plan changes in development data.
6. Run Inventory if you need an updated folder map (read-only scan).
7. Create a backup in Operations Manager before any major testing.
8. Stay in Development Mode — live publishing is disabled in this build.
""".strip()


class HelpPage(BasePage):
    page_id = "help"
    page_title = "Help"
    page_subtitle = "Plain-English guide to Mo's Place Studio"
    page_help = "Use this page when you are not sure where to go next."

    def build(self) -> None:
        settings = self.config_manager.load("settings", {})
        header = ttk.Labelframe(self._body, text="Studio Version", style="StudioCard.TLabelframe", padding=16)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(
            header,
            text=f"{APP_VERSION_LABEL} · {environment_mode(settings)} Mode",
            style="StudioCard.TLabel",
        ).pack(anchor="w")

        today = ttk.Labelframe(self._body, text="What do I do today?", style="StudioCard.TLabelframe", padding=16)
        today.pack(fill="x", pady=(0, 12))
        today_text = ScrolledText(today, height=8, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        today_text.pack(fill="x")
        self._set_text(today_text, TODAY_CHECKLIST)

        modules = ttk.Labelframe(self._body, text="Module Guide", style="StudioCard.TLabelframe", padding=16)
        modules.pack(fill="both", expand=True)
        module_text = ScrolledText(modules, height=16, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        module_text.pack(fill="both", expand=True)
        self._set_text(module_text, MODULE_GUIDE)

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")
