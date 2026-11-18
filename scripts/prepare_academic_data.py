"""Build source-linked faculty and curriculum datasets from official AISHE and SRM files.

Primary responsibility: extract AISHE teacher tables and SRM faculty/curriculum text,
then produce structured CSVs, searchable Markdown, and readable PDF reference files.
This exists to add reliable faculty and semester-course information to the admissions RAG corpus.
"""
from __future__ import annotations

import csv
import os
import re
import sys
import tempfile
from pathlib import Path

import pandas as pd
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SOURCE_DIR = RAW / "academic_sources"
STRUCTURED = ROOT / "data" / "structured"
PROCESSED = ROOT / "data" / "processed"
AISHE = RAW / "AISHE Final Report 2023-24.xlsx"

SHEETS = {
    "22TeacherPost": "aishe_2023_24_teachers_by_state_and_post.csv",
    "22aTeacherPostUC": "aishe_2023_24_teachers_universities_and_colleges_by_post.csv",
    "22bTeacherPostU": "aishe_2023_24_teachers_university_departments_by_post.csv",
    "21TeacherCategory": "aishe_2023_24_teachers_by_state_and_social_group.csv",
    "29TypeTeacherPostEstimated": "aishe_2023_24_teachers_by_university_type_and_post.csv",
    "30TypeTeacherCategoryEstimated": "aishe_2023_24_teachers_by_university_type_and_social_group.csv",
    "51PostTeacher": "aishe_2023_24_teachers_five_year_trend.csv",
}

SOURCES = [
    ("AISHE Final Report 2023-24 (Excel)", "https://aishe.gov.in/aishe-final-report/", "National and state faculty counts, posts, gender and social-group distributions. Aggregated statistics; no nationwide person-level faculty directory."),
    ("AICTE Model Curriculum - Computer Science and Engineering", "https://www.aicte.gov.in/sites/default/files/Updated-AICTE%20-%20UG%20CSE.pdf", "India-wide model undergraduate engineering curriculum; semester structure and detailed course content. Institutions may adopt or modify it."),
    ("AICTE Model Curriculum - Civil Engineering (January 2024)", "https://www.aicte.gov.in/sites/default/files/AICTE%20Model%20Curriculum%20_UG_Civil_2024.pdf", "India-wide model undergraduate Civil Engineering curriculum; semester structure and detailed course content."),
    ("AICTE Revised Model Curriculum - Electronics and Communication Engineering", "https://www.aicte.gov.in/sites/default/files/Final_ECE.pdf", "India-wide model undergraduate ECE curriculum; semester structure and detailed course content."),
    ("AICTE Model Curriculum - Electrical Engineering", "https://aicte.gov.in/sites/default/files/ug-vol1.pdf", "India-wide model undergraduate Electrical Engineering curriculum; semester structure and detailed course content."),
    ("AICTE Revised Model Curriculum - Mechanical Engineering", "https://www.aicte.gov.in/sites/default/files/Final_Mechanical%20Engg.pdf", "India-wide model undergraduate Mechanical Engineering curriculum; semester structure and detailed course content."),
    ("SRMIST Engineering Handbook 2025-26", "https://webstor.srmist.edu.in/web_assets/downloads/2025/hand-book-2025-26.pdf", "Named faculty, qualifications, roles and academic departments by SRM campus. Handbook is a dated snapshot and not a live directory."),
    ("SRMIST B.Tech CSE (Information Technology specialization) curriculum, Regulations 2026", "https://webstor.srmist.edu.in/web_assets/downloads/2026/srmist-btech-computer-science-and-engineering-information-technology-curriculum-2026.pdf", "Eight-semester SRMIST curriculum, Kattankulathur. Specific to the CSE-IT specialization; not a universal SRM curriculum."),
]


def clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    s = re.sub(r"\s+", " ", str(value)).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def flatten_aishe_sheet(df: pd.DataFrame, sheet_name: str) -> tuple[list[str], list[dict[str, str]]]:
    """Flatten AISHE's merged two-level column headings without changing reported values."""
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if len(df) < 5:
        return [], []
    width = df.shape[1]
    row1 = [clean(v) for v in df.iloc[1].tolist()]
    row2 = [clean(v) for v in df.iloc[2].tolist()]
    names = [row1[0] or "serial_number", row1[1] or "geography_or_group"]
    group = ""
    for col in range(2, width):
        if row1[col] and not row1[col].isdigit():
            group = row1[col]
        sub = row2[col]
        name = " - ".join(part for part in (group, sub) if part and not part.isdigit())
        names.append(name or f"column_{col + 1}")
    # Disambiguate repeated or blank header names while preserving their meaning.
    seen: dict[str, int] = {}
    unique_names = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        unique_names.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    records = []
    for values in df.iloc[4:].itertuples(index=False, name=None):
        row = [clean(v) for v in values]
        if len(row) < len(unique_names) or not any(row):
            continue
        record = dict(zip(unique_names, row))
        # Skip source tables' repeated column-number rows.
        label = record.get(unique_names[1], "")
        if label.isdigit() and all(not v or v.isdigit() for v in row):
            continue
        records.append(record)
    return unique_names, records


