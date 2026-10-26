from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "word"
SCREENSHOT_DIR = DOCS / "截图资产"

MATERIAL_DOC = OUT / "MICP软著材料汇编.docx"
CODE_DOC = OUT / "MICP关键源代码清单.docx"

MATERIAL_FILES = [
    DOCS / "软著材料清单.md",
    DOCS / "软件基础信息与功能说明.md",
    DOCS / "设计说明书.md",
    DOCS / "流程图.md",
    DOCS / "测试用例.md",
    DOCS / "部署说明.md",
    DOCS / "截图说明.md",
]

# 仅收录原创业务代码：算法包、接口层、数据层与前端逻辑；不含 README / 依赖清单 / 样式表
CODE_FILES = [
    ROOT / "backend" / "micp" / "__init__.py",
    ROOT / "backend" / "micp" / "schemas.py",
    ROOT / "backend" / "micp" / "mechanism.py",
    ROOT / "backend" / "micp" / "models.py",
    ROOT / "backend" / "micp" / "evaluation.py",
    ROOT / "backend" / "micp" / "sensitivity.py",
    ROOT / "backend" / "micp" / "optimizer.py",
    ROOT / "backend" / "micp" / "statistics.py",
    ROOT / "backend" / "micp" / "validators.py",
    ROOT / "backend" / "micp" / "synthetic.py",
    ROOT / "backend" / "micp" / "report.py",
    ROOT / "backend" / "db.py",
    ROOT / "backend" / "server.py",
    ROOT / "backend" / "ml.py",
    ROOT / "backend" / "wsgi.py",
    ROOT / "backend" / "bootstrap_admin.py",
    ROOT / "backend" / "static" / "app.js",
    ROOT / "backend" / "templates" / "index.html",
]


def set_east_asia_font(run, font_name: str) -> None:
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(table, top=80, start=120, bottom=80, end=120) -> None:
    tbl_pr = table._tbl.tblPr
    tbl_cell_mar = tbl_pr.first_child_found_in("w:tblCellMar")
    if tbl_cell_mar is None:
        tbl_cell_mar = OxmlElement("w:tblCellMar")
        tbl_pr.append(tbl_cell_mar)
    for margin, value in {
        "top": top,
        "start": start,
        "bottom": bottom,
        "end": end,
    }.items():
        node = tbl_cell_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tbl_cell_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_width(table, width_dxa: int = 9360) -> None:
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(width_dxa))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_layout = OxmlElement("w:tblLayout")
    tbl_layout.set(qn("w:type"), "fixed")
    tbl_pr.append(tbl_layout)


def style_document(doc: Document, title: str) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1

    for name, size, color, before, after in [
        ("Heading 1", 16, "2E74B5", 16, 8),
        ("Heading 2", 13, "2E74B5", 12, 6),
        ("Heading 3", 12, "1F4D78", 8, 4),
    ]:
        style = styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)

    if "Code" not in styles:
        code_style = styles.add_style("Code", 1)
    else:
        code_style = styles["Code"]
    code_style.font.name = "Courier New"
    code_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    code_style.font.size = Pt(8)
    code_style.paragraph_format.space_after = Pt(0)
    code_style.paragraph_format.line_spacing = 1.0

    header = section.header.paragraphs[0]
    header.text = title
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.runs[0].font.size = Pt(9)
    header.runs[0].font.color.rgb = RGBColor(100, 100, 100)
    set_east_asia_font(header.runs[0], "宋体")

    footer = section.footer.paragraphs[0]
    footer.text = "MICP 软件著作权登记材料"
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.runs[0].font.size = Pt(9)
    footer.runs[0].font.color.rgb = RGBColor(100, 100, 100)
    set_east_asia_font(footer.runs[0], "宋体")


