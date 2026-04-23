"""
Convert USER_MANUAL.md to a formatted PDF.

Usage:
    python scripts/export_manual_pdf.py [output_path]

If output_path is omitted the PDF is written to the project root as
USER_MANUAL.pdf.

Requires: fpdf2 (already in requirements.txt), markdown-it-py (already
installed as a transitive dependency).
"""

import os
import re
import sys
from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import TextStyle
from markdown_it import MarkdownIt

# ---------------------------------------------------------------------------
# Font paths — Liberation fonts ship with most Linux distros and are available
# for Windows/macOS as a free download. They are Unicode-capable and cover all
# characters used in this manual (em-dash, curly quotes, etc.).
# ---------------------------------------------------------------------------
SANS_DIR = "/usr/share/fonts/liberation-sans-fonts"
MONO_DIR = "/usr/share/fonts/liberation-mono-fonts"

FONT_SANS_REG  = f"{SANS_DIR}/LiberationSans-Regular.ttf"
FONT_SANS_BOLD = f"{SANS_DIR}/LiberationSans-Bold.ttf"
FONT_SANS_IT   = f"{SANS_DIR}/LiberationSans-Italic.ttf"
FONT_SANS_BI   = f"{SANS_DIR}/LiberationSans-BoldItalic.ttf"
FONT_MONO_REG  = f"{MONO_DIR}/LiberationMono-Regular.ttf"
FONT_MONO_BOLD = f"{MONO_DIR}/LiberationMono-Bold.ttf"

DARK   = (30,  30,  30)
MID    = (80,  80,  80)
LIGHT  = (140, 140, 140)
ACCENT = (50,  90,  160)


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def md_to_html(md_text: str) -> str:
    """Render Markdown to HTML using markdown-it-py with table support."""
    md = MarkdownIt("commonmark").enable("table")
    return md.render(md_text)


def extract_toc_entries(md_text: str) -> list[tuple[int, str]]:
    """
    Parse the Table of Contents block from the markdown and return a list of
    (indent_level, display_text) tuples. indent_level 0 = top-level section,
    1 = sub-section.
    """
    toc_start = md_text.find("## Table of Contents")
    if toc_start == -1:
        return []
    toc_end = md_text.find("\n---\n", toc_start)
    if toc_end == -1:
        return []

    entries = []
    for line in md_text[toc_start:toc_end].splitlines():
        # Top-level: "1. [Title](#anchor)" or "10. [Title](#anchor)"
        m = re.match(r"^(\d+)\.\s+\[([^\]]+)\]", line.lstrip())
        if m and not line.startswith(" "):
            entries.append((0, f"{m.group(1)}.  {m.group(2)}"))
            continue
        # Sub-item: "   - [Sub Title](#anchor)"
        m = re.match(r"^\s+-\s+\[([^\]]+)\]", line)
        if m:
            entries.append((1, m.group(1)))

    return entries


def strip_toc_block(md_text: str) -> str:
    """Remove the Table of Contents block from the markdown source."""
    toc_start = md_text.find("## Table of Contents\n")
    if toc_start == -1:
        return md_text
    toc_end = md_text.find("\n---\n", toc_start)
    if toc_end == -1:
        return md_text
    return md_text[:toc_start] + md_text[toc_end:]


def preprocess_html(html: str) -> str:
    """
    Normalise the HTML so fpdf2's write_html renders it cleanly.
    """
    # fpdf2 does not render <pre><code> well — strip inner <code> tags.
    html = re.sub(r"<pre><code[^>]*>", "<pre>", html)
    html = html.replace("</code></pre>", "</pre>")

    # Replace <hr> with a visible separator (fpdf2 ignores <hr> in write_html).
    html = re.sub(
        r"<hr\s*/?>",
        "<p><font color=\"#aaaaaa\">_____________________________________________"
        "___________________________</font></p>",
        html,
    )

    # Strip internal anchor links — fpdf2 cannot resolve them.
    html = re.sub(r'<a\s+href="#[^"]*"[^>]*>(.*?)</a>', r"\1", html, flags=re.DOTALL)

    # Strip target attributes from external links.
    html = re.sub(r'\s+target="[^"]*"', "", html)

    return html


