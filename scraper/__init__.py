"""BetterBlackboard scraper.

Authenticates to Blackboard with a persisted Playwright session and pulls
courses, assignments, announcements, grades, and calendar events into a
local SQLite database.

Personal-use only. Automated access to Blackboard may violate your
institution's terms of service — run this against your own account, on
your own hardware, and do not share the running dashboard publicly.
"""
