# Changelog

All notable changes to Nucleus will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.9.73] - 2026-03-12

### Added

#### Inventory Items
- New **Settings > Inventory** panel (admin only): add items with a name, optional description, and price; items appear in a table and can be deleted
- Inventory cart in the Manual Transaction section (Purchases tab, staff and admin): click any item in the available items table, set a quantity, and click **Add to Cart**; the same item added a second time merges its quantity
- Cart auto-fills the **Amount** field with the running total and the **Description** field with a summary of item names and quantities
- Staff can still edit Amount and Description manually after items are added to mix cart items with custom charges
- **Remove Selected** removes the highlighted cart row; **Clear Cart** empties it entirely
- **Clear Form** also clears the cart

#### Member Storage
- New **Storage** tab (staff and admin) for tracking items stored at the space
- Active assignments table: unit number, assigned name, item description, notes, charges flag, total, and assigned date
- **Assign Storage** button opens a modal where staff select the unit from a dropdown, enter a freeform name or search for a registered member, describe the item, and optionally record charges (unit type, unit count, cost per unit; total auto-calculates)
- **Remove Selected (Archive)** archives the selected assignment; archived records appear in a read-only history table below
- New **Settings > Storage Units** panel (admin only): create units with a unit number (auto-increments) and description (defaults to "Storage Bin", both editable), and delete units that have no active assignments

#### Square Recurring Membership Subscriptions
- Staff and admin can enrol a member in a Square recurring subscription from the Purchases tab by searching for a user and clicking **Activate Square Membership Subscription**
- The same action is available via the Member Action modal in the Reports tab
- Square handles billing entirely: it emails the member a payment link each billing cycle; no card data is stored in or processed by Nucleus
- Three new action buttons appear in the Purchases tab once a user is selected: Activate Square Membership Subscription, Cancel Subscription, and Poll Subscription Status
- New **Settings > Subscriptions** panel: configure the Square Plan Variation ID (created once in the Square Dashboard) and the billing timezone

#### Product Tier Templates
- Admins can define reusable membership and day pass tier templates in Settings > Product Categories
- Each membership tier stores a name, price, duration in days, optional consumables credits, and an optional description
- Each day pass tier stores a name, price, and optional description
- Add Membership and Add Day Pass dialogs now include an optional tier selector; choosing a tier auto-fills price, duration, and description fields
- When a membership tier with consumables credits is applied, those credits are automatically posted to the member's consumables balance after the membership is saved
- Selecting "Custom" in either dialog restores the original manual-entry behaviour


---

## [0.9.72] - 2026-03-09

### Added

#### Square Terminal Integration (Point of Sale)
- Push transactions to Square Terminal for Credit and Debit transactions
- Manual Transaction section added to the top of the Purchases tab (Staff and Admin): enter amount, customer name, email, phone, and description then send directly to the Square Terminal or record locally
- Transaction history table in the Purchases tab shows recent transactions with status and source; staff can select a row and check its live status from Square
- New Point of Sale tab in Settings (Admin only): enable or disable Square Terminal, switch between Sandbox and Production environments, configure Location ID, Device ID, and currency code, and save the access token as a write-only credential


---

## [0.9.71] - 2026-03-08

### Added

#### Added Resend API Email and Notifications
- Added ability to connect with resend.com/resend.dev email service via API

#### Added Option to Send Daily Membership and Community Contacts Report
- New `core/email_service.py` module delivers a daily membership summary email via the Resend API

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
