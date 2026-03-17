"""
Email delivery module for Nucleus using the Resend API.

This module is responsible for building and sending outbound email reports and
transaction receipts. It relies on services.py for all data access and never
imports from screens/ or any Textual UI code. Configuration (API key, addresses)
is read from the AppSetting table at send time so that admin changes take effect
without restarting the application.
"""

import base64

import resend

from core.services import (
    build_daily_report_data,
    get_sensitive_setting_value,
    get_setting,
)

_TABLE_STYLE = (
    "border-collapse: collapse; width: 100%; font-size: 0.85em; margin-bottom: 1.5em;"
)
_TH_STYLE = (
    "background: #2d2d2d; color: #fff; padding: 6px 10px; "
    "text-align: left; border: 1px solid #555; white-space: nowrap;"
)
_TD_STYLE = "padding: 5px 10px; border: 1px solid #ccc; text-align: center;"
_TD_LABEL_STYLE = (
    "padding: 5px 10px; border: 1px solid #ccc; text-align: left; font-weight: bold;"
)
_TD_ALT_STYLE = (
    "padding: 5px 10px; border: 1px solid #ccc; "
    "background: #f4f4f4; text-align: center;"
)
_TD_ALT_LABEL_STYLE = (
    "padding: 5px 10px; border: 1px solid #ccc; "
    "background: #f4f4f4; text-align: left; font-weight: bold;"
)


def send_transaction_receipt(
    txn_id: int,
    amount: float,
    customer_name: str,
    customer_email: str,
    description: str,
    payment_method: str,
    transaction_ref: str,
    transaction_date: str,
    subject_override: str = "",
) -> bool:
    """
    Emails a transaction receipt to the customer via Resend.

    Returns True on successful delivery. Returns False when receipts are
    disabled in settings, the Resend API key is not configured, or no
    recipient email is available. Raises on unexpected API errors so the
    caller can surface them as notifications.

    Parameters:
        txn_id           -- Local Nucleus transaction ID, shown as Receipt number.
        amount           -- Transaction amount in dollars.
        customer_name    -- Display name on the receipt.
        customer_email   -- Recipient address; function returns False if empty.
        description      -- Item or service description; shown as N/A if empty.
        payment_method   -- Human-readable method, e.g. "Cash" or "Card (Square Terminal)".
        transaction_ref  -- Square checkout or payment ID; shown as N/A if empty.
        transaction_date -- Pre-formatted date string, e.g. "2026-03-12 14:30".
        subject_override -- Optional subject line override; defaults to "Receipt #{txn_id}".
    """
    if get_setting("email_receipts_enabled", "false").lower() != "true":
        return False

    if not customer_email:
        print("[Email] Receipt not sent: no customer email address")
        return False

    api_key = get_sensitive_setting_value("resend_api_key")
    if not api_key:
        print("[Email] Receipt not sent: Resend API key not configured")
        return False

    hackspace_name = get_setting("hackspace_name", "Nucleus")
    from_email = get_setting("report_from_email", "onboarding@resend.dev")

    subject = (
        subject_override
        if subject_override
        else f"{hackspace_name} - Receipt #{txn_id}"
    )

    resend.api_key = api_key
    html_body = _build_receipt_html(
        hackspace_name=hackspace_name,
        txn_id=txn_id,
        amount=amount,
        customer_name=customer_name,
        description=description or "N/A",
        payment_method=payment_method,
        transaction_ref=transaction_ref or "N/A",
        transaction_date=transaction_date,
    )

    params = {
        "from": from_email,
        "to": [customer_email],
        "subject": subject,
        "html": html_body,
    }

    resend.Emails.send(params)
    print(f"[Email] Receipt #{txn_id} sent to {customer_email}")
    return True


def _build_receipt_html(
    hackspace_name: str,
    txn_id: int,
    amount: float,
    customer_name: str,
    description: str,
    payment_method: str,
    transaction_ref: str,
    transaction_date: str,
) -> str:
    """Renders a clean two-column receipt table as an HTML email body."""
    divider = "<div style='border-top: 1px solid #ddd; margin: 20px 0;'></div>"

    rows_data = [
        ("Receipt Number", f"#{txn_id}"),
        ("Date", transaction_date),
        ("Amount", f"${amount:.2f}"),
        ("Payment Method", payment_method),
        ("Description", description),
        ("Transaction Reference", transaction_ref),
    ]

    rows_html = ""
    for i, (label, value) in enumerate(rows_data):
        label_style = _TD_ALT_LABEL_STYLE if i % 2 else _TD_LABEL_STYLE
        val_style = _TD_ALT_STYLE if i % 2 else _TD_STYLE
        rows_html += (
            f"<tr>"
            f"<td style='{label_style}'>{label}</td>"
            f"<td style='{val_style}'>{value}</td>"
            f"</tr>"
        )

    table = f"<table style='{_TABLE_STYLE}'><tbody>{rows_html}</tbody></table>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; color: #333; max-width: 640px; margin: auto; padding: 20px;">
  <h2 style="margin-bottom: 0;">{hackspace_name} - Receipt</h2>
  <p style="margin-top: 4px; color: #666;">
    Thank you for your payment, {customer_name}.
  </p>
  {divider}
  {table}
  {divider}
  <p style="color: #555;">
    This is your receipt from {hackspace_name}. Please retain it for your records.
  </p>
  <p style="font-size: 0.8em; color: #999;">
    Sent automatically by Nucleus. To disable transaction receipts, contact your administrator.
  </p>
