LiveDJ history helpers (source of truth on the Radio/Office platform is D:\MPR).

Deploy scripts from this folder to:
  D:\MPR\Engines\LiveDJ\Scripts\   (SeventiesOnThisDay.py, MusicHistory.py, livedj_events.py, Bands.py)
  D:\MPR\Tools\                    (enrich_music_history_days.py, verify_music_birthdays.py, repair_bands_host.py)
  D:\MPR\Application\              (schedule_mission_catalog.py)

Operator folders on the platform:
  D:\MPR\This Day in History
  D:\MPR\On this Day 1970's
  D:\MPR\Events\Weekly Events.csv   ->   D:\MPR\Knowledge\BandsTonight.txt

Mo Mon-Fri 10:45 = This Day in Music History
Casey Sat/Sun 10:45 = On This Day in the 70s (1970-1979 only)

Reverend JJ = Band Announcements (BandsTonight.txt)
  - Schedule Host must be Reverend JJ — never Mo
  - Engine hook (same pattern as LocalHeadlines):
      import Bands
      block = Bands.prompt_block_for_break(
          host=host, event_type=event_type, mission=mission
      )
      # append block only when non-empty (Mo gets nothing)
  - Repair existing Mo rows:
      python Tools/LiveDJ/repair_bands_host.py
  - Friday/Saturday/Sunday Bea band-rundown wav files stay separate
