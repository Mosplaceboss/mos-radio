LiveDJ history helpers (source of truth on the Radio/Office platform is D:\MPR).

Deploy scripts from this folder to:
  D:\MPR\Engines\LiveDJ\Scripts\   (SeventiesOnThisDay.py, MusicHistory.py, livedj_events.py, FunDays.py)
  D:\MPR\Tools\                    (enrich_music_history_days.py, verify_music_birthdays.py)
  D:\MPR\Application\              (schedule_mission_catalog.py)

Operator folders on the platform:
  D:\MPR\This Day in History
  D:\MPR\On this Day 1970's

Mo Mon-Fri 10:45 = This Day in Music History
Casey Sat/Sun 10:45 = On This Day in the 70s (1970-1979 only)

Fun days that share a calendar date rotate: each LiveDJ break gets one
(FunDays.prompt_payload_for_break). The editor still lists all of today's
days. The preview uses FunDays.preview_prompt_payload.
On Edit Fun Day, Category is Fun Day or Serious Day. A Serious Day is one
respectful mention. Breast Cancer Awareness Month loads as Serious Day when
the saved record has no category yet.
