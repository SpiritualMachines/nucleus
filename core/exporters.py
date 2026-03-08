import csv
import os
from datetime import datetime

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
except ImportError:
    FPDF = None
    XPos = None
    YPos = None


def ensure_export_dir():
    if not os.path.exists("exports"):
        os.makedirs("exports")


def get_timestamp_filename(base_name: str, extension: str) -> str:
    """Creates a filename like 'members_report_2023-10-27_1430.csv'"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    return f"{base_name}_{timestamp}.{extension}"


def export_to_csv(
    filename: str, headers: list[str], rows: list[list], output_dir: str = None
) -> str:
    if output_dir:
        output_dir = output_dir.strip()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        filepath = os.path.join(output_dir, filename)
    else:
        ensure_export_dir()
        filepath = os.path.join("exports", filename)

    try:
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return filepath
    except Exception as e:
        raise IOError(f"Failed to write CSV: {str(e)}")


def safe_encode(text: str) -> str:
    """Encodes text to Latin-1, replacing errors, to prevent FPDF crashes."""
    # FPDF standard fonts only support Latin-1.
    # We replace unsupported characters (like Emojis) with '?'
    if not isinstance(text, str):
        text = str(text)
    return text.encode("latin-1", "replace").decode("latin-1")


# Keyword groups that determine the relative width weight of a column.
# Earlier entries take priority; unmatched columns fall back to the default weight.
_COLUMN_WEIGHT_RULES: list[tuple[list[str], float]] = [
    # ID columns are always short integers
    (["id"], 0.35),
    # Short, fixed-width values
    (
        [
            "date",
            "time",
            "start",
            "end",
            "amount",
            "type",
            "month",
            "tour",
            "urgent",
            "role",
        ],
        0.85,
    ),
    # Medium-length values with some variance
    (["account", "phone", "visit", "name", "email"], 1.4),
    # Freeform text that can be long and unpredictable
    (
        [
            "description",
            "reason",
            "comment",
            "other",
            "brought",
            "response",
            "allergy",
            "health",
            "warning",
            "interest",
            "skill",
            "accreditation",
        ],
        3.0,
    ),
]
_COLUMN_WEIGHT_DEFAULT = 1.2


def _compute_column_widths(headers: list[str], available_width: float) -> list[float]:
    """
    Returns a list of column widths (in mm) that sum to available_width.
    Widths are proportional to keyword-based weights derived from the header names,
    so short fixed-value columns (like ID) stay narrow while variable-text columns
    (like Description) receive the space they need.
    """
    weights = []
    for h in headers:
        h_lower = h.lower()
        weight = _COLUMN_WEIGHT_DEFAULT
        for keywords, w in _COLUMN_WEIGHT_RULES:
            if any(kw in h_lower for kw in keywords):
                weight = w
                break
        weights.append(weight)
    total = sum(weights)
    return [available_width * (w / total) for w in weights]


def _render_row(
    pdf,
    x_start: float,
    col_widths: list,
    items: list,
    line_height: float,
    border: int = 1,
    align: str = "",
) -> None:
    """
    Renders a single table row using multi_cell so text wraps within each column
    rather than being cut off. Tracks the tallest cell in the row and advances
    the PDF cursor below it so the next row always starts cleanly.
    """
    y_start = pdf.get_y()
    max_y = y_start
    x = x_start
    for cw, item in zip(col_widths, items):
        pdf.set_xy(x, y_start)
        pdf.multi_cell(
            cw, line_height, safe_encode(str(item)), border=border, align=align
        )
        max_y = max(max_y, pdf.get_y())
        x += cw
    pdf.set_y(max_y)


def export_to_pdf(
    filename: str,
    title: str,
    headers: list[str],
    rows: list[list],
    output_dir: str = None,
    header_text: str = "",
) -> str:
    """
    Exports tabular data to a landscape A4 PDF. If header_text is provided it is
    rendered as a subtitle line beneath the report title, allowing admins to include
    custom branding or contact information on every report without code changes.
    """
    if FPDF is None:
        raise ImportError(
            "fpdf2 library is not installed. Please run: pip install fpdf2"
        )

    if output_dir:
        output_dir = output_dir.strip()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        filepath = os.path.join(output_dir, filename)
    else:
        ensure_export_dir()
        filepath = os.path.join("exports", filename)

    # Landscape mode ('L') for wider tables, A4 format
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    # --- Title ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        0, 10, text=safe_encode(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C"
    )

    # --- Optional custom header text (e.g. org name, address, contact info) ---
    if header_text:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(
            0,
            5,
            text=safe_encode(header_text),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="C",
        )
    pdf.ln(5)

    # --- Meta ---
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(
        0,
        5,
        text=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="R",
    )
    pdf.ln(5)

    # --- Table Config ---
    pdf.set_font("Helvetica", "B", 10)
    line_height = 8

    # A4 landscape width is ~297mm; subtract ~20mm for margins
    available_width = 277
    col_widths = _compute_column_widths(headers, available_width)
    x_start = pdf.l_margin

    # --- Headers ---
    _render_row(pdf, x_start, col_widths, headers, line_height, align="C")

    # --- Rows ---
    pdf.set_font("Helvetica", size=9)
    for row in rows:
        if pdf.get_y() > 185:
            pdf.add_page()
        _render_row(pdf, x_start, col_widths, row, line_height)

    pdf.output(name=filepath)
    return filepath


def export_period_report_to_csv(
    filename: str, sections: list[dict], output_dir: str = None
) -> str:
    """
    Exports a multi-section report to a single CSV file.
    Each section dict must have 'title', 'headers', and 'rows' keys.
    Sections are separated by a blank line in the output.
    """
    if output_dir:
        output_dir = output_dir.strip()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        filepath = os.path.join(output_dir, filename)
    else:
        ensure_export_dir()
        filepath = os.path.join("exports", filename)

    try:
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for i, section in enumerate(sections):
                if i > 0:
                    writer.writerow([])  # Blank row between sections
                writer.writerow([section["title"]])
                writer.writerow(section["headers"])
                writer.writerows(section["rows"])
        return filepath
    except Exception as e:
        raise IOError(f"Failed to write CSV: {str(e)}")


def export_period_report_to_pdf(
    filename: str,
    title: str,
    sections: list[dict],
    output_dir: str = None,
    header_text: str = "",
) -> str:
    """
    Exports a multi-section report to a single PDF file.
    Each section dict must have 'title', 'headers', and 'rows' keys.
    Each section starts with a bold heading followed by a data table.
    If header_text is provided it appears beneath the report title on the first page.
    """
    if FPDF is None:
        raise ImportError(
            "fpdf2 library is not installed. Please run: pip install fpdf2"
        )

    if output_dir:
        output_dir = output_dir.strip()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        filepath = os.path.join(output_dir, filename)
    else:
        ensure_export_dir()
        filepath = os.path.join("exports", filename)

    # Landscape A4 for wider tables
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()

    # Report title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        0, 10, text=safe_encode(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C"
    )

    # Optional custom header text beneath the title
    if header_text:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(
            0,
            5,
            text=safe_encode(header_text),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="C",
        )
    pdf.ln(3)

    # Generation timestamp
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(
        0,
        5,
        text=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="R",
    )
    pdf.ln(4)

    available_width = 277  # A4 landscape minus margins (~20mm total)
    line_height = 7

    for section in sections:
        headers = section["headers"]
        rows = section["rows"]

        # Section heading
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(
            0,
            8,
            text=safe_encode(section["title"]),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(1)

        if not rows:
            pdf.set_font("Helvetica", "I", 9)
            pdf.cell(
                0,
                6,
                text="No records in this period.",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            pdf.ln(4)
            continue

        col_widths = _compute_column_widths(headers, available_width)
        x_start = pdf.l_margin

        # Column headers
        pdf.set_font("Helvetica", "B", 9)
        _render_row(pdf, x_start, col_widths, headers, line_height, align="C")

        # Data rows
        pdf.set_font("Helvetica", size=8)
        for row in rows:
            # Start a new page if we are near the bottom (A4 landscape height ~210mm, margins ~10mm each)
            if pdf.get_y() > 185:
                pdf.add_page()
            _render_row(pdf, x_start, col_widths, row, line_height)

        pdf.ln(5)  # Gap between sections

    pdf.output(name=filepath)
    return filepath
