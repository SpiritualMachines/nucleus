# Nucleus User Manual

A complete guide to installing, configuring, and running the Nucleus Membership Management System for your hackerspace or makerspace.

---

## Table of Contents

1. [Installation and First Run](#1-installation-and-first-run)
2. [Creating Your First Admin Account](#2-creating-your-first-admin-account)
3. [Logging In](#3-logging-in)
4. [User Roles and Permissions](#4-user-roles-and-permissions)
5. [Settings (Admin Only)](#5-settings-admin-only)
   - [General](#51-general)
   - [Operations](#52-operations)
   - [Branding and Reporting](#53-branding-and-reporting)
   - [Security](#54-security)
   - [Point of Sale (Square Terminal)](#55-point-of-sale-square-terminal)
   - [Subscriptions (Square Recurring Billing)](#56-subscriptions-square-recurring-billing)
   - [Product Categories](#57-product-categories)
   - [Storage Units](#58-storage-units)
   - [Inventory](#59-inventory)
   - [Email and Notifications (Resend)](#510-email-and-notifications-resend)
   - [Backup](#511-backup)
6. [My Profile Tab](#6-my-profile-tab)
7. [Staff Tools Tab](#7-staff-tools-tab)
8. [Purchases Tab](#8-purchases-tab)
9. [Reports Tab](#9-reports-tab)
10. [Storage Tab](#10-storage-tab)
11. [Database Tab](#11-database-tab)
12. [Feedback Tab](#12-feedback-tab)
13. [Walk-In Visitors and Community Contacts](#13-walk-in-visitors-and-community-contacts)
14. [Public Purchase Screen (Kiosk Mode)](#14-public-purchase-screen-kiosk-mode)
15. [Automatic Background Tasks](#15-automatic-background-tasks)
16. [Updating Nucleus](#16-updating-nucleus)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Installation and First Run

### Requirements

- Python 3.12 or newer
- A terminal that supports modern text rendering (most terminals on Linux, macOS, and Windows Terminal work)

### Supported Platforms

- Fedora 43+
- Ubuntu 24.04 LTS
- Windows 11
- macOS 12+

### Step-by-Step Setup

1. **Download or clone the repository** to a folder on your computer.

2. **Open a terminal** and navigate to the project folder:
   ```
   cd /path/to/nucleus-dev
   ```

3. **Create a virtual environment and install dependencies:**

   On Linux or macOS:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   On Windows:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Create your first admin account** (see the next section).

5. **Launch the application:**
   ```
   python nucleus.py
   ```

---

## 2. Creating Your First Admin Account

Before you can log in, you need to create an administrator account. Run the setup script from the project folder:

```
python scripts/create_admin.py
```

You will be prompted to enter:
- An email address (this is your login username)
- A password (minimum 8 characters)

This creates a fully activated admin account and initializes the database. You only need to do this once.

If you later need to promote an existing member account to admin, use:
```
python scripts/promote_superuser.py
```

---

## 3. Logging In

When you start Nucleus, you will see the login screen with these options:

- **Email and Password fields** -- Enter your credentials to log in.
- **Register New Account** -- Opens the self-registration form for new members. Self-registered accounts require staff or admin approval before they can log in.
- **Community Contacts** -- Opens a walk-in visitor form that does not require an account (see Section 13).
- **Manual Purchase** -- Opens a public point-of-sale screen for processing transactions without logging in (see Section 14).

### Account Lockout

If the admin has configured a login attempt limit (see Security settings), accounts are temporarily locked for 30 minutes after too many failed password attempts.

---

## 4. User Roles and Permissions

Nucleus has four user roles. Each role determines what tabs and actions are available on the dashboard.

| Role | Description | Available Tabs |
|------|-------------|----------------|
| **Admin** | Full system access. Can manage settings, users, and the database. | My Profile, Staff Tools, Purchases, Reports, Storage, Database, Settings, Feedback |
| **Staff** | Can manage members, process transactions, and view reports. | My Profile, Staff Tools, Purchases, Reports, Storage, Feedback |
| **Member** | Active paying member. Can view their own data. | My Profile, Purchases (view only), Feedback |
| **Community** | Inactive or expired member. Lowest access. | My Profile, Purchases (view only), Feedback |

Members whose membership expires are automatically downgraded to the Community role. The timing depends on the grace period setting (see Section 5.2).

---

## 5. Settings (Admin Only)

The Settings tab is only visible to admin users. It contains a sidebar on the left with all settings categories. Click a category to switch to its panel.

### 5.1 General

- **Auto-Logout Timeout (minutes):** How long a session can sit idle before Nucleus logs the user out automatically. Default is 10 minutes. A countdown timer is shown at the bottom of the dashboard.

### 5.2 Operations

- **Membership Grace Period (days):** After a membership expires, Nucleus waits this many days before downgrading the member to the Community role. Set to 0 for immediate downgrade.
- **Day Pass Cost:** The default price of a day pass in your currency. Set to 0 for free day passes.
- **Max Concurrent Sign-Ins:** Limits how many people can be signed into the space at one time. Set to 0 for unlimited.
- **Backup Retention (days):** How many days to keep automatic backups. Older backups are deleted automatically. Set to 0 to keep all backups forever.

### 5.3 Branding and Reporting

- **Hackspace Name:** Your organization's full name. Used in reports and emails.
- **Tag Name:** A short label used on buttons and sign-in prompts (e.g., "Makerspace").
- **App Name:** The name shown in the application title bar.
- **ASCII Logo:** A text-based logo displayed on the login screen. Edit the text art in the text box.
- **Currency Name:** What your space calls its internal credit system (e.g., "Credits", "Bucks", "Tokens"). This label appears throughout the Purchases tab and member profiles.
- **Default Export Format:** Choose CSV or PDF as the default for report exports.
- **PDF Report Header Text:** A subtitle line printed below the title on all PDF exports (e.g., your organization name and tagline).
- **Staff Reply-To Email Address:** Shown on exported reports so recipients know who to contact.

### 5.4 Security

- **Minimum Password Length:** Enforced when members register or change their password. Default is 8 characters.
- **Max Login Attempts Before Lockout:** How many wrong passwords before the account is locked for 30 minutes. Set to 0 to disable lockout (unlimited attempts).
- **SQL Console Enabled:** Turns the raw SQL console on or off for the Database tab. Disabling this prevents all admins from running custom queries. Changes take effect on next login.

### 5.5 Point of Sale (Square Terminal)

This section configures Nucleus to process card payments through a Square Terminal device. If you do not use Square, leave this disabled and Nucleus will record transactions locally.

#### What You Need Before Starting

1. A **Square account** at [squareup.com](https://squareup.com).
2. A **Square Terminal** device (the physical hardware).
3. Your **Square Developer credentials** from [developer.squareup.com](https://developer.squareup.com):
   - An Access Token (sandbox for testing, production for live payments)
   - Your Location ID
   - Your Terminal Device ID

#### How to Find Your Square Credentials

1. **Access Token:**
   - Go to [developer.squareup.com](https://developer.squareup.com) and sign in.
   - Open your application (or create one).
   - Under **Credentials**, find the **Access Token**.
   - For testing, use the **Sandbox Access Token**.
   - For live payments, use the **Production Access Token**.
   - Keep these secret. Do not share them.

2. **Location ID:**
   - In the Square Developer dashboard, go to your application.
   - Under **Locations**, find and copy the Location ID for the location where your terminal is set up.

3. **Device ID:**
   - In your Square Dashboard (not the developer site), go to **Devices**.
   - Find your Terminal and note its Device ID.
   - Alternatively, after pairing (below), the device ID may appear in API responses.

#### Configuration Steps in Nucleus

1. Check the **Enable Square Terminal** box.
2. Select the **Environment**: choose **Sandbox** for testing or **Production** for live payments.
3. Paste your **Sandbox Access Token** and click **Save Sandbox Token**. The token is stored securely and will never be displayed again.
4. When you are ready for live payments, paste your **Production Access Token** and click **Save Production Token**.
5. Enter your **Location ID**.
6. Enter your **Device ID**.
7. Select your **Currency** (e.g., CAD, USD, GBP).
8. Click **Save POS Settings**.

#### Pairing Your Terminal

If your terminal is not receiving checkout requests from Nucleus, it needs to be paired for Terminal API use:

1. In Nucleus Settings > Point of Sale, click **Pair Terminal**. A pairing code will appear on screen.
2. On your physical Square Terminal:
   - Tap the three-dot menu icon.
   - Go to **Settings** then **Device**.
   - Tap **Pair for Terminal API**.
   - Enter the code shown in Nucleus.
3. Back in Nucleus, click **Check Pairing Status** to confirm the pairing succeeded.

You only need to pair the terminal once unless you reset it.

### 5.6 Subscriptions (Square Recurring Billing)

This feature lets you set up recurring monthly memberships through Square. Square handles the billing and payment collection automatically. No card data is stored in Nucleus.

#### What You Need Before Starting

1. Square must be configured and working (see Section 5.5).
2. A **Subscription Plan** created in the Square Dashboard:
   - Go to [squareup.com/dashboard](https://squareup.com/dashboard).
   - Navigate to **Subscriptions** (or **Recurring Payments**).
   - Create a new plan with your desired pricing and billing cycle.
   - After creating the plan, find the **Plan Variation ID** (a string like `D3KPJGMOWQQFJJGZIHHDBFDA`).

#### Configuration Steps in Nucleus

1. Paste your **Plan Variation ID** into the field.
2. Set the **Billing Timezone** to your local timezone (e.g., `America/Toronto`, `America/New_York`, `Europe/London`).
3. Click **Save Subscription Settings**.

#### Activating a Subscription for a Member

1. Go to the **Purchases** tab.
2. Search for the member in the "Existing User Transactions" section.
3. Click the member's row in the search results.
4. Click **Activate Square Membership Subscription**.
5. Confirm the member's details in the popup.
6. Square will email the member a payment link. The member completes payment directly with Square.

#### Checking Subscription Status

- Click **Poll All Subscriptions Now** in Settings > Subscriptions to check the status of all enrolled members.
- In the Purchases tab, select a member and click **Poll Subscription Status** to check an individual.
- Use **Cancel Subscription** to stop a member's recurring billing.

### 5.7 Product Categories

Product categories are reusable templates that auto-fill the price and duration when you add a membership or day pass for a member.

#### Membership Tiers

Create templates for your membership plans. For example:

| Name | Price | Duration (days) | Credits | Description |
|------|-------|-----------------|---------|-------------|
| Monthly Standard | 50.00 | 30 | 0.00 | Standard monthly membership |
| Annual Premium | 500.00 | 365 | 50.00 | Annual membership with $50 credits |

- **Name:** What appears in the dropdown when adding a membership.
- **Price ($):** The membership cost.
- **Duration (days):** How long the membership lasts.
- **Consumables Credits:** Bonus credits added to the member's balance when the membership is activated. Set to 0 for no bonus.
- **Description:** Optional notes.

To add a tier, fill in the fields and click **Add Membership Tier**. To remove one, click its row in the table then click **Delete Selected**.

#### Day Pass Tiers

Same concept as membership tiers, but for single-day passes. Fill in the name, price, and optional description, then click **Add Day Pass Tier**.

### 5.8 Storage Units

Storage units represent physical bins, lockers, shelves, or other spaces that members can use to store materials at your space.

- **Unit Number:** An identifier like "A-01", "B-12", etc. Auto-incremented but editable.
- **Description:** A label like "Storage Bin" or "Large Locker".

Click **Create Storage Unit** to add one. Units with active assignments cannot be deleted.

### 5.9 Inventory

Inventory items are products or services that staff can add to a transaction cart when processing a sale. For example: 3D printing filament, laser cutting time, snacks, or workshop fees.

- **Name:** What appears in the cart (e.g., "PLA Filament - 100g").
- **Description:** Optional detail.
- **Price ($):** The unit price.

Click **Add Item** to create one. To remove, click its row and click **Delete Selected**.

### 5.10 Email and Notifications (Resend)

Nucleus uses [Resend](https://resend.com) to send emails. Resend is an email delivery service with a free tier that is sufficient for most makerspaces.

#### What Resend is Used For

- **Daily activity summary reports** sent to admin/staff.
- **Transaction receipts** sent to customers after point-of-sale payments.
- **Database backup files** sent as email attachments (if configured).

#### Setting Up Resend

1. **Create a Resend account** at [resend.com](https://resend.com). The free tier allows 100 emails per day and 3,000 per month.

2. **Get your API key:**
   - After signing in to Resend, go to **API Keys** in the sidebar.
   - Click **Create API Key**.
   - Give it a name (e.g., "Nucleus") and select **Full Access** or **Sending Access**.
   - Copy the key. You will only see it once.

3. **Configure your sending domain** (recommended for production use):
   - In Resend, go to **Domains** and click **Add Domain**.
   - Enter your domain (e.g., `yourhackerspace.org`).
   - Resend will show you DNS records to add. You need to add these to your domain's DNS settings:
     - **SPF record** (TXT): Authorizes Resend to send on your behalf.
     - **DKIM records** (TXT or CNAME): Proves emails are authentic.
     - **DMARC record** (TXT): Tells receiving servers what to do with unauthenticated email.
   - Add these records through your domain registrar's DNS management panel (e.g., Cloudflare, Namecheap, GoDaddy, Google Domains).
   - Back in Resend, click **Verify** and wait for DNS propagation (can take a few minutes to 48 hours).
   - Once verified, you can send from any address at that domain (e.g., `reports@yourhackerspace.org`).

   If you skip domain setup, you can only send from `onboarding@resend.dev` (Resend's test address). This works for testing but emails may land in spam.

4. **Enter your settings in Nucleus** (Settings > Email and Notifications):
   - **Resend API Key:** Paste the key and click **Save Key**. The key is stored securely and will never be displayed again. The placeholder text will change to "Key configured" to confirm.
   - **From Email Address:** The sender address for all outgoing emails. Must be an address at a verified domain (e.g., `reports@yourhackerspace.org`) or `onboarding@resend.dev` for testing.
   - **Send Daily Report To:** One or more recipient email addresses, separated by commas (e.g., `admin@yourspace.org, board@yourspace.org`).
   - **Daily Report Send Time:** When to send the daily summary, in 24-hour format (e.g., `07:00` for 7 AM, `18:30` for 6:30 PM).
   - **Enable Daily Email Reports:** Check this box to activate daily report emails.
   - **Email receipts to customers:** Check this box to automatically email receipts after point-of-sale transactions (only sent when the customer's email address is provided).

5. Click **Save Email Settings**.

6. Click **Send Test Email** to verify everything works. You should receive a daily summary report at the configured address within a few seconds.

#### What the Daily Report Contains

The daily report email includes:
- A 7-day activity summary table showing: active members, new registrations, expiring memberships, sign-ins, volunteers, day passes, transactions, and community contacts.
- A list of recent community contact visits with names and details.
- A list of recent point-of-sale transactions.

### 5.11 Backup

Nucleus can automatically back up its database on a daily schedule. Backups are saved to the `backups/` folder inside the project directory.

#### Configuration

- **Enable automatic backups:** Check this box to turn on the backup scheduler.
- **Backup Time:** When to create the daily backup, in 24-hour format (e.g., `02:00` for 2 AM).
- **Backup Retention (days):** How many days to keep old backups. Backups older than this are automatically deleted. Set to 0 to keep everything.
- **Email Backup To:** Optionally enter one or more email addresses (comma-separated) to receive the backup file as an attachment. Requires Resend to be configured (see Section 5.10).

Click **Save Backup Settings** to apply.

#### How Backups Work

- One backup is created per calendar day, named `db_backup_MMDDYY.db`.
- The scheduler checks every 60 seconds and runs at the configured time.
- If email delivery is configured, the backup file is sent as an attachment.
- Old backups are deleted based on the retention setting.

#### Manual Backup

You can also copy the `hackspace.db` file at any time while Nucleus is not running for a manual backup.

---

## 6. My Profile Tab

This tab is available to all logged-in users.

- **Account information:** Shows your name, role, account number, and credit balance.
- **Edit My Information:** Opens a form to update your personal details (name, phone, address, emergency contact, health information).
- **Change Password:** Opens a form to set a new password.
- **Sign In / Sign Out:** Records your physical presence at the space. The button changes between "Sign In" and "Sign Out" based on your current status.
- **Logout:** Ends your session and returns to the login screen.

### My Preferences

- **Preferred Visit Type:** If you set a preferred visit type (e.g., "Makerspace", "Workshop", "Volunteer"), you will be signed in automatically with that type instead of being asked each time. Leave it blank to always be prompted.

Click **Save Preferences** after making changes.

---

## 7. Staff Tools Tab

Available to Staff and Admin users.

### Register New Member (In-Person)

Opens the full registration form for staff to fill in while a new member is physically present. This is different from self-registration because:
- The account is activated immediately (no approval step needed).
- Staff confirm that they checked the member's ID.
- Staff explain the Terms of Service and Code of Conduct verbally.

### Quick User Search / Manage

Search for any user by name or email. Click a result row to open the **Member Action Menu** with these options:

1. **Edit User Profile / Role** -- Change any field on the user's account, including their role (admin, staff, member, community), status, and personal details.
2. **Add Membership** -- Activate a new membership period. Select from your pre-defined membership tiers or enter a custom price and duration.
3. **Edit Membership** -- View and modify existing memberships (extend, shorten, or cancel).
4. **Transaction (Credit/Debit)** -- Add or remove credits from the member's balance.
5. **Add Day Pass** -- Issue a single-day pass, optionally with credit bonus.
6. **View Day Pass History** -- See all day passes issued to this member.
7. **Edit Sign Ins** -- View and edit the member's space attendance records.
8. **Activate Square Subscription** -- Enroll the member in recurring billing through Square (see Section 5.6).

### Pending Approvals

Shows accounts that were created through self-registration and are waiting for approval. Select a row and click **Approve Selected Account** to activate it. The member can then log in.

---

## 8. Purchases Tab

### For Staff and Admin

#### Manual Transaction (Point of Sale)

This is where you process sales. The workflow has three steps:

**Step 1 -- Select Items (Optional):**
- The table shows all inventory items you have configured (see Section 5.9).
- Click an item row to select it, set the quantity, and click **Add to Cart**.
- The cart shows all selected items with quantities and subtotals.
- Use **Remove Selected** or **Clear Cart** to adjust.

**Step 2 -- Add Custom Item (Optional):**
- For charges not in your inventory (e.g., a workshop fee, donation, or one-off service).
- Enter an item name and price, then click **Add Custom Item**.

**Step 3 -- Customer Details:**
- Enter the customer's name (required).
- Enter their email (required if you want to send a receipt for cash transactions).
- Phone is optional.

**Processing the Transaction:**

- **Send to Square Terminal:** If Square is enabled, this sends the checkout to your physical terminal. The customer taps or inserts their card to pay. The transaction status is tracked in the table below.
- **Record Cash Transaction:** Records a cash payment. If Square is enabled and a Location ID is configured, the cash payment is also recorded in your Square Dashboard so your bookkeeper only has one system to reconcile. If Square is not enabled, the payment is recorded locally in Nucleus only.

**After the Transaction:**
- If the customer provided an email and receipts are enabled, a receipt email is sent automatically.
- The transaction appears in the **Recent Transactions** table.
- Click **Refresh** to update the table. Click **Check Terminal Status** to poll Square for a pending payment's status.

#### Existing User Transactions

Below the POS section, you can search for a registered member to manage their account:
- **Add Membership / Edit Memberships** -- manage membership periods.
- **Add Day Pass / View Day Passes** -- issue and view day passes.
- **Add / Deduct Credits** -- manage the member's credit balance.
- **View Credits** -- see the full transaction history.
- **Activate Square Subscription / Cancel / Poll Status** -- manage recurring billing (only available when Square is enabled).

### For Regular Members

Members see a read-only view of their own data:
- **My Memberships** -- a table of their membership periods.
- **My Day Passes** -- a table of day passes issued to them.
- **My Credits Ledger** -- a table of all credit/debit transactions and their current balance.

---

## 9. Reports Tab

Available to Staff and Admin users.

### Membership Report

Shows a filterable list of all users. Use the checkboxes to filter by role:
- Admin, Staff, Member (Active), Community (Inactive), Signed In

Click **Refresh Report** to reload. Click any row to open the Member Action Menu (same as Staff Tools search).

**Export Options:**
- **Export CSV** -- saves the table as a spreadsheet-compatible file.
- **Export PDF** -- saves a formatted PDF report.

### Period Traction Report

A detailed activity summary for a custom date range. Includes memberships, day passes, transactions, sign-ins, community contacts, and safety training records. Available as CSV or PDF.

### Community Contacts Report

All walk-in visitor records for a chosen date range. Useful for tracking community outreach. Available as CSV or PDF.

### Everything People CSV Report

A comprehensive export of all member data in the system. Exports as CSV only.

---

## 10. Storage Tab

Available to Staff and Admin users. Used to track physical storage spaces assigned to members (bins, lockers, shelves).

### Active Storage Assignments

Shows all current assignments with: unit number, who it is assigned to, what is stored, notes, charge type, total charged, and date assigned.

- **Assign Storage:** Opens a form to create a new assignment. Select a unit from the dropdown, enter the member's name or account number, describe what is being stored, and optionally set charges.
- **View Selected:** Opens a read-only detail view of the selected assignment.
- **Edit Selected:** Opens an editable form for the selected assignment.
- **Remove Selected (Archive):** Marks the assignment as archived. The unit becomes available for reassignment. The record moves to the archived table below.
- **Refresh:** Reloads both tables.

### Archived Storage Assignments

Shows historical assignments that have been archived. Read-only.

---

## 11. Database Tab

Available to Admin users only. Provides direct SQL access to the database for advanced queries.

### Security

The SQL console must first be unlocked by entering your admin password. This is an extra safety step because SQL queries can modify or delete data permanently.

The SQL console can be disabled entirely from Settings > Security.

### Pre-set Queries

Five common queries are available as buttons:
1. Users with medical/allergy information
2. Emergency contact list
3. Members missing safety orientation
4. User count by role
5. Attendance report for a date range

Click a button to load the query into the input field, then click **Execute SQL** to run it.

### Custom Queries

Type any SQL query in the input field and click **Execute SQL**. Results appear in the table below.

**Be careful:** UPDATE, DELETE, and DROP queries will modify your database permanently. There is no undo.

### Export Options

You can export query results as CSV or PDF using the buttons below the results table.

---

## 12. Feedback Tab

Available to all users.

### Submitting Feedback

1. Select at least one category: General Feedback, Feature Request, or Bug Report.
2. Optionally check **URGENT** to flag the submission.
3. Type your comment in the text field.
4. Click **Submit Feedback**.

### Viewing Feedback (Staff and Admin Only)

Staff and admin users see a table of all submitted feedback below the submission form. Click any row to view the full comment and add an admin response.

Feedback can be exported as CSV or PDF.

---

## 13. Walk-In Visitors and Community Contacts

The Community Contacts form is accessible from the login screen without needing an account. It is designed for walk-in visitors to your space.

### What the Form Collects

- **Required:** First name and email address.
- **Optional:** Last name, phone, postal code.
- **Demographics (optional):** Pronouns, age range, how they heard about your space, what brought them in.
- **Opt-in checkboxes:** Whether they want to receive updates, are interested in volunteering, or are interested in teaching/mentoring.

### Unknown Walk-In (Staff Shortcut)

If a visitor declines to provide details, staff can check the **Unknown Walk-In** box. This only requires a staff name and description (for accountability) and records the visit anonymously.

### Where the Data Goes

Community contact records appear in:
- The daily email report (if configured).
- The Community Contacts Report (Reports tab).

---

## 14. Public Purchase Screen (Kiosk Mode)

The **Manual Purchase** button on the login screen opens a simplified point-of-sale screen that works without logging in. This is useful if you set up a tablet or computer as a self-serve checkout kiosk.

It works the same as the staff Purchases tab (inventory cart, custom items, customer details, Square Terminal or cash), but:
- No member account is needed.
- The recent transactions table does not show customer names or emails for privacy (since the screen is shared).

---

## 15. Automatic Background Tasks

Nucleus runs three background tasks automatically when the application is open:

### Membership Expiry Check

- **Runs at:** 00:01 daily (and once at app startup).
- **What it does:** Checks all members with the "Member" role. If their membership has expired (past the grace period), their role is downgraded to "Community".

### Daily Email Report

- **Runs at:** The time configured in Settings > Email and Notifications (default 07:00).
- **What it does:** Sends the daily activity summary email to all configured recipients.
- **Requires:** Resend API key, at least one recipient email, and daily reports enabled.

### Database Backup

- **Runs at:** The time configured in Settings > Backup (default 02:00).
- **What it does:** Copies the database to the `backups/` folder. Optionally emails the backup file. Deletes old backups based on the retention setting.
- **Requires:** Backups enabled in settings.

All three tasks only run while Nucleus is open. If the application is closed at the scheduled time, the task will run the next time Nucleus is started (once per calendar day).

---

## 16. Updating Nucleus

When a new version of Nucleus is available:

1. Download or pull the updated code.
2. Activate your virtual environment.
3. Install any new dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the update script:
   ```
   python scripts/update.py
   ```
   This applies any database migrations needed for the new version and creates a backup of your database first.

5. Start Nucleus normally:
   ```
   python nucleus.py
   ```

---

## 17. Troubleshooting

### "Database file not found" when running scripts

Make sure you run scripts from the project root directory, not from inside the `scripts/` folder:
```
python scripts/create_admin.py     (correct)
cd scripts && python create_admin.py   (may not work)
```

### Emails are not being sent

1. Verify that your Resend API key is saved (Settings > Email and Notifications). The placeholder should say "Key configured".
2. Verify that "Enable Daily Email Reports" is checked.
3. Verify that you entered a recipient address in the "Send Daily Report To" field.
4. Click **Send Test Email** to test immediately.
5. If using a custom domain, verify that your DNS records are set up correctly in Resend's dashboard (check for a green "Verified" badge next to your domain).
6. If emails land in spam, set up SPF, DKIM, and DMARC records for your domain (Resend shows you exactly what records to add).

### Square Terminal is not receiving checkouts

1. Verify that "Enable Square Terminal" is checked in Settings > Point of Sale.
2. Verify that the correct environment is selected (Sandbox for testing, Production for live).
3. Verify that the access token, location ID, and device ID are all filled in and saved.
4. Try re-pairing the terminal (see Section 5.5).
5. Make sure the terminal is powered on, connected to the internet, and not in sleep mode.

### Members cannot log in after registering

Self-registered accounts must be approved by a staff or admin user. Go to the **Staff Tools** tab and check **Pending Approvals**.

### Session keeps timing out too quickly

Increase the auto-logout timeout in Settings > General. The default is 10 minutes.

### Cannot access Settings or Database tabs

These tabs are only visible to users with the Admin role. If you need admin access, ask an existing admin to change your role, or use `python scripts/promote_superuser.py`.
