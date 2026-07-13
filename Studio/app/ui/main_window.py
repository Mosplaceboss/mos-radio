"""Main application window shell."""

from __future__ import annotations

import os
import tkinter as tk
from typing import Type

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from app.core.config_manager import ConfigManager
from app.core.setup_wizard_model import setup_required
from app.core.user_modes import ADVANCED_ONLY_PAGES, USER_MODE_ADVANCED, page_allowed, verify_advanced_password
from app.pages.advanced import AdvancedPage
from app.pages.advertising import AdvertisingPage
from app.pages.advertising_manager import AdvertisingManagerPage
from app.pages.automation import AutomationPage
from app.pages.base_page import BasePage
from app.pages.broadcasting_manager import BroadcastingManagerPage
from app.pages.connection import ConnectionSetupPage
from app.pages.daily_operations import DailyOperationsPage
from app.pages.dashboard import DashboardPage
from app.pages.help import HelpPage
from app.pages.inventory import InventoryPage
from app.pages.livedj import LiveDJPage
from app.pages.music_manager import MusicManagerPage
from app.pages.news_content_manager import NewsContentManagerPage
from app.pages.news import NewsPage
from app.pages.operations_manager import OperationsManagerPage
from app.pages.personalities import PersonalitiesPage
from app.pages.platform_manager import PlatformManagerPage
from app.pages.programming_manager import ProgrammingManagerPage as ProgrammingPage
from app.pages.reports import ReportsPage
from app.pages.requests import RequestsPage
from app.pages.schedule import SchedulePage
from app.pages.settings import SettingsPage
from app.pages.setup_wizard import SetupWizardPage
from app.pages.station_information import StationInformationPage
from app.pages.station_manager import StationManagerPage
from app.pages.updates import UpdatesPage
from app.pages.voice_library import VoiceLibraryPage
from app.pages.website_audience_manager import WebsiteAudienceManagerPage
from app.ui.banner import BannerBar
from app.ui.navigation import NavigationPanel
from app.ui.status_bar import StatusBar
from app.ui.theme import StudioTheme


class MainWindow(ttk.Frame):
    """Hosts navigation, banner, page content, and status bar."""

    PAGE_CLASSES: dict[str, Type[BasePage]] = {
        "daily_operations": DailyOperationsPage,
        "station_manager": StationManagerPage,
        "dashboard": DashboardPage,
        "help": HelpPage,
        "programming": ProgrammingPage,
        "music_manager": MusicManagerPage,
        "personalities": PersonalitiesPage,
        "voice_library": VoiceLibraryPage,
        "schedule": SchedulePage,
        "requests": RequestsPage,
        "advertising_manager": AdvertisingManagerPage,
        "advertising": AdvertisingPage,
        "website_audience_manager": WebsiteAudienceManagerPage,
        "news_content_manager": NewsContentManagerPage,
        "inventory": InventoryPage,
        "broadcasting_manager": BroadcastingManagerPage,
        "operations_manager": OperationsManagerPage,
        "reports": ReportsPage,
        "settings": SettingsPage,
        "platform_manager": PlatformManagerPage,
        "advanced": AdvancedPage,
        "setup_wizard": SetupWizardPage,
        "updates": UpdatesPage,
        "news": NewsPage,
        "automation": AutomationPage,
        "connection": ConnectionSetupPage,
        "livedj": LiveDJPage,
        "station_information": StationInformationPage,
    }

    STARTUP_PAGES = frozenset(NavigationPanel.PRIMARY_PAGES)

    def __init__(self, master: tk.Misc, config_manager: ConfigManager) -> None:
        super().__init__(master, style="Studio.TFrame")
        self.config_manager = config_manager
        self._pages: dict[str, BasePage] = {}
        self._current_page_id: str | None = None

        settings = config_manager.load("settings")
        station_name = settings.get("station_name", "Mo's Place Radio")

        self._banner = BannerBar(self, station_name=station_name, settings=settings)
        self._banner.pack(fill="x", side="top")

        body = ttk.Frame(self, style="Studio.TFrame")
        body.pack(fill="both", expand=True)

        self._content = ttk.Frame(body, style="Studio.TFrame")

        self._navigation = NavigationPanel(body, on_navigate=self.show_page, settings=settings)
        self._navigation.pack(side="left", fill="y")

        self._content.pack(side="left", fill="both", expand=True)

        self._status_bar = StatusBar(self, config_manager)
        self._status_bar.pack(fill="x", side="bottom")

        if setup_required(settings):
            start_page = "setup_wizard"
        elif settings.get("user_mode") == "staff":
            start_page = "daily_operations"
        else:
            start_page = settings.get("last_page", "daily_operations")
        if start_page not in self.STARTUP_PAGES and start_page not in self.PAGE_CLASSES:
            start_page = "daily_operations"
        if not page_allowed(start_page, settings) and start_page != "setup_wizard":
            start_page = "daily_operations"
        self.show_page(start_page)

    def set_status(self, message: str) -> None:
        self._status_bar.set_message(message)

    def refresh_shell(self) -> None:
        settings = self.config_manager.load("settings")
        self._banner.refresh(settings)
        self._navigation.refresh(settings)
        self._status_bar.refresh_meta()

    def show_page(self, page_id: str) -> None:
        if page_id not in self.PAGE_CLASSES:
            return

        settings = self.config_manager.load("settings")
        if setup_required(settings) and page_id != "setup_wizard" and os.environ.get("STUDIO_VERIFY") != "1":
            page_id = "setup_wizard"
        elif not page_allowed(page_id, settings):
            if page_id in ADVANCED_ONLY_PAGES:
                if not self._unlock_advanced(settings):
                    return
            elif os.environ.get("STUDIO_VERIFY") == "1":
                return
            else:
                Messagebox.show_warning("This screen is not available in your current operating mode.", "Access")
                return

        if self._current_page_id and self._current_page_id in self._pages:
            current = self._pages[self._current_page_id]
            if hasattr(current, "on_hide"):
                current.on_hide()
            current.pack_forget()

        if page_id not in self._pages:
            page_class = self.PAGE_CLASSES[page_id]
            self._pages[page_id] = page_class(
                self._content,
                config_manager=self.config_manager,
                on_status=self.set_status,
                on_navigate=self.show_page,
            )

        page = self._pages[page_id]
        page.pack(fill="both", expand=True)
        page.on_show()
        self._current_page_id = page_id
        self._navigation.select(page_id, notify=False)
        self.set_status(f"Ready — {page.page_title}")

        if page_id in self.STARTUP_PAGES and os.environ.get("STUDIO_VERIFY") != "1":
            if settings.get("last_page") != page_id:
                settings["last_page"] = page_id
                self.config_manager.save("settings", settings)

    def _unlock_advanced(self, settings: dict) -> bool:
        if os.environ.get("STUDIO_VERIFY") == "1":
            settings["user_mode"] = USER_MODE_ADVANCED
            self.config_manager._cache["settings"] = dict(settings)
            self.refresh_shell()
            return True

        from tkinter import simpledialog

        entered = simpledialog.askstring(
            "Advanced Access",
            "Enter the Advanced Mode password or leave blank to cancel:",
            show="*",
            parent=self,
        )
        if entered is None:
            return False
        if verify_advanced_password(settings, entered):
            settings["user_mode"] = USER_MODE_ADVANCED
            self.config_manager.save("settings", settings)
            self.refresh_shell()
            return True
        Messagebox.show_error("The password was not correct.", "Advanced Access")
        return False
