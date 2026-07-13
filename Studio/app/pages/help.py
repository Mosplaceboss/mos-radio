"""Help — plain-English guide to Mo's Place Studio v2."""

from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText

from app.core.studio_info import APP_VERSION_LABEL, environment_mode
from app.pages.base_page import BasePage

MODULE_GUIDE = """
Daily Operations — Your everyday home screen. On-air status, service health, alerts, and approved daily actions.

First-Run Setup Wizard — Configure station name, logo, paths, and test connections without editing code.

Station Manager — Full control center with service health, alerts, and quick actions.

Dashboard — Summary view of services, schedule, module status, and recent activity.

Broadcasting — Monitor RadioDJ, Voicebox, automation watchers, audio output, and today's schedule.

Programming Manager — Plan shows, formats, clocks, schedules, and programming validation.

Music Manager — Browse and organize your music library in read-only mode.

Personalities — Manage on-air hosts, pictures, and show assignments.

Voice Library — Manage voice profiles used for announcements and automation.

Schedule — Weekly show schedule used across Studio modules.

Requests — Listener request settings.

Advertising Manager — Sponsors and campaigns.

Website & Audience Manager — Website content and audience planning.

News & Content Manager — News personalities, feeds, schedules, and output.

Inventory — Open Mo's Place Inventory and review scan reports (read-only).

Operations Manager — System status, backups, deployment packages, and migration staging.

Reports — Station reports and summaries.

Settings — Station name, theme, and operating mode (Owner, Staff, or Advanced).

Platform Manager — Advanced only. Set and test every folder path used by Studio.

Advanced — Technical tools such as Connection Setup, LiveDJ, updates, and legacy automation screens.
""".strip()

TODAY_CHECKLIST = """
What do I do today?
1. Open Daily Operations and click Refresh.
2. Review alerts and confirm RadioDJ, Voicebox, and watcher status.
3. Check current host, format, and now playing.
4. Review today's advertising and the next scheduled event.
5. Run approved actions only when needed (Open RadioDJ, Run News, restart watchers).
6. Use Owner or Advanced Mode for programming, backups, or path changes.
7. Create a backup in Operations Manager before major testing.
8. Read the guides in Documentation\\StudioGuides after install.
""".strip()

OPERATING_MODES = """
Operating Modes
- Owner Mode — Full production tools without advanced path editors.
- Staff Mode — Daily Operations, schedule, personalities, requests, and Help only.
- Advanced Mode — All tools including Platform Manager, updates, and Connection Setup.

Switch modes in Settings. Advanced screens require a password or confirmation.
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

        modes = ttk.Labelframe(self._body, text="Operating Modes", style="StudioCard.TLabelframe", padding=16)
        modes.pack(fill="x", pady=(0, 12))
        modes_text = ScrolledText(modes, height=6, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        modes_text.pack(fill="x")
        self._set_text(modes_text, OPERATING_MODES)

        modules = ttk.Labelframe(self._body, text="Module Guide", style="StudioCard.TLabelframe", padding=16)
        modules.pack(fill="both", expand=True)
        module_text = ScrolledText(modules, height=14, autohide=True, bootstyle="secondary", state="disabled", wrap="word")
        module_text.pack(fill="both", expand=True)
        self._set_text(module_text, MODULE_GUIDE)

    @staticmethod
    def _set_text(widget: ScrolledText, content: str) -> None:
        widget.text.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.text.configure(state="disabled")