def write_aishe_outputs() -> dict[str, list[dict[str, str]]]:
    sheets = pd.read_excel(AISHE, sheet_name=None, header=None)
    extracted: dict[str, list[dict[str, str]]] = {}
    for sheet, filename in SHEETS.items():
        headers, rows = flatten_aishe_sheet(sheets[sheet], sheet)
        out = STRUCTURED / filename
        with out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        extracted[sheet] = rows
    post_rows = extracted["22TeacherPost"]
    lines = [
        "# India-wide higher-education faculty counts (AISHE 2023-24)",
        "",
        "This is an official Ministry of Education AISHE statistical extraction. It reports teacher counts by State/UT, designation, gender, university/college coverage and other groupings. It does not publish one consolidated person-by-person faculty directory.",
        "",
        "The tables below reflect institution submissions available for the survey year; coverage can vary by state and institution. Counts describe reported staff, not current 2026 employment.",
        "",
        "Source: https://aishe.gov.in/aishe-final-report/ (AISHE Final Report 2023-24, Excel).",
        "",
        "## State and Union Territory rows: Table 22",
        "",
    ]
    for row in post_rows:
        region = next((v for k, v in row.items() if "geography" in k or "States/UTs" in k), "")
        fields = [f"{k}: {v}" for k, v in row.items() if v and k not in ("serial_number", "Sl. No.", "Sl.  No.", "geography_or_group", "States/UTs")]
        if region:
            lines.append(f"- {region}: " + "; ".join(fields) + ".")
    lines.extend(["", "## Included structured files", ""])
    for sheet, filename in SHEETS.items():
        lines.append(f"- `{filename}`: AISHE workbook sheet `{sheet}` ({len(extracted[sheet])} extracted rows).")
    (RAW / "aishe_2023_24_faculty_data.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return extracted


def extract_faculty_text() -> str:
    path = SOURCE_DIR / "srmist_engineering_handbook_2025_26_faculty.pdf"
    reader = PdfReader(path)
    pages = []
    # Faculty-and-staff directory begins on PDF page 350 (printed page 342).
    for page_number in range(350, min(len(reader.pages), 500) + 1):
        text = (reader.pages[page_number - 1].extract_text() or "").strip()
        if not text:
            continue
        text = re.sub(r"\n{3,}", "\n\n", text)
        pages.append(f"\n## Handbook PDF page {page_number}\n\n{text}")
    header = (
        "# SRMIST Engineering faculty directory - handbook 2025-26\n\n"
        "Extracted from the official SRMIST Engineering Handbook 2025-26, faculty and staff section (printed pages 342 onward). Names, qualifications, roles, campus and department are reproduced as listed in that dated handbook. This is not a live employment directory; verify current appointments with SRMIST.\n\n"
        "Source: https://webstor.srmist.edu.in/web_assets/downloads/2025/hand-book-2025-26.pdf\n"
    )
    return header + "\n".join(pages) + "\n"


def extract_srm_faculty_csv() -> int:
    """Create one assignment per listed faculty member, retaining source line text verbatim."""
    path = SOURCE_DIR / "srmist_engineering_handbook_2025_26_faculty.pdf"
    reader = PdfReader(path)
    campus = ""
    department = ""
    in_faculty_roster = False
    rows: list[dict[str, str]] = []
    entry_lines: list[str] = []
    entry_page = 0

    def save_entry() -> None:
        if entry_lines:
            entry = re.sub(r"\s+", " ", " ".join(entry_lines)).strip()
            if not re.search(r"\b(Professor|Associate Professor|Assistant Professor|Professor of Practice|Research Professor|Visiting Professor|Adjunct Faculty|Lecturer|Teaching Fellow)\b", entry, re.I):
                return
            rows.append({
                "campus": campus,
                "department": department,
                "handbook_entry": entry,
                "source_pdf_page": str(entry_page),
                "source": "SRMIST Engineering Handbook 2025-26",
            })

    campus_patterns = [
        ("Kattankulathur", re.compile(r"^KATTANKULATHUR CAMPUS$", re.I)),
        ("Ramapuram", re.compile(r"^RAMAPURAM CAMPUS$", re.I)),
        ("Vadapalani", re.compile(r"^RAMAPURAM CAMPUS PART\s*-\s*VADAPALANI$", re.I)),
        ("Delhi-NCR / Modinagar", re.compile(r"^DELHI-NCR CAMPUS, MODINAGAR$", re.I)),
        ("Tiruchirappalli", re.compile(r"^TIRUCHIRAPPALLI CAMPUS$", re.I)),
    ]
    for page_idx in range(349, min(len(reader.pages), 500)):
        text = reader.pages[page_idx].extract_text() or ""
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" \t\u25cf\u2022")
            if not line:
                continue
            matched_campus = next((name for name, pattern in campus_patterns if pattern.match(line)), None)
            if matched_campus:
                save_entry(); entry_lines = []
                campus, department = matched_campus, ""
                in_faculty_roster = False
                continue
            if line.upper() == "FACULTY MEMBERS":
                save_entry(); entry_lines = []
                in_faculty_roster = True
                continue
            if line.upper() == "FACULTY AND STAFF DETAILS":
                save_entry(); entry_lines = []
                in_faculty_roster = False
                continue
            if line.upper().startswith("DEPARTMENT OF "):
                save_entry(); entry_lines = []
                department = line[14:].strip().title()
                in_faculty_roster = True
                continue
            if line.upper().startswith("SCHOOL OF "):
                continue
            if line.isupper() and len(line) > 3 and not re.match(r"^\d+[.)]", line):
                # Academic headings set the department; other uppercase headings end roster extraction.
                department_terms = ("ENGINEERING", "BIOTECHNOLOGY", "INFORMATION TECHNOLOGY", "COMPUTING", "ARTIFICIAL INTELLIGENCE", "MATHEMATICS", "PHYSICS", "CHEMISTRY", "ENGLISH", "LANGUAGES", "NANOTECHNOLOGY", "DATA SCIENCE", "MANAGEMENT", "ARCHITECTURE")
                if any(term in line for term in department_terms):
                    save_entry(); entry_lines = []
                    department = line.title()
                    in_faculty_roster = True
                elif in_faculty_roster:
                    save_entry(); entry_lines = []
                    department = ""
                    in_faculty_roster = False
                continue
            if not in_faculty_roster:
                continue
            if re.match(r"^\d{1,3}[.)]\s+", line):
                save_entry(); entry_lines = [line]; entry_page = page_idx + 1
            elif entry_lines:
                entry_lines.append(line)
    save_entry()
    out = STRUCTURED / "srmist_faculty_2025_26.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["campus", "department", "handbook_entry", "source_pdf_page", "source"])
        writer.writeheader(); writer.writerows(rows)
    return len(rows)


