"""Studio installs News launcher files — no manual copy step."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Studio"))

from app.core.news_runtime import MANAGED_NEWS_FILES, ensure_news_runtime_scripts  # noqa: E402


def main() -> None:
    template = ROOT / "Studio" / "runtime" / "News"
    assert (template / "run_news_now.bat").is_file()
    assert (template / "build_bulletin.bat").is_file()
    assert (template / "build_bulletin.py").is_file()

    with tempfile.TemporaryDirectory() as tmp:
        news_dir = Path(tmp) / "Automation" / "News"
        # Leave a local-only engine hook and operator files alone.
        news_dir.mkdir(parents=True)
        engine = news_dir / "engine.local.cmd"
        engine.write_text("@echo off\nexit /b 0\n", encoding="utf-8")
        (news_dir / "news_copy.txt").write_text("keep me", encoding="utf-8")
        old_engine = engine.read_text(encoding="utf-8")

        ok, message = ensure_news_runtime_scripts(news_dir)
        assert ok, message
        for name in MANAGED_NEWS_FILES:
            assert (news_dir / name).is_file(), name
        assert engine.read_text(encoding="utf-8") == old_engine
        assert (news_dir / "news_copy.txt").read_text(encoding="utf-8") == "keep me"

        # Second pass is a no-op when files already match.
        ok2, message2 = ensure_news_runtime_scripts(news_dir)
        assert ok2, message2
        assert "already current" in message2.lower() or "already live" in message2.lower()

    # Studio Run News Now builds in-process after ensure (no manual copy).
    from app.core import operations

    with tempfile.TemporaryDirectory() as tmp:
        news_dir = Path(tmp) / "News"
        news_dir.mkdir(parents=True)
        run_bat = news_dir / "run_news_now.bat"
        run_bat.write_text("@echo off\n", encoding="utf-8")
        engine = news_dir / "engine.local.cmd"
        engine.write_text("@echo off\nexit /b 0\n", encoding="utf-8")

        integration = {
            "live_paths": {
                "news": {
                    "config": str(news_dir / "news.json"),
                    "start_script": str(news_dir / "start_tasks.bat"),
                    "restart_script": str(news_dir / "restart_tasks.bat"),
                    "run_now_script": str(run_bat),
                }
            },
            "engine_scripts": {},
        }

        with patch(
            "app.core.news_bulletin.write_bulletin",
            return_value=news_dir / "bulletin.txt",
        ) as write_mock, patch(
            "app.core.news_bulletin.next_air_label",
            return_value="7:15",
        ), patch.object(operations, "_run_script", return_value=(True, "engine ok")) as run_mock:
            ok, msg = operations.run_news_now(integration)
            assert ok, msg
            write_mock.assert_called_once()
            assert write_mock.call_args.kwargs["news_dir"] == news_dir
            run_mock.assert_called_once()
            assert run_mock.call_args.args[0] == engine
            assert (news_dir / "build_bulletin.py").is_file()

    print("OK: Studio installs news launcher files and Run News Now builds bulletin.txt")


if __name__ == "__main__":
    main()
