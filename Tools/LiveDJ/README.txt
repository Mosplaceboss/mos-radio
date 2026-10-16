LiveDJ history / topical helpers (source of truth on the Radio/Office platform is D:\MPR).

Deploy scripts from this folder to:
  D:\MPR\Engines\LiveDJ\Scripts\   (SeventiesOnThisDay.py, MusicHistory.py, LocalHeadlines.py, livedj_events.py)
  D:\MPR\Tools\                    (enrich_music_history_days.py, verify_music_birthdays.py, verify_local_headlines.py)
  D:\MPR\Application\              (schedule_mission_catalog.py)

Operator folders on the platform:
  D:\MPR\This Day in History
  D:\MPR\On this Day 1970's

Knowledge cache:
  D:\MPR\Knowledge\MusicHistoryToday.json
  D:\MPR\Knowledge\SeventiesOnThisDay.json
  D:\MPR\Knowledge\LocalHeadlinesToday.json

Mo Mon-Fri 10:45 = This Day in Music History
Casey Sat/Sun 10:45 = On This Day in the 70s (1970-1979 only)

Bailey / Kathy / Johnny J = optional today-only local news aside (WCVB RSS by default)
  - Engine hook (same pattern as MusicHistory):
      import LocalHeadlines
      block = LocalHeadlines.prompt_block_for_break(
          host=host, event_type=event_type, mission=mission
      )
      # append block to the AI prompt when non-empty
  - Only Check-In style breaks; never turns the break into a newscast
  - Only headlines dated today (America/New_York); grim topics filtered out
  - If the feed is empty/down, skip the aside and still generate the break
