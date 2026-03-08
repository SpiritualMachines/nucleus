# Changelog

All notable changes to Nucleus will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.9.7] - 2026-03-07

### Added

#### Sign In Visit Type
- Visit type selection modal prompts members at sign-in to categorise their visit
- Supported visit types: Workshop, Digital Creator, Digital Creator Camp, Volunteer, Volunteer and Visit
- Visit type stored on each SpaceAttendance record
- Staff can view and edit visit type on existing sign-in records via Edit Sign Ins modal

#### Sign In/Out Auto Logout
- Post sign-in/out countdown modal: 10-second auto-logout after signing in or out of the space, with a Stay Signed In button to cancel and reset the inactivity timer

#### Admin Settings Tab
- Admin-only Settings tab replacing settings.txt for runtime configuration
- Settings: Hackspace Name, Tag Name, App Name, ASCII Logo (editable), Auto-Logout Timeout
- Tag Name setting provides a short label (e.g. Makerspace) used on buttons and labels in place of the full space name
- Settings changes apply immediately without a restart
- Settings seeded from settings.txt on first run; stored in database thereafter
- Added several settings for administration and security

#### Database & Migrations
- Auto schema migration on app launch via `run_migrations()` in `core/database.py`
- `update_db.py` explicitly reads and reports values from settings.txt when seeding a new database

#### Community Contacts
- Walk-in contact form accessible from the login screen without requiring a member account
- Visit reason options: Curiosity, 3D Printing, Art, Photography, Film Making, Music/Audio, Referral, Ad/Promotion, Other
- New communitycontact database table, created automatically on first run

#### Admin and Statistic Reports
- Export Period Traction Report: Covers all memberships active during the period, day passes, consumable transactions, space sign-ins/outs, and community contact visits
- Export Community Contacts Report: date-range report of all community contact records with all fields; exports to CSV or PDF
- Export Everything People CSV Report: full dump of every person-related database table (users, memberships, dues, consumable transactions, day passes, attendance, safety training, community contacts, feedback) as a multi-section CSV

#### UI
- Selection modals (Visit Type, Member Actions) now use OptionList instead of stacked buttons, reducing vertical space usage

### Fixed

#### Password Change Fixed
- Password update modal crashed the app due to missing error handling in `update_user_password`

#### Consumables Table Auto Reload
- Consumables table did not refresh after a credit or debit transaction; balance column now updates automatically on success

#### Member Report Filters
- Filter checkboxes (Admin, Staff, Member, Community, Signed In) now immediately refresh the member table on toggle without needing to click Refresh Report
- Replaced "Signed In Only" post-filter with an additive "Signed In" checkbox consistent with the role filters; when checked, currently signed-in users are included alongside any role-filtered results

---

## [0.9.61] - Pre-existing
