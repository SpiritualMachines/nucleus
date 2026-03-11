"""
Email delivery module for Nucleus using the Resend API.

This module is responsible for building and sending outbound email reports.
It relies on services.py for all data access and never imports from screens/
or any Textual UI code. Configuration (API key, addresses) is read from the
AppSetting table at send time so that admin changes take effect without
restarting the application.
"""

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
    to_email = get_setting("report_to_email", "")

    if not api_key:
        print("[Email] Cannot send daily report: API key not configured")
        return False

    if not to_email:
        print("[Email] Cannot send daily report: recipient email not configured")
        return False

    resend.api_key = api_key

    data = build_daily_report_data()
    html_body = _build_html(data)

    params = {
        "from": from_email,
        "to": [to_email],
        "subject": f"Nucleus Makerspace Activity Summary - {data['report_date']}",
        "html": html_body,
    }

    resend.Emails.send(params)
    print(f"[Email] Daily report sent to {to_email}")
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
                "Staff",
                "Notes",
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

    # A unique token per send prevents Gmail's threading heuristic from treating
    # the community contacts section as "already seen" content from a previous
    # daily report and collapsing it as quoted text. The token is invisible to
    # the reader but is different on every email so Gmail cannot match it.
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
    <p style="font-size: 0.8em; color: #999;">
      Sent automatically by Nucleus. To disable, turn off daily reports in Settings.
    </p>
  </div>
</body>
</html>"""