def add_cover(doc: Document, title: str, subtitle: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(96)
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(24)
    run.font.color.rgb = RGBColor.from_string("0B2545")
    set_east_asia_font(run, "黑体")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(36)
    run = p.add_run(subtitle)
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor.from_string("555555")
    set_east_asia_font(run, "宋体")

    table = doc.add_table(rows=5, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    set_table_width(table, 7600)
    set_cell_margins(table)
    rows = [
        ("软件全称", "MICP-椰壳纤维协同固化砂土性能分析与预测系统"),
        ("软件简称", "MICP 固化砂土分析预测系统"),
        ("版本号", "V1.0"),
        ("材料类型", subtitle),
        ("整理日期", "2026-06-23"),
    ]
    for row, (label, value) in zip(table.rows, rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        row.cells[0].text = label
        row.cells[1].text = value
        set_cell_shading(row.cells[0], "F2F4F7")
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    set_east_asia_font(run, "宋体")
                    run.font.size = Pt(10.5)

    doc.add_page_break()


def add_markdown_table(doc: Document, lines: list[str], start: int) -> int:
    header = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    rows = []
    i = start + 2
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append([c.strip().replace("`", "") for c in lines[i].strip().strip("|").split("|")])
        i += 1

    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_width(table)
    set_cell_margins(table)
    for idx, text in enumerate(header):
        table.rows[0].cells[idx].text = text
        set_cell_shading(table.rows[0].cells[idx], "F2F4F7")
    for row in rows:
        cells = table.add_row().cells
        for idx in range(len(header)):
            cells[idx].text = row[idx] if idx < len(row) else ""
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                for run in para.runs:
                    set_east_asia_font(run, "宋体")
                    run.font.size = Pt(9)
    return i


def add_markdown_content(doc: Document, md_path: Path) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    in_code = False
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code:
            p = doc.add_paragraph(style="Code")
            p.add_run(raw)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|\s*-+", lines[i + 1].strip()):
            i = add_markdown_table(doc, lines, i)
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = min(len(heading.group(1)), 3)
            doc.add_heading(heading.group(2).replace("`", ""), level=level)
            i += 1
            continue
        bullet = re.match(r"^\s*-\s+(.*)$", line)
        if bullet:
            text = bullet.group(1).replace("`", "")
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(text)
            i += 1
            continue
        numbered = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if numbered:
            text = numbered.group(1).replace("`", "")
            p = doc.add_paragraph(style="List Number")
            p.add_run(text)
            i += 1
            continue
        p = doc.add_paragraph()
        p.add_run(line.replace("`", ""))
        i += 1


def add_screenshots(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("运行截图附件", level=1)
    for image in sorted(SCREENSHOT_DIR.glob("*.png")):
        caption = image.stem
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"图 {caption}")
        r.bold = True
        set_east_asia_font(r, "黑体")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(image), width=Cm(15.8))


def build_material_doc() -> None:
    doc = Document()
    style_document(doc, "MICP 软著材料汇编")
    add_cover(doc, "MICP 软著材料汇编", "说明文档与运行截图")
    for index, md in enumerate(MATERIAL_FILES):
        if index:
            doc.add_page_break()
        add_markdown_content(doc, md)
    add_screenshots(doc)
    doc.save(MATERIAL_DOC)


def add_code_listing(doc: Document, path: Path) -> None:
    rel = path.relative_to(ROOT)
    doc.add_heading(str(rel), level=1)
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for idx, line in enumerate(text, 1):
        p = doc.add_paragraph(style="Code")
        run = p.add_run(f"{idx:04d}  {line}")
        set_east_asia_font(run, "Consolas")


def build_code_doc() -> None:
    doc = Document()
    style_document(doc, "MICP 关键源代码清单")
    add_cover(doc, "MICP 关键源代码清单", "软件著作权源程序附件")
    doc.add_heading("源代码文件目录", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    set_table_width(table)
    set_cell_margins(table)
    headers = ["序号", "文件路径", "行数"]
    for idx, text in enumerate(headers):
        table.rows[0].cells[idx].text = text
        set_cell_shading(table.rows[0].cells[idx], "F2F4F7")
    for i, path in enumerate(CODE_FILES, 1):
        row = table.add_row().cells
        row[0].text = str(i)
        row[1].text = str(path.relative_to(ROOT))
        row[2].text = str(len(path.read_text(encoding="utf-8", errors="replace").splitlines()))
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                for run in para.runs:
                    set_east_asia_font(run, "宋体")
                    run.font.size = Pt(9)

    for path in CODE_FILES:
        doc.add_section(WD_SECTION.NEW_PAGE)
        add_code_listing(doc, path)
    doc.save(CODE_DOC)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_material_doc()
    build_code_doc()
    print(MATERIAL_DOC)
    print(CODE_DOC)


if __name__ == "__main__":
    main()
