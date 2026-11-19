"""Office Open XML renderers: DOCX, XLSX and PPTX.

Files are ordinary macro-free ZIP packages containing OOXML parts.  No Office
installation, template or third-party library is required.  Entity locations
are recorded while the XML is written.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from ..docmodel import Block, Cell, Doc
from .base import EXTRACTION_METHODS, MIME_TYPES, RenderedFile

FIXED_DATE = "2026-01-01T00:00:00Z"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def _zip(files: Dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, files[name])
    return buffer.getvalue()


def _x(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _core_props(title: str, subject: str, author: str = "Privacy Gateway Testgen") -> bytes:
    xml = (
        f'{XML_HEAD}<cp:coreProperties xmlns:cp="{CP_NS}" xmlns:dc="{DC_NS}" '
        f'xmlns:dcterms="{DCTERMS_NS}" xmlns:xsi="{XSI_NS}">'
        f"<dc:title>{_x(title)}</dc:title><dc:subject>{_x(subject)}</dc:subject>"
        f"<dc:creator>{_x(author)}</dc:creator><cp:lastModifiedBy>{_x(author)}</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{FIXED_DATE}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{FIXED_DATE}</dcterms:modified>'
        "</cp:coreProperties>"
    )
    return xml.encode("utf-8")


def _app_props(application: str, company: str = "Synthetic Example Organisation") -> bytes:
    xml = (
        f'{XML_HEAD}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        f"<Application>{_x(application)}</Application><Company>{_x(company)}</Company>"
        "<DocSecurity>0</DocSecurity></Properties>"
    )
    return xml.encode("utf-8")


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------


def _w_run(text: str, bold: bool = False, mono: bool = False) -> str:
    props = ""
    if bold:
        props += "<w:b/>"
    if mono:
        props += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
    return f'<w:r>{"<w:rPr>" + props + "</w:rPr>" if props else ""}<w:t xml:space="preserve">{_x(text)}</w:t></w:r>'


def _w_paragraph(text: str, style: Optional[str] = None, bold: bool = False, mono: bool = False) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{_w_run(text, bold=bold, mono=mono)}</w:p>"


def _w_table(block: Block) -> str:
    columns = max(1, len(block.headers))
    grid = "".join('<w:gridCol w:w="2400"/>' for _ in range(columns))
    rows: List[str] = []
    if block.headers:
        cells = "".join(f"<w:tc><w:tcPr><w:tcW w:w=\"2400\" w:type=\"dxa\"/></w:tcPr>{_w_paragraph(h, bold=True)}</w:tc>"
                        for h in block.headers)
        rows.append(f"<w:tr>{cells}</w:tr>")
    for row in block.rows:
        cells = "".join(
            f"<w:tc><w:tcPr><w:tcW w:w=\"2400\" w:type=\"dxa\"/></w:tcPr>{_w_paragraph(cell.text)}</w:tc>"
            for cell in row
        )
        rows.append(f"<w:tr>{cells}</w:tr>")
    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(rows)}</w:tbl>"
    )


def _docx_styles() -> bytes:
    xml = (
        f'{XML_HEAD}<w:styles xmlns:w="{W_NS}">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
        '<w:basedOn w:val="Normal"/></w:style>'
        '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>'
        '<w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        "</w:tblBorders></w:tblPr></w:style></w:styles>"
    )
    return xml.encode("utf-8")


def _docx_header_footer(cell: Optional[Cell], tag: str) -> bytes:
    paragraph = _w_paragraph(cell.text if cell else "")
    xml = (
        f'{XML_HEAD}<w:{tag} xmlns:w="{W_NS}" xmlns:r="{R_NS}"><w:p>'
        f"<w:pPr><w:pStyle w:val=\"Normal\"/></w:pPr>"
        f'{_w_run(cell.text if cell else "")}</w:p></w:{tag}>'
    )
    return xml.encode("utf-8")


def _docx_relationships(header: bool, footer: bool, links: Sequence[Tuple[str, str]]) -> bytes:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
    ]
    index = 2
    if header:
        rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>')
        index += 1
    if footer:
        rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>')
        index += 1
    for text, url in links:
        rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{_x(url)}" TargetMode="External"/>')
        index += 1
    return (f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{"".join(rels)}</Relationships>').encode("utf-8")


def _render_docx(doc: Doc, filename: str) -> RenderedFile:
    header = doc.metadata.get("header")
    footer = doc.metadata.get("footer")
    links = list(doc.metadata.get("hyperlinks", []))
    body: List[str] = []
    locations: List[dict] = []
    paragraph_index = 0
    table_index = 0

    for block in doc.blocks:
        if block.kind == "heading":
            body.append(_w_paragraph(block.text, style="Heading1"))
            paragraph_index += 1
        elif block.kind in ("paragraph", "note"):
            body.append(_w_paragraph(block.text))
            for placement in block.placements:
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "docx_paragraph", "paragraph": paragraph_index,
                        "character_start": placement.start, "character_end": placement.end,
                    },
                    "role": placement.role,
                })
            paragraph_index += 1
        elif block.kind == "bullet":
            body.append(_w_paragraph("• " + block.text, style="ListParagraph"))
            for placement in block.placements:
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "docx_paragraph", "paragraph": paragraph_index,
                        "character_start": placement.start + 2, "character_end": placement.end + 2,
                    },
                    "role": placement.role,
                })
            paragraph_index += 1
        elif block.kind in ("code", "log"):
            for line in block.text.splitlines():
                body.append(_w_paragraph(line, style="Code"))
                paragraph_index += 1
            for placement in block.placements:
                line_number = block.text.count("\n", 0, placement.start)
                line_start = block.text.rfind("\n", 0, placement.start) + 1
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "docx_paragraph", "paragraph": paragraph_index - (block.text.count("\n") - line_number),
                        "character_start": placement.start - line_start,
                        "character_end": placement.end - line_start,
                    },
                    "role": placement.role,
                })
        elif block.kind == "table":
            body.append(_w_table(block))
            table_index += 1
            for row_number, row in enumerate(block.rows, start=1):
                for column_number, value in enumerate(row, start=1):
                    for placement in value.placements:
                        locations.append({
                            "entity": placement.entity,
                            "location": {
                                "kind": "docx_table_cell", "table": table_index,
                                "row": row_number + 1, "column": column_number,
                            },
                            "role": placement.role,
                        })
    if links:
        for text, url in links:
            # Links use safe example domains and carry no entity ground truth.
            body.append(_w_paragraph(text))
            paragraph_index += 1

    header_xml = _docx_header_footer(header, "hdr") if header else None
    footer_xml = _docx_header_footer(footer, "ftr") if footer else None
    sect = '<w:sectPr>'
    if header_xml:
        sect += '<w:headerReference w:type="default" r:id="rId2"/>'
    if footer_xml:
        sect += f'<w:footerReference w:type="default" r:id="{"rId3" if header_xml else "rId2"}"/>'
    sect += '<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
    document = (
        f'{XML_HEAD}<w:document xmlns:w="{W_NS}" xmlns:r="{R_NS}"><w:body>'
        f'{"".join(body)}{sect}</w:body></w:document>'
    ).encode("utf-8")

    overrides = [
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    if header_xml:
        overrides.append('<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>')
    if footer_xml:
        overrides.append('<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>')
    content_types = (
        f'{XML_HEAD}<Types xmlns="{CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'{"".join(overrides)}</Types>'
    ).encode("utf-8")

    root_rels = (
        f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    ).encode("utf-8")

    files = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "word/document.xml": document,
        "word/styles.xml": _docx_styles(),
        "word/_rels/document.xml.rels": _docx_relationships(bool(header_xml), bool(footer_xml), links),
        "docProps/core.xml": _core_props(doc.title, "Synthetic business document"),
        "docProps/app.xml": _app_props("privacy-gateway-testgen DOCX renderer"),
    }
    if header_xml:
        files["word/header1.xml"] = header_xml
        for placement in header.placements:
            locations.append({
                "entity": placement.entity,
                "location": {"kind": "docx_header", "character_start": placement.start, "character_end": placement.end},
                "role": placement.role,
            })
    if footer_xml:
        files["word/footer1.xml"] = footer_xml
        for placement in footer.placements:
            locations.append({
                "entity": placement.entity,
                "location": {"kind": "docx_footer", "character_start": placement.start, "character_end": placement.end},
                "role": placement.role,
            })
    data = _zip(files)
    return RenderedFile(filename, data, MIME_TYPES["docx"], "docx",
                        EXTRACTION_METHODS["docx"], locations,
                        {"parts": sorted(files), "paragraph_count": paragraph_index, "table_count": table_index})


# --------------------------------------------------------------------------
# XLSX
# --------------------------------------------------------------------------


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_sheet(block: Block, hidden: bool = False) -> bytes:
    rows: List[str] = []
    all_rows = [block.headers] + [[cell.text for cell in row] for row in block.rows]
    for row_index, row in enumerate(all_rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{_column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_x(str(value))}</t></is></c>'
            )
        rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    xml = (
        f'{XML_HEAD}<worksheet xmlns="{W_NS.replace("wordprocessingml", "spreadsheetml")}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheetData>{"".join(rows)}</sheetData></worksheet>'
    )
    return xml.encode("utf-8")


def _xlsx_styles() -> bytes:
    xml = (
        f'{XML_HEAD}<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )
    return xml.encode("utf-8")


def _render_xlsx(doc: Doc, filename: str) -> RenderedFile:
    tables = [block for block in doc.blocks if block.kind == "table"]
    if not tables:
        # Derive one table from a record or flat document.
        record = doc.record or {}
        if isinstance(record, dict):
            headers = ["key", "value"]
            rows = [[key, value if isinstance(value, Cell) else Cell(str(value))] for key, value in record.items()]
            tables = [Block("table", headers=headers, rows=rows, title="Data")]
        else:
            tables = [Block("table", headers=["value"], rows=[[Cell(str(record))]], title="Data")]
    hidden_names = set(doc.metadata.get("hidden_sheets", []))
    sheet_names = []
    used = set()
    for index, block in enumerate(tables, start=1):
        base = re.sub(r"[^A-Za-z0-9 _-]", "", block.title or f"Sheet{index}")[:31] or f"Sheet{index}"
        name = base
        suffix = 2
        while name in used:
            name = f"{base[:28]}_{suffix}"
            suffix += 1
        used.add(name)
        sheet_names.append((name, name in hidden_names))

    files: Dict[str, bytes] = {}
    locations: List[dict] = []
    overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    rels = []
    sheets_xml = []
    for index, (block, (name, hidden)) in enumerate(zip(tables, sheet_names), start=1):
        files[f"xl/worksheets/sheet{index}.xml"] = _xlsx_sheet(block)
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
        state = ' state="hidden"' if hidden else ""
        sheets_xml.append(f'<sheet name="{_x(name)}" sheetId="{index}"{state} r:id="rId{index}"/>')
        for row_index, row in enumerate(block.rows, start=2):
            for column_index, value in enumerate(row, start=1):
                for placement in value.placements:
                    locations.append({
                        "entity": placement.entity,
                        "location": {
                            "kind": "xlsx_cell", "sheet": name,
                            "cell": f"{_column_name(column_index)}{row_index}",
                            "row": row_index, "column": column_index,
                            "header": block.headers[column_index - 1] if column_index - 1 < len(block.headers) else "",
                            "hidden": hidden,
                        },
                        "role": placement.role,
                    })
    workbook = (
        f'{XML_HEAD}<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'xmlns:r="{R_NS}"><sheets>{"".join(sheets_xml)}</sheets></workbook>'
    ).encode("utf-8")
    relations = (
        f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{"".join(rels)}'
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    content_types = (
        f'{XML_HEAD}<Types xmlns="{CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'{"".join(overrides)}</Types>'
    ).encode("utf-8")
    root_rels = (
        f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    files.update({
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": relations,
        "xl/styles.xml": _xlsx_styles(),
        "docProps/core.xml": _core_props(doc.title, "Synthetic workbook"),
        "docProps/app.xml": _app_props("privacy-gateway-testgen XLSX renderer"),
    })
    data = _zip(files)
    return RenderedFile(filename, data, MIME_TYPES["xlsx"], "xlsx",
                        EXTRACTION_METHODS["xlsx"], locations,
                        {"sheets": [{"name": name, "hidden": hidden} for name, hidden in sheet_names]})


# --------------------------------------------------------------------------
# PPTX
# --------------------------------------------------------------------------


def _slide_texts(doc: Doc) -> List[Tuple[str, List[Tuple[str, Block]]]]:
    slides: List[Tuple[str, List[Tuple[str, Block]]]] = []
    if doc.slides:
        for slide in doc.slides:
            pieces = []
            for block in slide.blocks:
                if block.kind == "table":
                    lines = [" | ".join(block.headers)] + [" | ".join(c.text for c in row) for row in block.rows]
                    pieces.append((block.kind, Block("paragraph", text="\n".join(lines))))
                else:
                    pieces.append((block.kind, block))
            slides.append((slide.title, pieces))
    else:
        paragraphs = [block for block in doc.blocks if block.kind in ("paragraph", "note", "bullet", "code", "log")]
        chunk: List[Block] = []
        for block in paragraphs:
            chunk.append(block)
            if len(chunk) >= 4:
                slides.append((doc.title, [("paragraph", item) for item in chunk]))
                chunk = []
        if chunk:
            slides.append((doc.title, [("paragraph", item) for item in chunk]))
    return slides


def _pptx_text_shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int,
                     paragraphs: Sequence[Block], title: bool = False) -> Tuple[str, str]:
    runs = []
    for block in paragraphs:
        text = block.text if block.kind != "bullet" else "• " + block.text
        for line in text.split("\n"):
            runs.append(f'<a:p><a:r><a:rPr lang="en-US" dirty="0"/><a:t>{_x(line)}</a:t></a:r></a:p>')
    txbox = ' txBox="1"' if not title else ""
    shape = (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{_x(name)}"/>'
        f'<p:cNvSpPr{txbox}/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{"".join(runs)}</p:txBody></p:sp>'
    )
    return shape, "".join(run.split("<a:t>", 1)[1].split("</a:t>", 1)[0] for run in runs)


def _render_pptx(doc: Doc, filename: str) -> RenderedFile:
    slides = _slide_texts(doc)
    if not slides:
        slides = [(doc.title, [("paragraph", Block("paragraph", text=doc.title))])]
    files: Dict[str, bytes] = {}
    slide_entries = []
    presentation_rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>',
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
        '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
    ]
    locations: List[dict] = []
    for slide_index, (title, pieces) in enumerate(slides, start=1):
        rel_id = f"rId{5 + slide_index}"
        presentation_rels.append(
            f'<Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{slide_index}.xml"/>'
        )
        slide_entries.append(f'<p:sldId id="{255 + slide_index}" r:id="{rel_id}"/>')
        shapes = []
        title_shape, _ = _pptx_text_shape(2, "Title", 609600, 365760, 10972800, 914400, [Block("paragraph", text=title)], title=True)
        shapes.append(title_shape)
        body_y = 1371600
        shape_index = 2
        for block_index, (kind, block) in enumerate(pieces, start=1):
            if block.kind == "table":
                text = " | ".join(block.headers) + "\n" + "\n".join(" | ".join(c.text for c in row) for row in block.rows)
                text_block = Block("paragraph", text=text, placements=[])
                body_block = text_block
            else:
                body_block = block
            shape, _ = _pptx_text_shape(2 + block_index, f"Content {block_index}", 609600, body_y, 10972800, 1000000, [body_block])
            shapes.append(shape)
            shape_index = 1 + block_index
            body_y += 1050000
            for placement in block.placements:
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "pptx_shape", "slide": slide_index, "shape": shape_index,
                        "character_start": placement.start, "character_end": placement.end,
                    },
                    "role": placement.role,
                })
        slide_xml = (
            f'{XML_HEAD}<p:sld xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
            f'<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{"".join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        ).encode("utf-8")
        slide_rels = (
            f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            "</Relationships>"
        ).encode("utf-8")
        files[f"ppt/slides/slide{slide_index}.xml"] = slide_xml
        files[f"ppt/slides/_rels/slide{slide_index}.xml.rels"] = slide_rels

    presentation = (
        f'{XML_HEAD}<p:presentation xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f'<p:sldIdLst>{"".join(slide_entries)}</p:sldIdLst>'
        '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
        '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    ).encode("utf-8")
    theme = (
        f'{XML_HEAD}<a:theme xmlns:a="{A_NS}" name="Synthetic">'
        '<a:themeElements><a:clrScheme name="Synthetic">'
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F3F4F6"/></a:lt2>'
        '<a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="7C3AED"/></a:accent2>'
        '<a:accent3><a:srgbClr val="059669"/></a:accent3><a:accent4><a:srgbClr val="D97706"/></a:accent4>'
        '<a:accent5><a:srgbClr val="DC2626"/></a:accent5><a:accent6><a:srgbClr val="0891B2"/></a:accent6>'
        '<a:hlink><a:srgbClr val="1D4ED8"/></a:hlink><a:folHlink><a:srgbClr val="7E22CE"/></a:folHlink>'
        '</a:clrScheme><a:fontScheme name="Synthetic">'
        '<a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        '</a:fontScheme><a:fmtScheme name="Synthetic">'
        '<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="25400"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="38100"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
        '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
        '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
        '</a:fmtScheme></a:themeElements></a:theme>'
    ).encode("utf-8")
    master = (
        f'{XML_HEAD}<p:sldMaster xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
        '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        '</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'
    ).encode("utf-8")
    master_rels = (
        f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    layout = (
        f'{XML_HEAD}<p:sldLayout xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}" type="blank" preserve="1">'
        '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    ).encode("utf-8")
    layout_rels = (
        f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    slide_overrides = "".join(
        '<Override PartName="/ppt/slides/slide%d.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' % index
        for index in range(1, len(slides) + 1)
    )
    content_types = (
        f'{XML_HEAD}<Types xmlns="{CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
        '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
        '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f"{slide_overrides}"
        "</Types>"
    ).encode("utf-8")
    root_rels = (
        f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    files.update({
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": (
            f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{"".join(presentation_rels)}</Relationships>'
        ).encode("utf-8"),
        "ppt/slideMasters/slideMaster1.xml": master,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": master_rels,
        "ppt/slideLayouts/slideLayout1.xml": layout,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": layout_rels,
        "ppt/theme/theme1.xml": theme,
        "ppt/presProps.xml": f'{XML_HEAD}<p:presentationPr xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}"/>'.encode("utf-8"),
        "ppt/viewProps.xml": f'{XML_HEAD}<p:viewPr xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}"/>'.encode("utf-8"),
        "ppt/tableStyles.xml": f'{XML_HEAD}<a:tblStyleLst xmlns:a="{A_NS}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>'.encode("utf-8"),
        "docProps/core.xml": _core_props(doc.title, "Synthetic presentation"),
        "docProps/app.xml": _app_props("privacy-gateway-testgen PPTX renderer"),
    })
    data = _zip(files)
    return RenderedFile(filename, data, MIME_TYPES["pptx"], "pptx",
                        EXTRACTION_METHODS["pptx"], locations,
                        {"slides": len(slides), "notes": "not_emitted"})


def render_ooxml(doc: Doc, ext: str, filename: str) -> RenderedFile:
    if ext == "docx":
        return _render_docx(doc, filename)
    if ext == "xlsx":
        return _render_xlsx(doc, filename)
    if ext == "pptx":
        return _render_pptx(doc, filename)
    raise ValueError(f"not an OOXML format: {ext}")
