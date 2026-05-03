#!/usr/bin/env python3
"""Convert XLSX worksheets to CSV files without external dependencies."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _sheet_name_to_filename(name: str) -> str:
    safe = re.sub(r"[^\w\-\.]+", "_", name.strip())
    return safe or "sheet"


def _col_to_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0
    col = 0
    for char in match.group(1):
        col = col * 26 + (ord(char) - ord("A") + 1)
    return col - 1


def _read_shared_strings(zf: ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []

    root = ET.fromstring(zf.read(path))
    strings: list[str] = []
    for si in root.findall(_qn(NS_MAIN, "si")):
        text_parts = [node.text or "" for node in si.findall(f".//{_qn(NS_MAIN, 't')}")]
        strings.append("".join(text_parts))
    return strings


def _read_sheet_map(zf: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
        for rel in rels.findall(_qn(NS_REL, "Relationship"))
        if rel.attrib.get("Type", "").endswith("/worksheet")
    }

    sheets = workbook.find(_qn(NS_MAIN, "sheets"))
    if sheets is None:
        return []

    mapped: list[tuple[str, str]] = []
    for sheet in sheets.findall(_qn(NS_MAIN, "sheet")):
        name = sheet.attrib.get("name", "Sheet")
        rel_id = sheet.attrib.get(_qn(NS_OFFICE_REL, "id"))
        if not rel_id:
            continue
        target = rel_map.get(rel_id)
        if target:
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            mapped.append((name, target))
    return mapped


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find(_qn(NS_MAIN, "v"))
    inline_node = cell.find(f"{_qn(NS_MAIN, 'is')}/{_qn(NS_MAIN, 't')}")
    formula_node = cell.find(_qn(NS_MAIN, "f"))

    if cell_type == "inlineStr" and inline_node is not None:
        return inline_node.text or ""

    if value_node is None:
        if formula_node is not None and formula_node.text:
            return f"={formula_node.text}"
        return ""

    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _read_sheet_rows(zf: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    sheet_data = root.find(f"{_qn(NS_MAIN, 'sheetData')}")
    if sheet_data is None:
        return []

    rows: list[list[str]] = []
    for row in sheet_data.findall(_qn(NS_MAIN, "row")):
        cells = row.findall(_qn(NS_MAIN, "c"))
        if not cells:
            rows.append([])
            continue

        row_map: dict[int, str] = {}
        max_col = -1
        for cell in cells:
            ref = cell.attrib.get("r", "")
            col_idx = _col_to_index(ref) if ref else max_col + 1
            value = _cell_value(cell, shared_strings)
            row_map[col_idx] = value
            max_col = max(max_col, col_idx)

        row_values = [row_map.get(i, "") for i in range(max_col + 1)]
        rows.append(row_values)
    return rows


def convert_xlsx_to_csv(xlsx_path: Path, output_dir: Path, sheet_filter: str | None = None) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: list[Path] = []

    with ZipFile(xlsx_path) as zf:
        shared_strings = _read_shared_strings(zf)
        sheets = _read_sheet_map(zf)
        if sheet_filter:
            sheets = [entry for entry in sheets if entry[0] == sheet_filter]
            if not sheets:
                raise ValueError(f"Sheet '{sheet_filter}' not found in {xlsx_path.name}")

        for sheet_name, sheet_path in sheets:
            rows = _read_sheet_rows(zf, sheet_path, shared_strings)
            output_name = f"{xlsx_path.stem}__{_sheet_name_to_filename(sheet_name)}.csv"
            output_path = output_dir / output_name
            with output_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            written_files.append(output_path)

    return written_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert XLSX worksheets to CSV files.")
    parser.add_argument("xlsx", type=Path, help="Path to the .xlsx file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../ADTS"),
        help="Directory for output .csv files (default: current directory)",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Optional single sheet name to export. Defaults to all sheets.",
    )
    args = parser.parse_args()

    written = convert_xlsx_to_csv(args.xlsx, args.output_dir, args.sheet)
    for file_path in written:
        print(file_path)


if __name__ == "__main__":
    main()