def extract_srm_curriculum_text() -> str:
    path = SOURCE_DIR / "srmist_btech_cse_curriculum_2026.pdf"
    reader = PdfReader(path)
    body = []
    for number, page in enumerate(reader.pages, start=1):
        body.append(f"\n## Source PDF page {number}\n\n{(page.extract_text() or '').strip()}")
    return (
        "# SRMIST B.Tech CSE-IT curriculum, Regulations 2026\n\n"
        "SRM Institute of Science and Technology, Kattankulathur. The source names the programme as B.Tech Computer Science and Engineering with Specialization in Information Technology / B.Tech Information Technology. Semester plans, course codes, titles, weekly lecture/tutorial/practical hours, and credits below are transcribed from the university's 2026 regulations. This is institution- and programme-specific.\n\n"
        "Source: https://webstor.srmist.edu.in/web_assets/downloads/2026/srmist-btech-computer-science-and-engineering-information-technology-curriculum-2026.pdf\n"
        + "\n".join(body) + "\n"
    )


def extract_srm_semester_csv() -> int:
    """Parse course codes and semester assignments from the official curriculum schedule page."""
    reader = PdfReader(SOURCE_DIR / "srmist_btech_cse_curriculum_2026.pdf")
    text = reader.pages[3].extract_text() or ""
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]
    semester = ""
    pending: list[str] = []
    rows: list[dict[str, str]] = []
    code_re = re.compile(r"26[A-Z]{2,4}\d{3,4}[A-Z]")

    def save_block() -> None:
        if not pending or not semester:
            return
        block = " ".join(pending)
        match = code_re.search(block)
        code = match.group(0) if match else ""
        if not match and not re.search(r"skill enhancement course|discipline skill elective|multidisciplinary skill course", block, re.I):
            return
        title = block[match.end():].strip() if match else block
        title = re.sub(r"\s+", " ", title)
        metrics = re.search(r"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", title)
        lecture = tutorial = practical = credits = ""
        if metrics:
            lecture, tutorial, practical, credits = metrics.groups()
            title = title[:metrics.start()].strip()
        elif not code:
            requirement = re.match(r"^(Skill Enhancement Course|Discipline Skill Elective Course|Multidisciplinary Skill Course)\s+(\d+)\s+(\d+)\s*$", title, re.I)
            if requirement:
                title = f"{requirement.group(1)} {requirement.group(2)}"
                credits = requirement.group(3)
        title = re.sub(r"\s+OR$", "", title, flags=re.I).strip()
        title = re.sub(r"\s+", " ", title).strip(" -*")
        if code.startswith("226GNN"):
            code = code[1:]
        if title:
            rows.append({"programme": "B.Tech CSE with IT specialization / B.Tech IT", "regulations": "2026", "semester": semester, "course_code": code, "course_title_or_requirement": title, "lecture_hours_week": lecture, "tutorial_hours_week": tutorial, "practical_hours_week": practical, "credits": credits, "source": "SRMIST official 2026 curriculum"})

    for line in lines:
        sem = re.match(r"^Semester\s+(\d+)\s*$", line, re.I)
        if sem:
            save_block(); pending = []; semester = sem.group(1); continue
        if line.lower().startswith("total learning credits") or line.lower().startswith("(total credits"):
            save_block(); pending = []; continue
        if line.upper() == "OR":
            save_block(); pending = []; continue
        has_code = code_re.search(line) is not None or re.search(r"226GNN\d{4}[A-Z]", line) is not None
        if has_code:
            save_block(); pending = [line]
        elif re.match(r"^(Skill Enhancement Course|Discipline Skill Elective Course|Multidisciplinary Skill Course)\s+\d+", line, re.I):
            save_block(); pending = [line]
        elif pending:
            pending.append(line)
    save_block()
    out = STRUCTURED / "srmist_btech_cse_it_semester_curriculum_2026.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["programme", "regulations", "semester", "course_code", "course_title_or_requirement", "lecture_hours_week", "tutorial_hours_week", "practical_hours_week", "credits", "source"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return len(rows)