def extract_license_text(license_path: str) -> str:
    """
    Read LICENSE.md and return a single clean copy of the AGPLv3 text.

    The project's LICENSE.md contains duplicated text. This function splits on
    the license header, locates the longest segment that ends with
    "END OF TERMS AND CONDITIONS", and returns that segment with the
    "How to Apply" section appended.
    """
    if not os.path.exists(license_path):
        return (
            "GNU Affero General Public License, Version 3\n\n"
            "The full license text is available at:\n"
            "https://www.gnu.org/licenses/agpl-3.0.html\n"
        )

    with open(license_path, encoding="utf-8") as f:
        raw = f.read()

    # Split into segments at each occurrence of the license header.
    segments = re.split(r"GNU AFFERO GENERAL PUBLIC LICENSE\s+Version 3", raw)

    # Reconstruct each segment with its header and find the longest clean one.
    best = ""
    for seg in segments[1:]:
        candidate = "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3" + seg
        end_marker = "END OF TERMS AND CONDITIONS"
        if end_marker in candidate:
            # Keep only through the end of the "How to Apply" appendix.
            apply_end = candidate.rfind("<https://www.gnu.org/licenses/>.")
            if apply_end != -1:
                candidate = candidate[: apply_end + len("<https://www.gnu.org/licenses/>.")] + "\n"
            end_pos = candidate.find(end_marker)
            clean = candidate[: end_pos + len(end_marker)]
            # Grab the "How to Apply" block that follows
            after = candidate[end_pos + len(end_marker):]
            apply_start = after.find("How to Apply")
            if apply_start != -1:
                clean += "\n" + after[apply_start:]
            if len(clean) > len(best):
                best = clean

    return best if best else (
        "GNU Affero General Public License, Version 3\n\n"
        "See LICENSE.md or https://www.gnu.org/licenses/agpl-3.0.html\n"
    )


# ---------------------------------------------------------------------------
# PDF class
# ---------------------------------------------------------------------------