</body>
</html>"""


def send_daily_report() -> bool:
    """
    Builds and sends the daily membership summary email via Resend.
    Returns True on successful delivery, False when the feature is disabled or
    a required setting is missing. Raises on unexpected API errors so the
    caller can surface them as notifications.

    Required settings in AppSetting:
      - resend_api_key  (sensitive)
      - report_from_email
      - report_to_email
      - email_reports_enabled  ("true" / "false")
    """
    if get_setting("email_reports_enabled", "false").lower() != "true":
        print("[Email] Daily reports disabled in settings")
        return False

    api_key = get_sensitive_setting_value("resend_api_key")
    from_email = get_setting("report_from_email", "onboarding@resend.dev")
    to_email_raw = get_setting("report_to_email", "")

    if not api_key:
        print("[Email] Cannot send daily report: API key not configured")
        return False

    # Support comma-separated list of recipient addresses.
    to_emails = [addr.strip() for addr in to_email_raw.split(",") if addr.strip()]

    if not to_emails:
        print("[Email] Cannot send daily report: recipient email not configured")
        return False

    resend.api_key = api_key

    data = build_daily_report_data()
    html_body = _build_html(data)

    params = {
        "from": from_email,
        "to": to_emails,
        "subject": f"Nucleus Makerspace Activity Summary - {data['report_date']}",
        "html": html_body,
    }

    resend.Emails.send(params)
    print(f"[Email] Daily report sent to {', '.join(to_emails)}")
    return True


def send_backup_email(backup_path: str, backup_filename: str, to_email: str) -> bool:
    """
    Emails the database backup file as an attachment to the given address.
    Uses the same Resend API key and from-address as the daily report.
    Raises on failure so the caller can surface the error as a notification.
    """
    api_key = get_sensitive_setting_value("resend_api_key")
    if not api_key:
        raise RuntimeError("Resend API key is not configured.")

    from_email = get_setting("report_from_email", "onboarding@resend.dev")

    with open(backup_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    resend.api_key = api_key

    params = {
        "from": from_email,
        "to": [addr.strip() for addr in to_email.split(",") if addr.strip()],
        "subject": f"Nucleus Database Backup - {backup_filename}",
        "html": (
            f"<p>Attached is the automated database backup: "
            f"<strong>{backup_filename}</strong>.</p>"
            f"<p>Store this file securely.</p>"
        ),
        "attachments": [{"filename": backup_filename, "content": encoded}],
    }

    resend.Emails.send(params)
    print(f"[Email] Backup {backup_filename} sent to {to_email}")
    return True


def _build_html(data: dict) -> str:
    """
    Renders the report data into two HTML tables:
    1. A 7-day activity summary with metrics as rows and dates as columns.
    2. A full-detail table of every community contact entry for the period.
    """
    days = data["days"]

    # --- Table 1: 7-day activity summary ---
    # Header row: blank label cell + one column per day
    date_headers = "".join(
        f"<th style='{_TH_STYLE}'>{d['date_label']}</th>" for d in days
    )
    thead = f"<thead><tr><th style='{_TH_STYLE}'>Metric</th>{date_headers}</tr></thead>"

    # One row per metric; label + 7 count cells
    metrics = [
        ("Active Members (total)", "active_members_snapshot"),
        ("New Members", "new_members"),
        ("Memberships Expiring", "memberships_expiring"),
        ("Sign-ins", "sign_ins"),
        ("Volunteers", "volunteers"),
        ("Day Passes", "day_passes"),
        ("Consumables Transactions", "transactions"),
        ("Community Contacts", "community_contacts"),
    ]

    # Active members is a snapshot, not a per-day count — fill it from the top-level key
    active_snapshot = data["total_active_members"]

    body_rows = []
    for i, (label, key) in enumerate(metrics):
        is_alt = i % 2 == 1
        label_style = _TD_ALT_LABEL_STYLE if is_alt else _TD_LABEL_STYLE
        val_style = _TD_ALT_STYLE if is_alt else _TD_STYLE

        label_cell = f"<td style='{label_style}'>{label}</td>"

        if key == "active_members_snapshot":
            # Same snapshot value repeated across all days for reference
            value_cells = "".join(
                f"<td style='{val_style}'>{active_snapshot}</td>" for _ in days
            )
        else:
            value_cells = "".join(
                f"<td style='{val_style}'>{d[key]}</td>" for d in days
            )

        body_rows.append(f"<tr>{label_cell}{value_cells}</tr>")

    tbody = f"<tbody>{''.join(body_rows)}</tbody>"
    summary_table = f"<table style='{_TABLE_STYLE}'>{thead}{tbody}</table>"

    # --- Table 2: Community contacts detail ---
    contacts = data["community_contacts_detail"]
    if contacts:
        contact_header_cells = "".join(
            f"<th style='{_TH_STYLE}'>{h}</th>"
            for h in [
                "Name",
                "Email",
                "Phone",
                "Brought In By",
                "Visited At",
                "Community Tour",
                "Staff Name and Description",
                "Other (please specify)",
            ]
        )
        contact_thead = f"<thead><tr>{contact_header_cells}</tr></thead>"

        contact_rows = []
        for i, c in enumerate(contacts):
            td = _TD_ALT_STYLE if i % 2 else _TD_STYLE
            cells = "".join(
                f"<td style='{td}'>{v}</td>"
                for v in [
                    c["name"],
                    c["email"],
                    c["phone"],
                    c["brought_in_by"],
                    c["visited_at"],
                    c["community_tour"],
                    c["staff"],
                    c["notes"],
                ]
            )
            contact_rows.append(f"<tr>{cells}</tr>")

        contact_tbody = f"<tbody>{''.join(contact_rows)}</tbody>"
        contacts_table = (
            f"<table style='{_TABLE_STYLE}'>{contact_thead}{contact_tbody}</table>"
        )
    else:
        contacts_table = (
            "<p style='color: #888;'>No community contacts recorded in this period.</p>"
        )

    # --- Table 3: Recent transactions detail ---
    txns = data["recent_transactions_detail"]
    if txns:
        txn_header_cells = "".join(
            f"<th style='{_TH_STYLE}'>{h}</th>"
            for h in ["Date", "Customer", "Amount", "Description", "Status", "Via"]
        )
        txn_thead = f"<thead><tr>{txn_header_cells}</tr></thead>"

        txn_rows = []
        for i, t in enumerate(txns):
            td = _TD_ALT_STYLE if i % 2 else _TD_STYLE
            cells = "".join(
                f"<td style='{td}'>{v}</td>"
                for v in [
                    t["date"],
                    t["customer_name"],
                    t["amount"],
                    t["description"],
                    t["status"],
                    t["via"],
                ]
            )
            txn_rows.append(f"<tr>{cells}</tr>")

        txn_tbody = f"<tbody>{''.join(txn_rows)}</tbody>"
        transactions_table = (
            f"<table style='{_TABLE_STYLE}'>{txn_thead}{txn_tbody}</table>"
        )
    else:
        transactions_table = (
            "<p style='color: #888;'>No transactions recorded in this period.</p>"
        )

    # A unique token per send prevents Gmail's threading heuristic from treating
    # repeated sections as "already seen" content from a previous daily report
    # and collapsing them as quoted text.
    from datetime import datetime as _dt

    unique_token = _dt.now().strftime("%Y%m%d%H%M%S%f")

    divider = "<div style='border-top: 1px solid #ddd; margin: 20px 0;'></div>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; color: #333; max-width: 960px; margin: auto; padding: 20px;">
  <div>
    <h2 style="margin-bottom: 0;">{data["hackspace_name"]} - Daily Report</h2>
    <p style="margin-top: 4px; color: #666;">
      <strong>Date:</strong> {data["report_date"]} &nbsp;|&nbsp;
      <strong>Pending Approvals:</strong> {data["pending_approvals"]}
    </p>
    {divider}
    <h3 style="border-bottom: 2px solid #333; padding-bottom: 4px;">
      7-Day Activity Summary
    </h3>
    {summary_table}
    {divider}
    <div>
      <span style="display:none">{unique_token}</span>
      <h3 style="border-bottom: 2px solid #333; padding-bottom: 4px;">
        Community Contacts (last 7 days)
      </h3>
      {contacts_table}
    </div>
    {divider}
    <h3 style="border-bottom: 2px solid #333; padding-bottom: 4px;">
      Transactions (last 7 days)
    </h3>
    {transactions_table}
    {divider}
    <p style="font-size: 0.8em; color: #999;">
      Sent automatically by Nucleus. To disable, turn off daily reports in Settings.
    </p>
  </div>
</body>
</html>"""