def write_source_catalog() -> None:
    lines = [
        "# Faculty and syllabus source catalog",
        "",
        "These records expand the admissions corpus with faculty counts, department faculty listings, and semester-level engineering curricula.",
        "",
        "## Important coverage distinction",
        "",
        "AISHE is the India-wide source for aggregate teacher counts and distributions. Its published annual workbook does not provide a single public national roster of every teacher by name. Named faculty are available institution by institution through approved disclosures, annual handbooks, and faculty pages; these records can be stale and must carry institution, campus, department, and observation date.",
        "",
        "AICTE model curricula provide national reference syllabi for common engineering disciplines. They are not a claim that all Indian colleges teach identical semester courses. University and autonomous-college curricula take precedence for a student-specific answer.",
        "",
        "## Sources",
        "",
    ]
    for title, url, scope in SOURCES:
        lines.append(f"- **{title}.** {scope} Source: {url}")
    (RAW / "faculty_and_syllabus_sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_pdfs() -> None:
    # reportlab is installed only in a temporary build-tools directory.
    build_tools = Path(tempfile.gettempdir()) / "codex-reportlab"
    sys.path.insert(0, str(build_tools))
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    PROCESSED.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallNote", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10, alignment=TA_LEFT))

    # Faculty data PDF with state-by-state totals extracted from AISHE Table 22.
    report_path = PROCESSED / "india_faculty_counts_aishe_2023_24.pdf"
    doc = SimpleDocTemplate(str(report_path), pagesize=landscape(letter), rightMargin=0.45*inch, leftMargin=0.45*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    staff = pd.read_csv(STRUCTURED / SHEETS["22TeacherPost"])
    selected = ["States/UTs", "Professor & Equivalent - Total", "Reader & Associate Professor - Total", "Lecturer/ Assistant Professor - Total", "Grand Total - Total"]
    staff = staff[selected].copy()
    for col in selected[1:]:
        staff[col] = staff[col].map(lambda value: "" if pd.isna(value) else f"{int(value):,}")
    table_data = [["State/UT", "Professor & equivalent", "Associate professor", "Assistant professor", "All listed teachers"]]
    table_data.extend(staff.itertuples(index=False, name=None))
    state_table = Table(table_data, colWidths=[2.0*inch, 1.8*inch, 1.8*inch, 1.8*inch, 1.8*inch], repeatRows=1)
    state_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#9EADBA")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#EDF3F8")]),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
    ]))
    story = [
        Paragraph("India-wide Higher-Education Faculty Data", styles["Title"]),
        Paragraph("AISHE Final Report 2023-24 | Ministry of Education, Government of India", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph("This source gives reported faculty counts by State/UT and designation, gender, institution type, and social group. It is the best available national baseline in the project, but it is aggregated: it does not identify every faculty member by name or assign each teacher to a department. For names and department-level profiles, use institution-specific official disclosures.", styles["BodyText"]),
        Spacer(1, 8),
        Paragraph("The complete extracted tables are supplied as CSV files in data/structured. The existing source workbook has 60 sheets; this extraction includes seven teacher-specific tables, including state counts, university subtypes, social-group distributions, and a five-year trend.", styles["BodyText"]),
        Spacer(1, 8),
        Paragraph("Source: https://aishe.gov.in/aishe-final-report/ — AISHE Final Report 2023-24 (Excel). Counts reflect reported responses for the survey period; they are not a live 2026 staffing count.", styles["SmallNote"]),
        Spacer(1, 14),
        Paragraph("State and Union Territory counts", styles["Heading1"]),
        Paragraph("These figures are taken from AISHE Table 22. Missing cells remain blank in the source; they are not silently treated as zero.", styles["SmallNote"]),
        Spacer(1, 6),
        state_table,
        PageBreak(),
        Paragraph("How to use these data", styles["Heading1"]),
        Paragraph("Use AISHE for national and state comparisons, faculty gender/category distributions, and broad staff-position counts. Do not answer questions such as ‘Who teaches CSE at College X?’ from these aggregate tables; retrieve that college’s latest faculty directory instead.", styles["BodyText"]),
        PageBreak(),
        Paragraph("Extracted files", styles["Heading1"]),
    ]
    files = [(name, filename) for name, filename in SHEETS.items()]
    data = [["AISHE sheet", "Extracted data file", "Use"]]
    uses = {
        "22TeacherPost": "State/UT, designation and gender totals",
        "22aTeacherPostUC": "Universities and their colleges by designation",
        "22bTeacherPostU": "University departments and constituent units by designation",
        "21TeacherCategory": "Teacher counts by social group and gender",
        "29TypeTeacherPostEstimated": "University type by designation",
        "30TypeTeacherCategoryEstimated": "University type by social group",
        "51PostTeacher": "Five-year trend by State/UT and designation",
    }
    for sheet, filename in files:
        data.append([sheet, filename, uses[sheet]])
    t = Table(data, colWidths=[2.4*inch, 3.3*inch, 4.0*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#9EADBA")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#EDF3F8")]),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    doc.build(story)

    # Make a precisely paginated excerpt of the SRM handbook faculty section.
    handbook = PdfReader(str(SOURCE_DIR / "srmist_engineering_handbook_2025_26_faculty.pdf"))
    writer = PdfWriter()
    for page in handbook.pages[349:500]:
        writer.add_page(page)
    writer.add_metadata({"/Title": "SRMIST Engineering Faculty Directory, Handbook 2025-26", "/Subject": "Extracted faculty and staff section from the official SRMIST engineering handbook"})
    with (PROCESSED / "srmist_engineering_faculty_directory_2025_26.pdf").open("wb") as handle:
        writer.write(handle)

    # Keep official original curriculum PDFs alongside the extracted semester Markdown.
    curriculum = PdfReader(str(SOURCE_DIR / "srmist_btech_cse_curriculum_2026.pdf"))
    curriculum_writer = PdfWriter()
    for page in curriculum.pages:
        curriculum_writer.add_page(page)
    curriculum_writer.add_metadata({"/Title": "SRMIST B.Tech CSE-IT Curriculum, Regulations 2026", "/Subject": "Official semester curriculum source"})
    with (PROCESSED / "srmist_btech_cse_it_semester_curriculum_2026.pdf").open("wb") as handle:
        curriculum_writer.write(handle)


def main() -> None:
    STRUCTURED.mkdir(parents=True, exist_ok=True)
    (RAW / "aishe_2023_24_faculty_data.md").unlink(missing_ok=True)
    write_aishe_outputs()
    (RAW / "srmist_2025_26_faculty_directory_extracted.md").write_text(extract_faculty_text(), encoding="utf-8")
    faculty_records = extract_srm_faculty_csv()
    (RAW / "srmist_btech_cse_it_curriculum_2026_extracted.md").write_text(extract_srm_curriculum_text(), encoding="utf-8")
    semester_records = extract_srm_semester_csv()
    write_source_catalog()
    make_pdfs()
    print("Academic source extraction completed.")
    print(f"AISHE structured tables: {len(SHEETS)}")
    print(f"SRM faculty roster entries: {faculty_records}")
    print(f"SRM semester course/requirement rows: {semester_records}")
    print(f"SRM handbook source pages: {len(PdfReader(str(SOURCE_DIR / 'srmist_engineering_handbook_2025_26_faculty.pdf')).pages)}")
    print(f"Generated PDFs: {', '.join(p.name for p in PROCESSED.glob('*.pdf'))}")


if __name__ == "__main__":
    main()
