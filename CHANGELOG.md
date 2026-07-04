# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- **CRITICAL:** Position mode timer now works correctly with frequent GPS updates
  - Timer no longer resets on every GPS update when position is stable
  - Timer only resets when vehicle moves outside tolerance radius
  - Fixes issue where alarm would never activate if GPS updates were frequent (e.g., every 2 minutes)
- **Position mode activation delay**: Reduced from ~3 minutes to ~1 minute with `stationary_count=0`
  - Fixed early return optimization that was blocking first GPS event
  - Now allows first event to start timer even with unchanged GPS timestamp
- **Infinite counter growth**: Counter now capped at `stationary_count + 5` to prevent unlimited increment
- **Baseline GPS handling**: First GPS timestamp properly saved as reference without incrementing counter
- **Stop command behavior**: Position mode state now resets when alarm is deactivated
  - Counter, candidate, and GPS timestamps reset to allow fresh monitoring
  - Pending timer cancelled on alarm stop

### Added
- Position mode now sends notifications when activating after stationary detection
- Comprehensive Position Mode Guide (POSITION_MODE_GUIDE.md)
- Support for `stationary_count=0` (bypasses counter check, uses time only)
- **GPS baseline detection**: First GPS timestamp saved as reference for future comparisons
- **GPS timestamp deduplication**: Skips processing duplicate GPS updates to reduce log spam
- **Smart early return optimization**: Processes first event even with unchanged GPS to start timer
- Unit labels for configuration parameters (minutes, samples)
- Code comments explaining GPS updates vs webhooks
- **15+ new tests** for position mode edge cases:
  - Timer behavior with GPS updates
  - Early return optimization
  - Stop/reset behavior
  - Baseline GPS handling
  - Notification delivery

### Changed
- Improved configuration descriptions for Position mode parameters
- Updated all 7 translations with detailed explanations of stationary parameters
- Enhanced `stationary_help` message to explain all configuration options
- Changed minimum `stationary_count` from 1 to 0 to allow time-only detection
- **Optimized GPS processing**: Only processes events when GPS timestamp actually changes (when timer not running)

### Documentation
- Added POSITION_MODE_GUIDE.md - comprehensive guide covering:
  - How Position mode works (technical details)
  - Configuration parameters explained
  - Timer behavior and examples
  - Troubleshooting guide
  - Configuration examples for different use cases
- Updated README.md with Position mode improvements and links
- Cleaned up temporary development documentation files

---

## [2.0.0] - 2024

### Added
- Position mode notifications
- Multi-language support (7 languages)
- GPS freshness checking
- Waiting mode with optional notifications

### Fixed
- Various bug fixes and improvements

---

## [1.0.0] - 2024

### Added
- Initial release
- Basic position tracking
- Connection-based detection
- Manual mode support
- Webhook control interface