class ManualPDF(FPDF):
    """FPDF subclass with running header and footer on content pages."""

    # Set to False on the cover and TOC pages so they get a clean look.
    show_header_footer = False

    def header(self):
        if not self.show_header_footer:
            return
        self.set_font("LiberationSans", "B", 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 6, "Nucleus User Manual", align="L")
        self.set_draw_color(210, 210, 210)
        self.line(self.l_margin, self.get_y() + 6, self.w - self.r_margin, self.get_y() + 6)
        self.ln(9)
        self.set_text_color(*DARK)

    def footer(self):
        if not self.show_header_footer:
            return
        self.set_y(-13)
        self.set_font("LiberationSans", "I", 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(*DARK)

    # ------------------------------------------------------------------
    # Cover page
    # ------------------------------------------------------------------

    def draw_cover_page(self):
        """Render a title page with Spiritual Machines branding."""
        self.show_header_footer = False
        self.add_page()

        page_h = self.h
        page_w = self.w
        l = self.l_margin
        usable_w = page_w - l - self.r_margin

        # Top accent bar
        self.set_fill_color(*ACCENT)
        self.rect(0, 0, page_w, 6, style="F")

        # Title block — centred vertically in the upper half
        self.set_y(page_h * 0.28)

        self.set_font("LiberationSans", "B", 36)
        self.set_text_color(*DARK)
        self.cell(0, 14, "Nucleus", align="C")
        self.ln(14)

        self.set_font("LiberationSans", "", 16)
        self.set_text_color(*MID)
        self.cell(0, 8, "User Manual", align="C")
        self.ln(8)

        self.set_font("LiberationSans", "I", 11)
        self.set_text_color(*LIGHT)
        self.cell(0, 7, "Membership Management for Hackerspaces and Makerspaces", align="C")
        self.ln(24)

        # Divider
        self.set_draw_color(*ACCENT)
        mid_x = page_w / 2
        self.line(mid_x - 35, self.get_y(), mid_x + 35, self.get_y())
        self.ln(20)

        # Spiritual Machines attribution block
        self.set_font("LiberationSans", "B", 12)
        self.set_text_color(*DARK)
        self.cell(0, 7, "A Spiritual Machines Project", align="C")
        self.ln(7)

        self.set_font("LiberationSans", "", 11)
        self.set_text_color(*MID)
        self.cell(0, 6, "Spiritual Machines Inc.", align="C")
        self.ln(6)

        self.set_font("LiberationSans", "", 10)
        self.set_text_color(*ACCENT)
        self.cell(0, 6, "https://spiritualmachines.ca", align="C", link="https://spiritualmachines.ca")
        self.ln(6)

        # Version and date — bottom of page
        self.set_y(page_h - 28)
        self.set_draw_color(210, 210, 210)
        self.line(l, self.get_y(), l + usable_w, self.get_y())
        self.ln(5)

        self.set_font("LiberationSans", "", 9)
        self.set_text_color(*LIGHT)
        self.cell(0, 5, f"v0.9.8   |   {datetime.now().strftime('%B %Y')}   |   Licensed under AGPLv3", align="C")

        # Bottom accent bar
        self.set_fill_color(*ACCENT)
        self.rect(0, page_h - 6, page_w, 6, style="F")

    # ------------------------------------------------------------------
    # Table of contents page
    # ------------------------------------------------------------------

    def draw_toc_page(self, entries: list[tuple[int, str]]):
        """Render a clean, well-spaced table of contents."""
        self.show_header_footer = False
        self.add_page()

        self.set_font("LiberationSans", "B", 18)
        self.set_text_color(*DARK)
        self.cell(0, 10, "Table of Contents", align="L")
        self.ln(4)

        self.set_draw_color(*ACCENT)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(10)

        for level, text in entries:
            if level == 0:
                self.set_font("LiberationSans", "B", 10)
                self.set_text_color(*DARK)
                self.set_x(self.l_margin)
                self.cell(0, 7, text, align="L")
                self.ln(7)
            else:
                self.set_font("LiberationSans", "", 9)
                self.set_text_color(*MID)
                self.set_x(self.l_margin + 10)
                self.cell(0, 5.5, text, align="L")
                self.ln(5.5)

    # ------------------------------------------------------------------
    # License page
    # ------------------------------------------------------------------

    def draw_license_page(self, license_text: str):
        """Render the full AGPLv3 license on a new page."""
        self.show_header_footer = False
        self.add_page()

        self.set_font("LiberationSans", "B", 16)
        self.set_text_color(*DARK)
        self.cell(0, 10, "License", align="L")
        self.ln(4)

        self.set_draw_color(*ACCENT)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(8)

        self.set_font("LiberationSans", "", 9)
        self.set_text_color(*MID)
        self.cell(0, 5, "Nucleus is free software. It is released under the terms below.", align="L")
        self.ln(10)

        self.set_font("LiberationMono", "", 6.5)
        self.set_text_color(60, 60, 60)

        # Render each line; preserve blank lines as spacing.
        for line in license_text.splitlines():
            stripped = line.rstrip()
            if stripped == "":
                self.ln(3)
            else:
                self.set_x(self.l_margin)
                self.multi_cell(0, 3.8, stripped, align="L")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manual_path  = os.path.join(project_root, "USER_MANUAL.md")
    license_path = os.path.join(project_root, "LICENSE.md")

    if not os.path.exists(manual_path):
        print(f"ERROR: USER_MANUAL.md not found at {manual_path}")
        sys.exit(1)

    output_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        project_root, "USER_MANUAL.pdf"
    )

    print("Reading source files ...")
    with open(manual_path, encoding="utf-8") as f:
        md_text = f.read()

    license_text = extract_license_text(license_path)

    print("Parsing table of contents ...")
    toc_entries = extract_toc_entries(md_text)
    md_body     = strip_toc_block(md_text)

    print("Converting Markdown to HTML ...")
    html = md_to_html(md_body)
    html = preprocess_html(html)

    print("Rendering PDF ...")
    pdf = ManualPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=22, top=22, right=22)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_title("Nucleus User Manual")
    pdf.set_author("Spiritual Machines Inc.")
    pdf.set_creator("Nucleus export_manual_pdf.py")

    # Register Unicode fonts.
    pdf.add_font("LiberationSans", style="",   fname=FONT_SANS_REG)
    pdf.add_font("LiberationSans", style="B",  fname=FONT_SANS_BOLD)
    pdf.add_font("LiberationSans", style="I",  fname=FONT_SANS_IT)
    pdf.add_font("LiberationSans", style="BI", fname=FONT_SANS_BI)
    pdf.add_font("LiberationMono", style="",   fname=FONT_MONO_REG)
    pdf.add_font("LiberationMono", style="B",  fname=FONT_MONO_BOLD)

    # --- Cover page ---
    pdf.draw_cover_page()

    # --- Table of contents ---
    if toc_entries:
        pdf.draw_toc_page(toc_entries)

    # --- Main content ---
    pdf.show_header_footer = True
    pdf.add_page()
    pdf.set_font("LiberationSans", size=10)

    pdf.write_html(
        html,
        tag_styles={
            "h1":   TextStyle(font_family="LiberationSans", font_size_pt=20, color=DARK,  t_margin=8,  b_margin=4),
            "h2":   TextStyle(font_family="LiberationSans", font_size_pt=15, color=DARK,  t_margin=7,  b_margin=3),
            "h3":   TextStyle(font_family="LiberationSans", font_size_pt=12, color=DARK,  t_margin=6,  b_margin=2),
            "h4":   TextStyle(font_family="LiberationSans", font_size_pt=10, color=MID,   t_margin=5,  b_margin=2),
            "p":    TextStyle(font_family="LiberationSans", font_size_pt=10,              t_margin=2,  b_margin=2),
            "pre":  TextStyle(font_family="LiberationMono", font_size_pt=8,               t_margin=3,  b_margin=3),
            "code": TextStyle(font_family="LiberationMono", font_size_pt=9),
        },
    )

    # --- License ---
    pdf.draw_license_page(license_text)

    pdf.output(output_path)
    print(f"PDF written to: {output_path}")


if __name__ == "__main__":
    main()
