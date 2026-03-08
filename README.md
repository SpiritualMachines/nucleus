# Nucleus

A membership management application for hackerspaces and makerspaces.
Built with a fast-to-deploy terminal UI and a platform-agnostic core library
designed to support a future web frontend.

**Current version:** 0.9.7
**License:** AGPLv3

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
| `./scripts/update_db.py` | Back up and migrate an existing deployed database |
**Security Warning: Delete the scripts directory after setup or migration after an update.**

## Database Migrations

Schema migrations are managed via `run_migrations()` in `core/database.py`.
This runs automatically on every app launch. When deploying an update to an
existing installation, run `./scripts/update_db.py` to create a backup and
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
