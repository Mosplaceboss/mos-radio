LiveDJ production helpers (source of truth on the Radio/Office platform is D:\MPR).

Deploy scripts from this folder to:
  D:\MPR\Engines\LiveDJ\Scripts\
    Producer.py
    break_continuity.py
    break_structure.py
    livedj_human_dj_rules.py
    livedj_events.py
    SeventiesOnThisDay.py
    MusicHistory.py
  D:\MPR\Tools\
    enrich_music_history_days.py
    verify_music_birthdays.py
    verify_break_structure.py
  D:\MPR\Application\
    schedule_mission_catalog.py

Operator folders on the platform:
  D:\MPR\This Day in History
  D:\MPR\On this Day 1970's

Mo Mon-Fri 10:45 = This Day in Music History
Casey Sat/Sun 10:45 = On This Day in the 70s (1970-1979 only)

Break structure (required behavior):
  Standard generated breaks need a natural opening/lead-in, conversational delivery of the
  supplied content item, and a natural exit. Source notes from daily content are facts to
  paraphrase — not finished scripts — unless the break is a station alert or approved custom script.
  Verify with: python Tools/LiveDJ/verify_break_structure.py
