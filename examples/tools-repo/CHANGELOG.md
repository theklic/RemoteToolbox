# Changelog

All notable changes to **my tools** are recorded here. This is your safety net:
when something breaks, the changelog tells you what changed and which commit/tag
to roll back to.

Format loosely follows [Keep a Changelog](https://keepachangelog.com). Newest at
the top. Tag known-good states in git (e.g. `git tag good-2026-06-08`) so you can
return to them quickly.

## [Unreleased]
### Added
- `hello` — starter greeting tool (from the template).

<!--
When you change tools, add an entry. Example:

## 2026-06-08
### Added
- `hue_lights` — turn living-room lights on/off via the Philips Hue API.
### Changed
- `weather` — switched provider; now returns wind speed too.
### Fixed
- `disk_free` — handle paths that don't exist instead of crashing.
### Removed
- `old_scraper` — site shut down.

Then commit, and optionally tag a good state:
    git add -A && git commit -m "hue_lights + weather wind speed"
    git tag good-2026-06-08
-->
