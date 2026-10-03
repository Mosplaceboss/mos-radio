LiveDJ history helpers (source of truth on the Radio/Office platform is D:\MPR).

Deploy scripts from this folder to:
  D:\MPR\Engines\LiveDJ\Scripts\   (SeventiesOnThisDay.py, MusicHistory.py, livedj_events.py)
  D:\MPR\Tools\                    (enrich_music_history_days.py, verify_music_birthdays.py)
  D:\MPR\Application\              (schedule_mission_catalog.py)

Operator folders on the platform:
  D:\MPR\This Day in History
  D:\MPR\On this Day 1970's

Mo Mon-Fri 10:45 = This Day in Music History
Casey Sat/Sun 10:45 = On This Day in the 70s (1970-1979 only)

Format mention guards (livedj_events.py):
  Kathy must not mention Country / country music unless Format is Country.
  LB must not mention Yacht Rock unless Format is Yacht Rock.
  Prefer event_coaching_for_row / mission_text_for_row / finalize_schedule_row so bans reach prompts.
  Optional script check: banned_format_mentions_in_text(row, script).
  Verify with: python verify_host_format_mentions.py
