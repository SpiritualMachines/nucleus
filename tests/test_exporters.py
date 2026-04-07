"""Tests for core/exporters.py — CSV and PDF file generation."""

import csv
import os

import pytest

from core import exporters


@pytest.fixture()
def out(tmp_path):
    """Temporary output directory, provided fresh per test by pytest."""
    return str(tmp_path)


# --- Filename helper ---


def test_get_timestamp_filename_starts_with_base_name():
    assert exporters.get_timestamp_filename("my_report", "csv").startswith("my_report_")


def test_get_timestamp_filename_ends_with_extension():
    assert exporters.get_timestamp_filename("report", "pdf").endswith(".pdf")


def test_get_timestamp_filename_csv_and_pdf_differ():
    # Filenames for different formats must differ
    assert exporters.get_timestamp_filename(
        "r", "csv"
    ) != exporters.get_timestamp_filename("r", "pdf")


# --- safe_encode ---


def test_safe_encode_passthrough_ascii():
    assert exporters.safe_encode("Hello World") == "Hello World"


def test_safe_encode_handles_latin1_character():
    # é (U+00E9) is valid Latin-1
    assert exporters.safe_encode("Caf\u00e9") == "Caf\u00e9"


def test_safe_encode_replaces_unsupported_unicode():
    # Emoji is outside Latin-1 range and should become '?'
    result = exporters.safe_encode("Hello \U0001f600")
    assert "?" in result
    assert "Hello" in result


def test_safe_encode_coerces_non_string_to_string():
    assert exporters.safe_encode(42) == "42"
    assert exporters.safe_encode(3.14) == "3.14"


# --- _compute_column_widths ---


def test_column_widths_sum_to_available_width():
    headers = ["ID", "Name", "Description"]
    widths = exporters._compute_column_widths(headers, 277.0)
    assert abs(sum(widths) - 277.0) < 0.01


def test_id_column_is_narrowest():
    headers = ["ID", "Name", "Description"]
    widths = exporters._compute_column_widths(headers, 277.0)
    assert widths[0] < widths[1]  # ID < Name
    assert widths[0] < widths[2]  # ID < Description


def test_description_column_is_widest():
    headers = ["ID", "Name", "Description"]
    widths = exporters._compute_column_widths(headers, 277.0)
    assert widths[2] > widths[1] > widths[0]


def test_unknown_headers_use_default_weight():
    # Two unknown headers should split the width equally
    widths = exporters._compute_column_widths(["Alpha", "Beta"], 100.0)
    assert abs(widths[0] - widths[1]) < 0.01


def test_single_column_gets_full_width():
    widths = exporters._compute_column_widths(["Name"], 200.0)
    assert abs(widths[0] - 200.0) < 0.01


# --- export_to_csv ---


def test_export_to_csv_creates_file(out):
    path = exporters.export_to_csv("test.csv", ["ID", "Name"], [["1", "Alice"]], out)
    assert os.path.exists(path)


def test_export_to_csv_writes_headers(out):
    path = exporters.export_to_csv("h.csv", ["ID", "Name", "Email"], [], out)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["ID", "Name", "Email"]


def test_export_to_csv_writes_data_rows(out):
    path = exporters.export_to_csv(
        "d.csv", ["ID", "Name"], [["1", "Alice"], ["2", "Bob"]], out
    )
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[1] == ["1", "Alice"]
    assert rows[2] == ["2", "Bob"]


def test_export_to_csv_empty_rows(out):
    path = exporters.export_to_csv("empty.csv", ["ID", "Name"], [], out)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["ID", "Name"]]


def test_export_to_csv_creates_output_dir_if_missing(tmp_path):
    subdir = str(tmp_path / "new_subdir")
    path = exporters.export_to_csv("f.csv", ["A"], [["1"]], subdir)
    assert os.path.exists(path)


# --- export_period_report_to_csv ---


def test_export_period_report_to_csv_creates_file(out):
    sections = [
        {"title": "Users", "headers": ["ID", "Name"], "rows": [["1", "Alice"]]},
        {"title": "Contacts", "headers": ["ID", "Email"], "rows": [["2", "b@t.com"]]},
    ]
    path = exporters.export_period_report_to_csv("report.csv", sections, out)
    assert os.path.exists(path)


def test_export_period_report_to_csv_contains_section_titles(out):
    sections = [
        {"title": "Memberships", "headers": ["ID"], "rows": [["1"]]},
        {"title": "Day Passes", "headers": ["ID"], "rows": [["2"]]},
    ]
    path = exporters.export_period_report_to_csv("r.csv", sections, out)
    with open(path, newline="", encoding="utf-8") as f:
        content = f.read()
    assert "Memberships" in content
    assert "Day Passes" in content


def test_export_period_report_to_csv_sections_separated_by_blank_row(out):
    sections = [
        {"title": "A", "headers": ["X"], "rows": [["1"]]},
        {"title": "B", "headers": ["Y"], "rows": [["2"]]},
    ]
    path = exporters.export_period_report_to_csv("sep.csv", sections, out)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    # There must be at least one empty row between sections
    empty_rows = [r for r in rows if r == []]
    assert len(empty_rows) >= 1


def test_export_period_report_to_csv_handles_empty_section(out):
    sections = [{"title": "Empty", "headers": ["ID", "Name"], "rows": []}]
    path = exporters.export_period_report_to_csv("empty.csv", sections, out)
    assert os.path.exists(path)


# --- export_to_pdf ---


def test_export_to_pdf_creates_file(out):
    path = exporters.export_to_pdf(
        "test.pdf",
        "Test Report",
        ["ID", "Name", "Description"],
        [["1", "Alice", "A long description that should wrap cleanly in its cell"]],
        out,
    )
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0


def test_export_to_pdf_handles_empty_rows(out):
    path = exporters.export_to_pdf("empty.pdf", "Empty Report", ["ID", "Name"], [], out)
    assert os.path.exists(path)


def test_export_to_pdf_many_rows_does_not_raise(out):
    headers = ["ID", "Name", "Date", "Description"]
    rows = [
        [str(i), f"Person {i}", "2026-01-01", "Some description text"]
        for i in range(100)
    ]
    path = exporters.export_to_pdf("many.pdf", "Large Report", headers, rows, out)
    assert os.path.exists(path)


# --- export_period_report_to_pdf ---


def test_export_period_report_to_pdf_creates_file(out):
    sections = [
        {
            "title": "Memberships",
            "headers": ["ID", "Name", "Start Date", "End Date", "Description"],
            "rows": [["1", "Alice Smith", "2026-01-01", "2026-02-01", "Monthly"]],
        },
        {
            "title": "Day Passes",
            "headers": ["ID", "Name", "Date", "Description"],
            "rows": [],
        },
    ]
    path = exporters.export_period_report_to_pdf(
        "period.pdf", "Period Traction Report", sections, out
    )
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0


def test_export_period_report_to_pdf_all_empty_sections(out):
    sections = [
        {"title": "Empty Section", "headers": ["ID", "Name"], "rows": []},
    ]
    path = exporters.export_period_report_to_pdf("empty.pdf", "Empty", sections, out)
    assert os.path.exists(path)
