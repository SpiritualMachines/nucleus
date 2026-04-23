# Nucleus User Manual

A complete guide to installing, configuring, and using the Nucleus Membership Management System for your hackerspace or makerspace.

---

## Table of Contents

1. [Installation and First Run](#1-installation-and-first-run)
2. [Creating Your First Admin Account](#2-creating-your-first-admin-account)
3. [Logging In](#3-logging-in)
4. [Navigating the Dashboard](#4-navigating-the-dashboard)
5. [User Roles and Permissions](#5-user-roles-and-permissions)
6. [Settings (Admin Only)](#6-settings-admin-only)
   - [General](#61-general)
   - [Operations](#62-operations)
   - [Branding and Appearance](#63-branding-and-appearance)
   - [Security](#64-security)
   - [Point of Sale (Square Terminal)](#65-point-of-sale-square-terminal)
   - [Subscriptions (Square Recurring Billing)](#66-subscriptions-square-recurring-billing)
   - [Product Categories](#67-product-categories)
   - [Storage Units](#68-storage-units)
   - [Inventory](#69-inventory)
   - [Email and Notifications (Resend)](#610-email-and-notifications-resend)
   - [Backup](#611-backup)
7. [My Profile Tab](#7-my-profile-tab)
8. [Staff Tools Tab](#8-staff-tools-tab)
9. [Purchases Tab](#9-purchases-tab)
10. [Transactions Tab](#10-transactions-tab)
11. [Reports Tab](#11-reports-tab)
12. [Storage Tab](#12-storage-tab)
13. [Database Tab](#13-database-tab)
14. [Feedback Tab](#14-feedback-tab)
15. [Walk-In Visitors and Community Contacts](#15-walk-in-visitors-and-community-contacts)
16. [Public Purchase Screen (Kiosk Mode)](#16-public-purchase-screen-kiosk-mode)
17. [Automatic Background Tasks](#17-automatic-background-tasks)
18. [Updating Nucleus](#18-updating-nucleus)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. Installation and First Run

### What You Need

- **Python 3.12 or newer** installed on your computer. You can download it from [python.org](https://python.org). To check if you have it, open a terminal and type `python --version` or `python3 --version`.
- **A terminal application:**
  - On Linux: the built-in terminal (GNOME Terminal, Konsole, etc.)
  - On macOS: the built-in Terminal app, or iTerm2
  - On Windows: Windows Terminal (recommended, free from the Microsoft Store)

### Supported Operating Systems

- Fedora 43 or newer
- Ubuntu 24.04 LTS or newer
- Windows 11
- macOS 12 (Monterey) or newer

### Step-by-Step Setup

**Step 1 — Download Nucleus**

Download or clone the Nucleus project folder to your computer. Place it somewhere you will remember, such as your home folder or Documents.

**Step 2 — Open a terminal and navigate to the folder**

Open your terminal application and navigate into the Nucleus project folder. Replace the example path with wherever you put the folder:

```
cd /path/to/nucleus-dev
```

On Windows, paths use backslashes:
```
cd C:\Users\YourName\Documents\nucleus-dev
```

**Step 3 — Create a virtual environment**

A virtual environment keeps Nucleus's Python dependencies separate from the rest of your system. You only need to do this once.

On Linux or macOS:
```
python -m venv venv
source venv/bin/activate
```

On Windows:
```
python -m venv venv
venv\Scripts\activate
```

After activation, your terminal prompt will show `(venv)` at the beginning. This tells you the virtual environment is active.

**Step 4 — Install required packages**

```
pip install -r requirements.txt
```

This downloads and installs everything Nucleus needs to run. It may take a minute or two.

**Step 5 — Create your first admin account**

See the next section.

**Step 6 — Start Nucleus**

```
python nucleus.py
```

The login screen will appear. If you see an error about a missing database, make sure you ran the admin creation script first (Step 5 / Section 2).

> **Note:** Every time you want to run Nucleus, you must first activate the virtual environment (Step 3) before running `python nucleus.py`. The `(venv)` prefix tells you it is active.

---

## 2. Creating Your First Admin Account

Before you can log in, you need to create an administrator account. This only needs to be done once.

Make sure your virtual environment is active, then run:

```
python scripts/create_admin.py
```

You will be prompted to enter:
- An **email address** — this is the username you will use to log in. It does not have to be a real email address, but using a real one is recommended so you can receive daily reports and backups.
- A **password** — must be at least 8 characters long (this minimum can be changed later in Settings).

After you submit, Nucleus creates the database, runs all setup steps, and saves your admin account. You will see a confirmation message.

### Promoting an Existing Account to Admin

If you already have a regular member account and want to promote it to admin, run:

```
python scripts/promote_superuser.py
```

You will be asked for the email address of the account to promote.

---

## 3. Logging In

When you start Nucleus, you will see the login screen. It has several options:

- **Email** field and **Password** field — Enter your credentials and press Enter or click **Login** to access the dashboard.

- **Register New Account** — Opens the self-service registration form for new members to create their own account. Self-registered accounts are placed in a pending queue and must be approved by a staff or admin user before they can log in. (See Section 8 — Staff Tools.)

- **Community Contacts** — Opens the walk-in visitor form. This does not require a Nucleus account. Useful for tracking visitors and community outreach. (See Section 15.)

- **Manual Purchase** — Opens a simplified point-of-sale screen without requiring a login. Useful for setting up a self-serve kiosk or processing a quick sale. (See Section 16.)

### Account Lockout

If the admin has configured a maximum login attempt limit (see Section 6.4 — Security), entering the wrong password too many times will lock the account for 30 minutes. After 30 minutes, the account unlocks automatically.

---

## 4. Navigating the Dashboard

Once you are logged in, the dashboard is organized into tabs across the top of the screen. Click any tab to switch to it. Which tabs are visible depends on your role (see Section 5).

### The Top Bar

Just below the header, a row of links provides quick access to resources:

- **A Spiritual Machines Project** — opens the Spiritual Machines website.
- **View User Manual** — opens this manual on GitHub in your web browser.
- **View Change Log** — opens the Nucleus change log on GitHub, listing what has changed in each release. Note: because Nucleus runs in your terminal, links open in your default browser behind the terminal window. The note "(Link May Open Under App)" is a reminder to check your taskbar if the browser seems to not have opened.

### The Auto-Logout Timer

On the right side of the top bar, a countdown timer shows how many seconds remain before the session times out due to inactivity. Any interaction with the app resets the timer. When it reaches zero, Nucleus logs you out automatically. The timeout duration is configured in Settings (see Section 6.1).

### The Footer

At the very bottom of the screen, the footer shows available keyboard shortcuts. You can navigate between tabs using the arrow keys or by clicking.

---

## 5. User Roles and Permissions

Nucleus has four user roles. Your role determines which tabs and actions are available to you.

| Role | Description | Visible Tabs |
|------|-------------|--------------|
| **Admin** | Full access to all features, including Settings and the Database console. | My Profile, Staff Tools, Purchases, Transactions, Reports, Storage, Database, Settings, Feedback |
| **Staff** | Can manage members, process sales, view reports, and handle storage. | My Profile, Staff Tools, Purchases, Transactions, Reports, Storage, Feedback |
| **Member** | An active paying member. Can view their own memberships, day passes, and credit history. | My Profile, Purchases (read-only), Feedback |
| **Community** | An inactive or expired member with minimal access. | My Profile, Purchases (read-only), Feedback |

Members whose membership expires are automatically downgraded from Member to Community after a configurable grace period (see Section 6.2). An admin or staff member can manually change any user's role at any time through Staff Tools.

---

## 6. Settings (Admin Only)

The **Settings** tab is only visible to admin users. It contains a sidebar on the left with all available settings categories. Click a category name to switch to its panel on the right.

> **Important:** Most settings panels have their own **Save** button. Changes are not applied until you click save.

---

### 6.1 General

**Auto-Logout Timeout (minutes)**

How long a logged-in session can sit idle before Nucleus automatically logs the user out. The countdown timer in the top bar counts down from this value. The default is 10 minutes. Set a higher number if staff find themselves getting logged out too often during busy periods.

Click **Save General Settings** after making changes.

---

### 6.2 Operations

**Membership Grace Period (days)**

After a member's membership end date passes, Nucleus will wait this many days before changing their role from Member to Community. Setting this to 0 means their role is downgraded immediately when the membership expires. A grace period of 3 to 7 days gives members time to renew without losing access.

**Day Pass Cost**

The default price charged for a day pass, in your local currency. This amount is pre-filled when staff issue a day pass, but can be overridden at the time of sale. Set to 0 if day passes are free at your space.

**Max Concurrent Sign-Ins**

The maximum number of people who can be signed into the space at the same time. If someone tries to sign in when this limit is reached, they will be notified that the space is at capacity. Set to 0 for no limit.

**Backup Retention (days)**

How many days to keep automatic database backups before deleting them. Set to 0 to keep all backups forever (not recommended unless you have ample disk space).

Click **Save Operations Settings** after making changes.

---

### 6.3 Branding and Appearance

These settings control how Nucleus looks and what it calls itself.

**Hackerspace Name**

Your organization's full name. This appears in the title bar, on reports, and in email headers. For example: "City Hackerspace" or "Downtown Makerspace Collective".

**Tag Name**

A short label used in buttons and prompts throughout the app. For example, if your tag name is "Makerspace", the sign-in button will say "Sign In to Makerspace". Keep this short — one or two words.

**App Name**

The name shown in the application title bar at the very top of the screen.

**ASCII Logo**

A text-art logo displayed on the login screen. You can edit or replace the multi-line text in the text box. ASCII art generators are available online if you want to create a custom logo for your space.

**Currency Name**

What your space calls its internal credit system. This label appears throughout the Purchases tab and member profiles wherever a credit balance is shown. Common choices: "Credits", "Hackerbucks", "Tokens", "Bucks".

**App Theme**

Choose a colour theme for the entire application. Selecting a theme previews it immediately so you can compare before saving. The theme is saved permanently when you click **Save Branding Settings**.

Available themes:

| Theme | Style |
|-------|-------|
| Nord | Cool blues and greys (default) |
| Textual Dark | Default dark theme |
| Textual Light | Default light theme |
| Gruvbox | Warm earth tones, dark |
| Dracula | Purple and pink on dark background |
| Tokyo Night | Dark blue, city at night feel |
| Monokai | Classic editor dark theme |
| Flexoki | Ink-inspired warm tones |
| Catppuccin Mocha | Dark pastel (Catppuccin family) |
| Catppuccin Latte | Light pastel (Catppuccin family) |
| Catppuccin Frappe | Medium pastel (Catppuccin family) |
| Catppuccin Macchiato | Dark pastel, slightly warmer |
| Solarized Dark | Classic dark solarized |
| Solarized Light | Classic light solarized |
| Rose Pine | Muted rose tones, dark |
| Rose Pine Moon | Cooler rose tones, dark |
| Rose Pine Dawn | Light rose tones |
| Atom One Dark | Dark theme inspired by Atom editor |
| Atom One Light | Light theme inspired by Atom editor |
| Textual ANSI | Uses your terminal's native colours |

**Default Export Format**

Choose whether reports are exported as **CSV** (spreadsheet) or **PDF** by default. This pre-selects the format in report export dialogs.

**PDF Report Header Text**

A subtitle line printed below the title on all PDF exports. Use this to add your organization name or tagline. For example: "City Hackerspace - Annual Reports".

**Staff Reply-To Email Address**

An email address printed on exported reports so that anyone receiving a report knows who to contact with questions.

Click **Save Branding Settings** after making changes.

---

### 6.4 Security

**Minimum Password Length**

The shortest password Nucleus will accept when a member registers or changes their password. The default is 8 characters. Increasing this to 12 or more is recommended for better security.

**Max Login Attempts Before Lockout**

How many times a user can enter the wrong password before their account is locked for 30 minutes. Set to 0 to allow unlimited attempts with no lockout.

**SQL Console Enabled**

Turns the raw SQL console (Database tab) on or off for all admins. Disabling this prevents accidental or unauthorized database changes. The change takes effect the next time an admin logs in.

Click **Save Security Settings** after making changes.

---

### 6.5 Point of Sale (Square Terminal)

This section connects Nucleus to a Square Terminal device for processing card payments. If your space only takes cash or handles payments outside of Nucleus, you can leave this disabled.

#### What You Need Before Starting

1. A **Square account** — sign up at [squareup.com](https://squareup.com) (free to create).
2. A **Square Terminal** — the physical card reader hardware sold by Square.
3. **Square Developer credentials** — from [developer.squareup.com](https://developer.squareup.com):
   - An **Access Token** (one for sandbox/testing, one for production/live)
   - A **Location ID**
   - A **Device ID**

#### How to Find Your Square Credentials

**Access Token**

1. Go to [developer.squareup.com](https://developer.squareup.com) and sign in with your Square account.
2. Click on your application (or create a new one by clicking **New Application** and giving it a name like "Nucleus").
3. Under the **Credentials** tab, you will see:
   - **Sandbox Access Token** — use this for testing. It does not process real payments.
   - **Production Access Token** — use this for live, real payments.
4. Copy the relevant token. Treat these like passwords — do not share them or store them in plain text.

**Location ID**

1. In the Square Developer dashboard, click on your application.
2. Open the **Locations** tab.
3. Copy the Location ID for the location where your terminal is physically set up.

**Device ID**

1. Go to your regular Square Dashboard (not the developer site) at [squareup.com/dashboard](https://squareup.com/dashboard).
2. Navigate to **Devices** (or **Point of Sale > Devices** depending on your account type).
3. Find your Terminal in the list and copy its Device ID.

#### Configuration Steps in Nucleus

1. Check the **Enable Square Terminal** box.
2. Select the **Square Environment**: choose **Sandbox (Testing)** while setting up, and switch to **Production (Live)** when you are ready to take real payments.
3. Paste your **Sandbox Access Token** into the sandbox field and click **Save Sandbox Token**. The token is stored securely and will not be shown again — the placeholder will change to confirm it is saved.
4. Paste your **Production Access Token** and click **Save Production Token** when you are ready to go live.
5. Enter your **Square Location ID**.
6. Enter your **Square Device ID**.
7. Select your **Currency** from the dropdown.
8. Click **Save POS Settings**.

#### Pairing Your Terminal

The first time you use the Square Terminal with Nucleus, it needs to be paired. You only need to do this once (unless you factory-reset the terminal).

1. In Nucleus, go to **Settings > Point of Sale** and click **Pair Terminal**. A pairing code will appear on screen.
2. On the physical Square Terminal:
   - Tap the three-dot menu icon (top right of the screen).
   - Go to **Settings**, then **Device**.
   - Tap **Pair for Terminal API**.
   - Enter the pairing code shown in Nucleus.
3. Back in Nucleus, click **Check Pairing Status** to confirm the pairing was successful.

Once paired, Nucleus can send checkout requests directly to the terminal.

---

### 6.6 Subscriptions (Square Recurring Billing)

This feature allows members to pay their membership automatically each month through Square. Square handles billing and stores payment information — Nucleus never sees or stores card numbers.

#### Before You Start

Square integration must be configured and working first (see Section 6.5).

You also need a **Subscription Plan** created in the Square Dashboard:
1. Log in to [squareup.com/dashboard](https://squareup.com/dashboard).
2. Go to **Subscriptions** (you may need to navigate to **Payments > Subscriptions** or search for it).
3. Click **Create a Plan**.
4. Set your plan's name, price, and billing cycle (e.g., monthly).
5. After saving, open the plan and find the **Plan Variation ID** — it looks like a long string of uppercase letters and numbers (e.g., `D3KPJGMOWQQFJJGZIHHDBFDA`).

#### Configuration Steps in Nucleus

1. Paste the **Plan Variation ID** into the field.
2. Set the **Billing Timezone** to your local timezone. Use the standard timezone format, for example:
   - `America/Toronto` for Eastern Time (Canada)
   - `America/New_York` for Eastern Time (US)
   - `America/Vancouver` for Pacific Time
   - `Europe/London` for UK time
   - `Australia/Sydney` for Australian Eastern Time
   A full list of timezone names can be found by searching for "IANA timezone list" online.
3. Click **Save Subscription Settings**.

#### Enrolling a Member in Recurring Billing

1. Go to the **Purchases** tab.
2. In the **Membership Transactions** section, search for the member by name or email.
3. Click their row in the search results to select them.
4. Click **Activate Square Subscription**.
5. Review the member's details in the popup and confirm.
6. Square will email the member a secure link to enter their payment information. The member completes this step themselves — their card details go directly to Square.

#### Managing Subscriptions

- **Poll All Subscriptions Now** — checks the current status of all enrolled subscriptions at once. Useful to run manually if you suspect a member's subscription status has changed.
- **Poll Subscription Status** — checks a single member's subscription. Select the member first, then click this button.
- **Cancel Subscription** — stops recurring billing for a selected member. This does not delete their membership record in Nucleus.

---

### 6.7 Product Categories

Product categories are reusable templates that speed up the process of adding memberships or day passes. Instead of entering a price and duration every time, staff can select a template and the fields are filled in automatically.

#### Membership Tiers

Create one template per membership plan you offer. For example:

| Name | Price ($) | Duration (days) | Credits Bonus | Description |
|------|-----------|-----------------|---------------|-------------|
| Monthly Standard | 50.00 | 30 | 0.00 | Standard monthly access |
| Annual Premium | 500.00 | 365 | 50.00 | Annual membership with $50 credit bonus |

- **Name** — appears in the dropdown when staff add a membership.
- **Price ($)** — the cost of this membership.
- **Duration (days)** — how long the membership is valid from the activation date.
- **Consumables Credits** — an amount of credits automatically added to the member's balance when this tier is activated. Set to 0 for no bonus.
- **Description** — optional notes visible to staff.

To add a tier: fill in the fields and click **Add Membership Tier**.
To delete a tier: click its row in the table to select it, then click **Delete Selected**. You cannot delete a tier if it has been used on a current active membership.

#### Day Pass Tiers

Same concept as membership tiers but for single-day passes. Create templates with a name, price, and optional description. Click **Add Day Pass Tier** to save.

---

### 6.8 Storage Units

Storage units represent physical spaces at your location — bins, lockers, shelves, drawers — that members can rent or borrow to store materials.

- **Unit Number** — a label like "A-01", "B-12", "Locker 5". Auto-incremented by default, but you can type any identifier.
- **Description** — a short label like "Shelf Bin", "Large Locker", "Wall Cabinet".

Click **Create Storage Unit** to add one. Units that are currently assigned to a member cannot be deleted. Archive the assignment first (Storage tab), then delete the unit.

---

### 6.9 Inventory

Inventory items are the products and services that staff can add to a sale in the Purchases tab. Examples: 3D printing filament by weight, laser cutting time, snacks, workshop fees, tool rental.

- **Name** — what appears in the item list (e.g., "PLA Filament - 100g").
- **Description** — optional detail for staff reference.
- **Price ($)** — the unit price. Staff can override this when adding a custom item.

Click **Add Item** to create one. To remove an item, click its row to select it and click **Delete Selected**.

---

### 6.10 Email and Notifications (Resend)

Nucleus uses [Resend](https://resend.com) to send emails. Resend is a third-party email delivery service with a free tier that is sufficient for most makerspaces (100 emails per day, 3,000 per month at no cost).

Email is used for four things in Nucleus:
1. **Daily activity summary** emails sent to admins and staff each morning.
2. **Monthly transaction report** emails sent automatically on the 1st of each month.
3. **Transaction receipt** emails sent to customers after a point-of-sale payment.
4. **Database backup** files sent as email attachments.

#### Setting Up a Resend Account

1. Go to [resend.com](https://resend.com) and create a free account.

2. After signing in, click **API Keys** in the sidebar, then click **Create API Key**.
   - Give it a name (e.g., "Nucleus").
   - Select **Full Access** or **Sending Access**.
   - Click **Add** and copy the key immediately — it will only be shown once.

3. **Optional but recommended for production use — set up a sending domain:**
   
   Without a domain, you can only send from `onboarding@resend.dev`, which is a test address. Emails from this address may land in spam. To send from your own address (e.g., `reports@yourhackerspace.org`), you need to verify your domain.
   
   To verify your domain:
   1. In Resend, click **Domains** in the sidebar, then **Add Domain**.
   2. Enter your domain name (e.g., `yourhackerspace.org`).
   3. Resend will show you a list of DNS records to add. You need to add these to your domain's DNS settings through whoever manages your domain (common providers: Cloudflare, Namecheap, GoDaddy, Squarespace Domains):
      - **SPF record** (type TXT) — tells email servers that Resend is allowed to send on your behalf.
      - **DKIM records** (type TXT or CNAME) — proves that emails are authentic and haven't been tampered with.
      - **DMARC record** (type TXT) — tells receiving email servers what to do if authentication fails.
   4. Add these records, then click **Verify** in Resend. DNS changes can take a few minutes to 48 hours to propagate globally.
   5. Once the domain shows a green "Verified" badge in Resend, you can send from any address at that domain.

#### Configuring Email in Nucleus

Go to **Settings > Email and Notifications**:

- **Resend API Key** — paste the key you copied and click **Save Key**. The key is stored securely and will not be shown again. The field will change to show "Key configured" when saved.
- **From Email Address** — the address all Nucleus emails will appear to come from. Must be at a verified domain (e.g., `reports@yourhackerspace.org`). If you have not set up a domain, use `onboarding@resend.dev` for testing.
- **Send Daily Report To** — one or more recipient addresses that should receive the daily summary email. Separate multiple addresses with commas. For example: `admin@yourspace.org, board@yourspace.org`
- **Daily Report Send Time** — the time each day to send the report, in 24-hour format. For example: `07:00` for 7 AM, `18:30` for 6:30 PM.
- **Enable Daily Email Reports** — check this box to activate daily emails. If unchecked, no daily emails are sent.
- **Enable Monthly Transaction Report** — check this box to have Nucleus automatically email a full transaction report on the 1st of every month. The report covers all transactions from the previous calendar month (for example, the report sent on February 1st covers all of January). It is sent to the same recipients as the daily report.
- **Email receipts to customers** — check this box to automatically email a receipt to a customer after a point-of-sale transaction. Receipts are only sent when the customer's email address is provided during the sale.

Click **Save Email Settings**, then click **Send Test Email** to confirm everything works. A daily report email should arrive at the configured address within a few seconds.

#### What the Daily Report Contains

- A 7-day activity summary table showing: active members, new registrations, expiring memberships, sign-ins, volunteers, day passes, transactions, and community contacts.
- A list of recent community contact visits.
- A list of recent point-of-sale transactions.

#### What the Monthly Transaction Report Contains

- All card (Square Terminal) transactions for the previous calendar month, with a section total.
- All cash and locally recorded transactions for the previous calendar month, with a section total.

The monthly report is sent on the 1st of each month. If Nucleus is not running when the 1st arrives, that month's report will not be sent — there is no catch-up. For reliable delivery, keep Nucleus running on a dedicated machine at your space.

---

### 6.11 Backup

Nucleus can automatically save a backup copy of its database every day.

- **Enable automatic backups** — check this box to turn on the backup scheduler.
- **Backup Time** — what time each day to create the backup, in 24-hour format (e.g., `02:00` for 2 AM — a quiet time when the space is likely not in use).
- **Backup Retention (days)** — how many days to keep old backup files before deleting them. Set to 0 to keep all backups indefinitely.
- **Email Backup To** — optionally enter one or more email addresses (comma-separated) to receive the backup file as an email attachment each day. This requires Resend to be configured (see Section 6.10).

Click **Save Backup Settings** to apply.

#### Where Backups Are Stored

Backup files are saved in the `backups/` folder inside the Nucleus project directory, named `db_backup_MMDDYY.db` (where MM=month, DD=day, YY=year). Only one backup is created per calendar day.

#### Manual Backup

You can make a manual backup at any time by copying the `hackspace.db` file from the Nucleus project folder. Do this while Nucleus is not running to ensure the file is in a consistent state.

---

## 7. My Profile Tab

This tab is available to all logged-in users.

### Account Information

At the top of the tab, you will see:
- Your role and name (e.g., "Welcome, Member Jason!")
- Your account type and account number
- Your current credit balance (the internal currency your space uses)

### Buttons

- **Edit My Information** — opens a form where you can update your personal details: name, phone number, address, emergency contact, health information, and allergies. Your emergency contact and health information is accessible to admins through the Database tab for safety purposes.
- **Change Password** — opens a form to set a new password. You will need to enter your current password to confirm the change.
- **Sign In / Sign Out** — records your physical arrival at or departure from the space. The button label changes based on whether you are currently signed in. If you have a preferred visit type set (see below), you are signed in with that type automatically. Otherwise, a prompt will ask what kind of visit this is (workshop, makerspace, volunteer, etc.).
- **Logout** — ends your current session and returns to the login screen.

### My Preferences

**Preferred Visit Type**

If you always visit for the same reason (e.g., you are always at a workshop), you can set that here so you are not prompted every time you sign in. Select your preference from the dropdown, then click **Save Preferences**.

Leave it set to "No preference (always ask)" if your visit type varies and you want to be prompted each time.

---

## 8. Staff Tools Tab

Available to Staff and Admin users only.

### Register New Member (In-Person)

Click this button to open the full registration form for use when a new member is physically present. This differs from self-registration in two ways:
- The account is activated immediately — no approval step is required.
- Staff confirm that they checked the member's ID and explained the Terms of Service and Code of Conduct.

### Quick User Search / Manage

Use this section to find and manage any registered user.

1. Type the member's name or email address into the search box and click **Search**.
2. Click any row in the results table to open the **Member Action Menu** for that person.

The Member Action Menu offers these options:

1. **Edit User Profile / Role** — change any field on the user's account, including their role (Admin, Staff, Member, or Community), their active/inactive status, and all personal details.
2. **Add Membership** — activate a new membership period for this member. You can select from your pre-defined membership tiers (see Section 6.7) or enter a custom price and duration.
3. **Edit Membership** — view existing memberships and modify them (extend the end date, change the description, or deactivate a membership early).
4. **Transaction (Credit/Debit)** — manually add or remove credits from the member's balance. Use this for adjustments, refunds, or bonus credits.
5. **Add Day Pass** — issue a single-day pass. You can select from your day pass tiers or enter a custom price.
6. **View Day Pass History** — see a complete list of all day passes ever issued to this member.
7. **Edit Sign Ins** — view and edit the member's space attendance records (sign-in and sign-out times and visit types).
8. **Activate Square Subscription** — enroll the member in recurring monthly billing through Square (requires Square subscription to be configured, see Section 6.6).

### Pending Approvals

This table shows accounts that were created through self-registration and are waiting for approval before the member can log in.

1. Click a row in the table to select the account.
2. Click **Approve Selected Account** to activate it. The member will now be able to log in.

Click **Refresh List** to reload the pending accounts list.

---

## 9. Purchases Tab

### For Staff and Admin

This tab is where you process sales. It is divided into two sections.

#### Manual Transaction (Point of Sale)

Use this section to ring up a sale. Follow the steps below:

**Step 1 — Select Items from Inventory (Optional)**

Click **Step 1: Select Items (Optional)** to expand this section.

- The table shows all inventory items you have configured (see Section 6.9).
- Click an item row to select it (it will be highlighted).
- Set the quantity in the **Quantity** field.
- Click **Add to Cart** to add it.

You can add multiple items from inventory. Repeat for each one.

**Step 2 — Add a Custom Item (Optional)**

Click **Step 2: Add Custom Item (Optional)** to expand this section.

Use this for one-off charges that are not in your inventory list — for example, a special workshop fee, a donation, or a custom service.

- Enter a description in the **Item Name / Description** field (e.g., "Custom laser job - 30 min").
- Enter the price in the **Price ($)** field.
- Click **Add Custom Item**.

**Step 3 — Enter Customer Details**

Click **Step 3: Customer Details** to expand this section.

You can search for an existing member to auto-fill their details:
- Type their name or email in the search box and click **Search**.
- Click their row in the search results to fill in their name, email, and phone automatically.

Or type the details manually:
- **Customer Name** (required for all transactions).
- **Customer Email** (required if you want to send an email receipt for cash transactions).
- **Customer Phone** (optional).

**The Cart**

Between the steps and the action buttons, you will see the cart — a table listing all items added so far, with quantities, unit prices, and subtotals. The total is shown below the cart.

- **Remove Selected** — click a cart row to select it, then click this to remove just that item.
- **Clear Cart** — removes all items from the cart at once.

**Processing the Transaction**

Once you have added items and entered customer details, you can process the sale:

- **Send to Square Terminal** (shown when Square is enabled) — sends the total to your physical Square Terminal device. The customer taps or inserts their card directly on the terminal to pay. The terminal handles the payment and Nucleus records the result automatically.
- **Record Transaction** (shown when Square is disabled) or **Record Cash Transaction** — records the sale locally in Nucleus as a cash or manual payment. If Square is enabled and a Location ID is configured, cash sales are also recorded in your Square Dashboard so your bookkeeper has one system to reconcile.
- **Clear Form** — resets all fields and the cart without recording anything.

**After the Transaction**

- If the customer provided an email address and email receipts are enabled (see Section 6.10), a receipt is sent automatically.
- The transaction is saved and will appear in the Transactions tab.

#### Membership Transactions

Below the POS section, the **Membership Transactions** collapsible lets you search for a registered member to manage their account without processing a sale.

Search by name or email, then click a result row to select the member. The following action buttons become active:

- **Add Membership / Edit Memberships** — manage membership periods for this member.
- **Add Day Pass / View Day Passes** — issue a day pass or view their history.
- **Add Credits / Deduct Credits** — adjust the member's credit balance.
- **View Credits** — see the full ledger of all credit and debit transactions.
- **Activate Square Subscription / Cancel / Poll Status** — manage recurring billing (only shown when Square is configured and enabled).

### For Members and Community Users

Members see a read-only view of their own data in three sections:

- **My Memberships** — a table showing all their membership periods with start dates, end dates, and descriptions.
- **My Day Passes** — a table of all day passes issued to them.
- **My Credits Ledger** — a table of all credit and debit entries and their running balance.

---

## 10. Transactions Tab

Available to Staff and Admin users only.

The Transactions tab provides a complete, always-visible history of all financial activity recorded in Nucleus. Unlike the Purchases tab (which is focused on processing new sales), this tab is for reviewing and managing existing transactions.

### What the Table Shows

The table displays all transaction records sorted by date, newest first, with the following columns:

- **ID** — the transaction record number.
- **Date** — when the transaction was recorded.
- **Customer** — the customer name at the time of the transaction.
- **Amount** — the transaction total.
- **Type** — what kind of transaction this was (e.g., Manual, Day Pass, Membership, Credit).
- **Description** — the items or service description.
- **Status** — the current status (Completed, Pending, Cancelled, Cash, Local, etc.).
- **Via** — how it was processed (Square Terminal, Cash, Local, Free, etc.).
- **Processed By** — which staff member recorded the transaction.

### Actions

- **Refresh** — reloads the table and checks Square for any updates to pending transactions (e.g., a terminal checkout that completed or timed out since the last load).
- **Check Terminal Status** — select a transaction row with a Pending status, then click this to query Square for its latest status. Useful if a customer is waiting and you want to confirm their payment went through.
- **Issue Refund** — select a completed Square Terminal transaction row, then click this to initiate a refund. A confirmation dialog will show the refund amount and ask you to confirm.
- **Edit Details** — select any transaction row and click this to correct the customer name, email, description, or other text fields on the record.
- **Edit Allocation** — select a transaction row to reassign which registered member account the transaction is linked to. Useful if a sale was processed for the wrong account.

---

## 11. Reports Tab

Available to Staff and Admin users only.

### Membership Report

A filterable table of all registered users in the system.

**Filtering:**

Use the checkboxes to control which roles are included:
- **Admin** — show admin accounts
- **Staff** — show staff accounts
- **Member (Active)** — show active paying members
- **Community (Inactive)** — show expired or inactive members
- **Signed In** — show only users currently signed into the space

After changing filters, click **Refresh Report** to update the table. Click any row to open the Member Action Menu for that person (same as the Staff Tools search).

**Export Options:**

- **Export CSV** — saves the filtered member list as a CSV file (opens a folder picker to choose where to save it).
- **Export PDF** — saves a formatted PDF report.

### Admin and Statistics Reports

These reports cover activity across a date range that you choose. Each opens a dialog where you enter a start date and end date (both pre-filled to the last 30 days), then select a save folder and file format.

**Export Period Transaction Report**

A financial report covering all transactions in the selected date range, split into two sections:
1. **Card Transactions** — Square Terminal payments with status "Completed".
2. **Cash Transactions** — all cash, manual, and locally recorded payments.

Each section includes a total at the bottom. Available as CSV or PDF.

**Export Period User Activity Report**

A comprehensive activity summary covering everything that happened in your space during the selected date range. Includes six sections:
1. Memberships activated or active during the period.
2. Day passes issued during the period.
3. Consumable (credit) transactions.
4. Space sign-ins and sign-outs.
5. Community contact visits (walk-in visitors).
6. Product sales from inventory.

Available as CSV or PDF.

**Export Community Contacts Report**

All walk-in visitor records (from the Community Contacts form) within the selected date range. Useful for reporting community outreach numbers to funders or boards. Available as CSV or PDF.

**Export Everything People CSV Report**

A complete export of all member data in the system — personal information, roles, memberships, credits, and more. Exports as CSV only. Useful for data migration or external analysis.

> **Privacy note:** This export contains personal information. Handle the file securely and do not share it publicly.

**Export Products / Services Sales Report**

A sales breakdown covering all product and service revenue in the selected date range, split into four sections:
1. **Transactions** — completed Square and cash transactions.
2. **Product Sales** — individual inventory items sold.
3. **Day Passes** — day passes issued (paid and free).
4. **Memberships** — memberships activated (paid and free/manual).

Available as CSV or PDF.

---

## 12. Storage Tab

Available to Staff and Admin users only. Used to track physical storage spaces assigned to members — bins, lockers, shelves, and similar.

### Active Storage Assignments

The top table shows all current assignments. Each row shows:
- The unit number and what it contains.
- Who it is assigned to.
- Notes, charge type, total charged, and the date assigned.

**Actions:**

- **Assign Storage** — opens a form to create a new assignment. Select the unit from the dropdown (only available units appear), enter the member's name or account number, describe what is being stored, and optionally enter charge details.
- **View Selected** — click a row to select it, then click this to open a read-only detail view.
- **Edit Selected** — opens an editable form for the selected assignment. Use this to update notes, charges, or other details.
- **Remove Selected (Archive)** — marks the assignment as completed and moves it to the archived table below. The unit becomes available for new assignments. This action cannot be undone through the UI.
- **Refresh** — reloads both tables.

### Archived Storage Assignments

The lower table shows historical assignments that have been ended. This is a read-only record for reference.

---

## 13. Database Tab

Available to Admin users only.

This tab provides direct access to the underlying database using SQL (Structured Query Language). It is intended for advanced queries — looking up data that is not available through the normal interface, generating custom reports, or investigating data issues.

> **Caution:** This is a powerful tool. Queries that modify data (UPDATE, DELETE, DROP) make permanent changes with no undo. Always be confident in what a query does before running it.

### Unlocking the Console

When you first open the Database tab, you will be asked to enter your admin password. This extra step is an intentional safety barrier. Enter your password and click **Unlock** to proceed.

The SQL console can be disabled entirely from Settings > Security if you do not want it available.

### Pre-Set Queries

Five common queries are available as buttons. Click a button to load the query into the input field, review it, then click **Execute SQL** to run it:

1. **Users with medical / allergy information** — lists members who have entered health or allergy details. Useful for space safety awareness.
2. **Emergency contact list** — lists all members with their emergency contact names and phone numbers.
3. **Members missing safety orientation** — lists members who have not completed safety orientation.
4. **User count by role** — shows how many accounts exist in each role category.
5. **Attendance report for a date range** — shows sign-in and sign-out records. Note: the dates in this query are example values — edit them in the input field before running.

### Custom Queries

Type any SQL query into the input field and click **Execute SQL**. Results appear in the table below.

Examples of safe read-only queries:
```sql
SELECT * FROM user WHERE role = 'member' LIMIT 50;
SELECT email, first_name, last_name FROM user ORDER BY last_name;
```

### Export Options

After running a query, you can export the results:
- **Export Results as CSV** — saves the results table as a CSV file.
- **Export Results as PDF** — saves the results as a formatted PDF.

---

## 14. Feedback Tab

Available to all logged-in users.

### Submitting Feedback

1. Check at least one category that applies:
   - **General Feedback** — comments, compliments, or concerns about the space or this system.
   - **Feature Request** — something you would like added to Nucleus.
   - **Bug Report** — something that is not working correctly.
2. Check **URGENT** if the issue needs immediate attention.
3. Type your message in the text area.
4. Click **Submit Feedback**.

Your feedback is saved and visible to all staff and admin users.

### Viewing and Responding to Feedback (Staff and Admin Only)

Staff and admin see a table below the submission form showing all submitted feedback. Click any row to open the full comment and add an admin response.

Feedback can be exported as **CSV** or **PDF** using the buttons above the table.

---

## 15. Walk-In Visitors and Community Contacts

The **Community Contacts** button on the login screen opens a visitor form that does not require a Nucleus account. Any visitor to your space — whether or not they are a member — can fill it in, or staff can fill it in on their behalf.

### What the Form Collects

**Required fields:**
- First name
- Email address

**Optional fields:**
- Last name
- Phone number
- Postal or ZIP code

**Optional demographics (for reporting and outreach):**
- Pronouns
- Age range
- How they heard about your space
- What brought them in today (community tour, visiting a project, etc.)

**Opt-in checkboxes:**
- Would like to receive updates and news from the space
- Interested in volunteering
- Interested in teaching or mentoring

After submitting, the visitor is thanked and the form resets.

### Unknown Walk-In (Staff Shortcut)

If a visitor declines to provide their information, staff can check the **Unknown Walk-In** box at the top of the form. This mode only requires a staff name and a brief description of the visit (for accountability purposes). The visit is recorded anonymously with no personal details.

### Where Community Contact Records Appear

- In the **daily email report** sent to admins and staff (if configured).
- In the **Community Contacts Report** on the Reports tab (exportable as CSV or PDF).
- In the **Period User Activity Report** (Reports tab), under the Community Contacts section.

---

## 16. Public Purchase Screen (Kiosk Mode)

The **Manual Purchase** button on the login screen opens a simplified point-of-sale screen that works without anyone being logged in. This is intended for use when a computer or tablet is set up as a self-serve checkout station.

The screen works identically to the staff Purchases tab — inventory cart, custom items, customer details, Square Terminal or cash — with one difference: the recent transactions table does not display customer names or email addresses. This protects the privacy of previous customers on a shared public screen.

This screen is useful for:
- A kiosk where members can pay for consumables on their own.
- A front desk tablet where staff can quickly process a sale without logging into the full dashboard.

---

## 17. Automatic Background Tasks

Nucleus runs three scheduled tasks automatically while the application is open.

### Membership Expiry Check

- **When it runs:** Once when Nucleus starts, then again daily at 00:01 (just after midnight).
- **What it does:** Checks all accounts with the Member role. If a membership has expired and the grace period (see Section 6.2) has passed, the account is automatically downgraded to the Community role.

### Daily Email Report

- **When it runs:** At the time configured in Settings > Email and Notifications (default: 07:00).
- **What it does:** Sends the daily activity summary email to all configured recipients.
- **Requires:** A saved Resend API key, at least one recipient email address, and "Enable Daily Email Reports" checked.

### Monthly Transaction Report

- **When it runs:** Once on the 1st day of each month, at the first opportunity after midnight.
- **What it does:** Sends a full transaction report for the previous calendar month to all configured recipients. The report is split into card transactions and cash transactions, each with a total. A duplicate-send guard ensures the report is only sent once per month even if Nucleus restarts on the 1st.
- **Requires:** A saved Resend API key, at least one recipient email address, and "Enable Monthly Transaction Report" checked.
- **Important:** If Nucleus is not running when the 1st of the month arrives, that month's report is skipped entirely — it will not be sent retroactively on the next launch.

### Database Backup

- **When it runs:** At the time configured in Settings > Backup (default: 02:00).
- **What it does:** Copies the database to the `backups/` folder. Optionally emails the file to configured recipients. Deletes backup files older than the configured retention period.
- **Requires:** "Enable automatic backups" checked.

> **Important:** All three tasks only run while Nucleus is open. If the application is not running when a scheduled time passes, that task will run once the next time Nucleus is launched (no more than once per calendar day). For reliable daily reports and backups, Nucleus should be kept running on a dedicated computer at your space.

---

## 18. Updating Nucleus

When a new version of Nucleus is available:

**Step 1 — Download the updated code**

If you used git to get Nucleus:
```
git pull
```

Or download the new version and replace the project folder.

**Step 2 — Activate your virtual environment**

On Linux or macOS:
```
source venv/bin/activate
```

On Windows:
```
venv\Scripts\activate
```

**Step 3 — Install any new dependencies**

```
pip install -r requirements.txt
```

**Step 4 — Run the update script**

```
python scripts/update.py
```

This script does two things automatically:
1. Creates a backup of your current database before making any changes.
2. Applies any database migrations needed for the new version (adds new columns or tables while preserving all existing data).

You will see a confirmation message when it completes.

**Step 5 — Start Nucleus**

```
python nucleus.py
```

---

## 19. Troubleshooting

### "Database file not found" or similar error when running scripts

Make sure you are running scripts from the main project folder, not from inside the `scripts/` subfolder:

```
# Correct:
python scripts/create_admin.py

# May not work:
cd scripts
python create_admin.py
```

### Nucleus starts but shows a blank or broken screen

Make sure you are using a supported terminal that handles colour and Unicode. On Windows, use **Windows Terminal** (available free from the Microsoft Store) rather than the older Command Prompt or PowerShell window.

### Emails are not being sent

1. Go to **Settings > Email and Notifications** and verify the Resend API key is saved — the field should show "Key configured", not blank.
2. Confirm that "Enable Daily Email Reports" is checked.
3. Confirm that at least one address is entered in the "Send Daily Report To" field.
4. Click **Send Test Email** to trigger an immediate test.
5. If using a custom domain, open your Resend dashboard and verify the domain shows a green "Verified" badge. If not, double-check the DNS records you added.
6. If emails arrive but land in spam, verify that SPF, DKIM, and DMARC records are set up for your domain (Resend shows you exactly what records to add when you verify a domain).

### Square Terminal is not receiving checkout requests

1. In Settings > Point of Sale, confirm "Enable Square Terminal" is checked.
2. Confirm the correct environment is selected — **Sandbox** for testing, **Production** for real payments.
3. Confirm the access token, location ID, and device ID are all entered and saved.
4. Make sure the terminal is powered on, not in sleep mode, and connected to the internet.
5. Try re-pairing the terminal (see Section 6.5 — Pairing Your Terminal).

### A member cannot log in after registering

Self-registered accounts must be approved by a staff or admin user. Go to **Staff Tools** and check the **Pending Approvals** table. The account will appear there.

### Session times out too quickly

Increase the auto-logout timeout in **Settings > General**. The default is 10 minutes. Changing it to 30 or 60 minutes is common for spaces where staff are busy and step away from the screen.

### Cannot see the Settings or Database tabs

These tabs are only visible to users with the **Admin** role. If you need admin access, ask an existing admin to change your role through the Member Action Menu (Staff Tools > search for your name > Edit User Profile / Role), or run the promote script from the terminal:

```
python scripts/promote_superuser.py
```

### App looks wrong after changing themes

If the theme change did not fully apply, try clicking a different tab and back again, or logging out and back in. The theme is saved to the database and should apply immediately on next startup.

### Data seems out of date or a table is not updating

Most tables in Nucleus do not refresh automatically. Click the relevant **Refresh** button on the tab you are viewing. If a member's role or balance does not look right after a change, click Refresh or navigate away and back to reload the data.
