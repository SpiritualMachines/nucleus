# Changelog

All notable changes to Nucleus will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


---

## [0.9.81] - 2026-04-23

### Added

#### Version and Links in Daily Acitivity Email
- Added Nucleus version number, User Manual link and Change Log link in the Daily Acitivity Report email.

### Fixed 

#### Fixed Daily Acitivity Email
- Fixed Incorrect Member Reporting in Daily Acitivity Email.

#### Fixed Table Sizing and Duplicated Scrolls Bars on Mac OS
- Fixed the transactions table sizing on the Transactions tab.
- Fixed the duplicated scroll bars on multiple tabs.

#### Removed Default Export Filetype Setting
- Remvoed the defualt export filetype dropdown in settings that is no longer functional. 

___


## [0.9.8] - 2026-04-17

### Added

#### Moved Nested Cart
- On Purchases tab, moved nested cart from Step 1. to above the process transaction buttons.

#### Theme Setting
- Added ability to change and set default theme to settings under branding.

#### Products/Services Report
- Added ability to run periodic reports on the sales of products and services.

#### Transactions Tab
- Added a dedicated Transactions tab after Purchases (staff/admin only) with a flat, always-visible table showing all activity: Square/POS transactions, day pass activations, and free-tier membership activations.
- Added ability to edit transactions details.
- Added abiltiy to edit transaction allocation without issuing a refund.

#### DayPass Table
- Extracted day pass records out of the UserCredits table into a dedicated DayPass table. Existing daypass rows are automatically migrated on first launch.  

#### Added Header Links
- Added custom header with project links and link to User Manual.

#### Daily Acitivity Email
- Changed so Trasanctions is broken up into two tables. One table showing the past 24hrs and a second showing the past 7 days.
- Added row indicating number of Free "Promotional Memberships Activated".

#### Label Changes
- In settings renamed "Product Categories" to "Services" and "Inventory" to "Products".

#### layout/UI
- Layout and UI improvements


___


## [0.9.79] - 2026-04-02

### Added

#### Added Monthly Transaction Report
- Added the ability to enable a monthly transaction report to sends out an email that contains tables of all the Square transactions and all of the cash transactions with totals.

#### Added and Adjusted Manual Reports
- Changed layout for Period Transaction Report and make existing report layout for said button Period User Activity Transaction Report. 

### Fixed

#### Improved Update Tool
- Improved the update tool so it properly updates the application files without running into permission errors.

---

## [0.9.78] - 2026-03-27

### Added

#### Added Auto Update Script
- Expanded update.py script functionality to be an auto update script.

#### Added Transaction Refunds
- Added the ability to refund cash and Square transactions.

#### Push Cash to Square Toggle
- Added ability to toggle pushing cash transactions to Square on and off.

#### Improved Purchases Tab UI
- Cleaned up UI on purchases tab for readability; made subsections collapsable.

### Fixed

#### Cash Details Error
- Fixed cash_details error when processing a cash transaction. 

___

## [0.9.77] - 2026-03-24

### Added

#### Error Email Notifications
- Added a setting to email staff whenever a severity error notification is triggered in the application. When enabled, the error message and traceback context (if available) are sent to the configured address via the existing Resend integration. Configured in Settings under Email and Notifications with a toggle and a recipient email field.

___

## [0.9.76] - 2026-03-17

## Fixed

#### Daily Reports to Multiple Email Addresses
- Fixed a bug where the validation through an error when multiple email addresses were entered.

#### Daily Report Duplicate Send on Restart
- Fixed a bug where the daily report email would resend on app restart even if it had already been sent that day. The last-sent date is now persisted in the database.

#### Crash When Editing User With Legacy Role
- Fixed a crash in Staff Tools when editing a user whose role did not match the current role options. Legacy role values are now automatically normalised during database migration.


### Added

#### USER_MANUAL.md
- Added a detailed user manual to make it easier for non-technical individuals to set up the app.

#### UI/UX
- Changes to user interface to improve user experience. 


___

## [0.9.75] - 2026-03-17

### Added

#### Daily Reports to Multiple Email Addresses
- Now able to enter multiple email addresses seperated by a comma to send daily reports to

#### Major Refactor
- Major code refactor for reliability and readability


___

## [0.9.74] - 2026-03-16

### Added

#### View/Edit Storage Entries
- Can now view and edit storage entries by 2 new buttons added

#### Backup Chanages and Emailing Backups
- Can now set backup time and frequency
- Can now enable email backups of database

#### Code Refactoring
- Split some script files for readability


___

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
