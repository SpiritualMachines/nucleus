# Nucleus

A membership management application for hackerspaces and makerspaces.
Built with a fast-to-deploy terminal UI and a platform-agnostic core library
designed to support a future web frontend.

**Current version:** 0.9.72
**License:** AGPLv3

---

## Screenshots

<img src="screenshots/LoginScreen.png" alt="Login Screen" width="800"/>
<img src="screenshots/ProfileScreen.png" alt="Member Profile" width="800"/>
<img src="screenshots/StaffToolsScreen.png" alt="Staff Tools" width="800"/>

---

## Features

- Member registration, approval, and profile management
- Membership tracking with automatic expiry and role downgrade
- Space sign-in and sign-out with visit type categorisation
- Day pass and consumables/credits ledger
- Safety training records (Orientation, WHMIS)
- Member feedback with staff response
- CSV and PDF exports for reports
- Staff and Admin tools including raw SQL console
- Automated daily database backups

## Tech Stack

| Layer | Library |
|---|---|
| UI | Textual |
| ORM | SQLModel |
| Database | SQLite |
| Auth | passlib[bcrypt] |
| PDF Export | fpdf2 |
| Email Validation | email-validator |
| Email Delivery | resend |

## Requirements

- Python 3.12
- See `requirements.txt` for all dependencies

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# Standard
python nucleus.py

# Dev mode (Textual live reload)
textual run --dev nucleus.py
```

## Scripts

| Script | Purpose |
|---|---|
| `./scripts/create_admin.py` | Create the initial admin account |
| `./scripts/promote_superuser.py` | Promote an existing account to Admin |
| `./scripts/seed_dummy_data.py` | Seed test member data |
| `./scripts/update.py` | Back up and migrate an existing deployed database |
**Security Warning: Delete the scripts directory after setup or migration after an update.**

## Email Reports (Resend)

Nucleus can send a daily membership summary email using the [Resend](https://resend.com) API.

### Setup

1. Create a free account at [resend.com](https://resend.com) and obtain an API key from the dashboard.
2. Optionally verify a sending domain in the Resend dashboard. Until a domain is verified, use `onboarding@resend.dev` as the From address (Resend's shared test sender — delivers only to the account owner's email).
3. Log in to Nucleus as an admin and open **Settings > Email and Notifications**.
4. Enter your Resend API key — it will be visible while you type and permanently hidden after you save.
5. Set the **From Email** (your verified domain address or `onboarding@resend.dev` for testing).
6. Set the **Send Daily Report To** address — the inbox where daily reports should arrive.
7. Tick **Enable Daily Email Reports** and click **Save Email Settings**.
8. Click **Send Test Email** to confirm delivery before relying on the automated schedule.

The daily report is sent automatically each morning when the app is running. It includes active member count, pending approvals, memberships expiring within 7 days, and sign-ins for the day.

## Square Terminal (Point of Sale)

Nucleus can process card payments through a paired Square Terminal device using the Square Terminal API.

### Requirements

- A [Square developer account](https://developer.squareup.com) with a Sandbox or Production application.
- The `squareup` Python package (included in `requirements.txt`).
- A Square Terminal device (1st or 2nd generation) running firmware that supports Terminal API peripheral mode.

### API Credentials Setup

1. Log in to the [Square Developer Dashboard](https://developer.squareup.com/apps).
2. Open your application and copy the **Access Token** for Sandbox (for testing) or Production.
3. Find your **Location ID** under Locations in the dashboard.
4. Log in to Nucleus as an admin and open **Settings > Point of Sale**.
5. Paste the Sandbox token and click **Save Sandbox Token**. Repeat for Production if needed.
6. Enter your Location ID and select the active environment (Sandbox or Production).
7. Click **Save POS Settings**.

### Pairing a Terminal Device

The Square Terminal must be paired once per installation to enter Terminal API peripheral mode. After pairing the terminal will display a blank screen with the Square logo and wait for checkout requests from Nucleus.

1. In Nucleus, open **Settings > Point of Sale** and click **Pair Terminal**.
   A short pairing code will appear on screen.
2. On the Square Terminal, tap the three-dot menu (top-right corner).
3. Go to **Settings > Device** and tap **Pair for Terminal API**.
4. Enter the code shown in Nucleus and confirm on the terminal.
5. Back in Nucleus, click **Check Pairing Status**. When pairing succeeds, the Device ID is shown — paste it into the **Device ID** field and click **Save POS Settings**.

**Note:** Pairing is per-installation. If you move the terminal to a different host or re-install Nucleus, repeat the pairing steps. The terminal can only be paired to one application at a time. To unpair, factory-reset the terminal or remove it from the Square Dashboard under Devices.

### Processing Transactions

Staff and admin users can process transactions from the **Purchases** tab.

- **Send to Square Terminal**: Sends the amount to the paired terminal for card or contactless payment.
- **Record Cash Transaction**: Records a cash payment locally without contacting the terminal. The description is prefixed with "Cash -" for easy identification in reports.
- **Check Terminal Status**: Fetches the current checkout status from Square for a selected transaction row.

All transactions — Square and cash — are stored in the local database for audit and reporting purposes.

## Database Migrations

Schema migrations are managed via `run_migrations()` in `core/database.py`.
This runs automatically on every app launch. When deploying an update to an
existing installation, run `./scripts/update.py` to create a backup and
apply any pending migrations manually.

When adding a new column to a model in `/core/models.py`, register it in
`run_migrations()` using `_verify_and_add_column()`.

## Project Structure

```
/nucleus.py        Main app entry point (Textual App class)
/core              Business logic and database models (no UI dependencies)
/screens           Textual UI screens and modals
/scripts           Admin and setup utilities
/theme             CSS (.tcss), policy documents, and settings
/backups           Automated daily and pre-migration database backups
/tests             Pytest suite
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE.md).
