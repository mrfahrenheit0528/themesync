"""
ThemeSync — mail merge (notes §3.53)
=====================================
A CSV fills one content field or more (names, roles, any field it has a
column for), one layout per row:

  1. Step 1: the CSV's columns are matched to the target format's content
     fields by name ("Participant Name", "participant_name" and
     "{{Participant_Name}}" all match). Every row is checked against the
     same content schema as the form (p.47: present, a string, within
     max_characters); a row that fails is listed and left out.
  2. The designer edits one layout, in which each merged field shows a
     placeholder such as «Participant Name». The session keeps those
     fields out of text editing (OrchestrationSession.merge).
  3. Step 2's Download menu renders the finished layout once per row, with
     the row's words in the merged fields, as PNG or PDF files in a ZIP.
     Only the words change: the layout is solved once, and the renderer
     fits each row's text to its box as it does for typed text.
"""

import csv
import io
import os
import re
import unicodedata
import zipfile

from schema_validation import validate_content

import rasterize


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def read_csv(data: bytes) -> tuple:
    """(headers, rows) of a CSV file: UTF-8 (with or without Excel's BOM),
    else Windows-1252. Rows are dicts; blank rows are dropped."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("The file isn't UTF-8 or Windows-1252 text.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    rows = [{k: (v or "").strip() for k, v in row.items() if k is not None}
            for row in reader if any((v or "").strip() for k, v in row.items() if k is not None)]
    return headers, rows


def placeholder(label: str, max_chars: int = None) -> str:
    """«Participant Name», shortened when the field's limit is tighter."""
    text = f"«{label}»"
    if max_chars and len(text) > max_chars:
        text = f"«{label[:max(1, max_chars - 2)]}»"
    return text


# The fields that change from person to person: the template's columns
PERSON_FIELDS = ("Student_Name", "Certificate_ID", "Participant_Name", "Participant_Role")


def person_fields(fields: dict) -> dict:
    """The fields (content key → (label, max_characters)) that name the
    person a layout is for; every field when the format has none of
    them."""
    own = {k: v for k, v in fields.items() if k.strip("{}") in PERSON_FIELDS}
    return own or dict(fields)


def template(fields: dict) -> bytes:
    """A CSV with one column per text field, named by its label (content
    key → (label, max_characters)), to fill in one row per layout. UTF-8
    with Excel's BOM, so Excel opens accented names correctly."""
    buf = io.StringIO()
    csv.writer(buf).writerow([label for label, _ in fields.values()])
    return buf.getvalue().encode("utf-8-sig")


def build(data: bytes, fields: dict, base_content: dict, meta: dict, source: str) -> dict:
    """The merge for one CSV file.

    fields: content key → (label, max_characters) of the format's text
    fields. Returns {"source", "fields" [key...], "labels", "placeholders",
    "rows" [{key: value}], "invalid" [(row number, [errors])], "unmatched"
    [headers], "total"}; raises ValueError for a file with no usable
    column."""
    headers, rows = read_csv(data)
    # Keys first, then labels, so a label wins: "Signature Blocks 1" is the
    # first block (its key ends in _0).
    names = {_norm(key): key for key in fields}
    names.update({_norm(label): key for key, (label, _) in fields.items()})
    # A column blank in every row (the template's fields the designer left
    # alone) isn't merged: the form's value stands
    mapping = {h: names[_norm(h)] for h in headers
               if _norm(h) in names and any(row.get(h) for row in rows)}
    if not mapping and rows:
        wanted = ", ".join(label for label, _ in fields.values())
        raise ValueError(f"No filled column matches a content field. Name the columns after the fields "
                         f"(or start from the template): {wanted}.")
    if not rows:
        raise ValueError("The CSV has no data rows.")
    merged = list(dict.fromkeys(mapping.values()))
    out_rows, invalid = [], []
    for number, row in enumerate(rows, start=2):           # row 1 is the header
        values = {key: row.get(h, "") for h, key in mapping.items()}
        content = dict(base_content, **values)
        check = validate_content(content, meta)
        errors = [e for e in check["errors"] if any(key in e for key in merged)] if not check["valid"] else []
        if errors:
            invalid.append((number, errors))
        else:
            out_rows.append(values)
    return {
        "source": source, "fields": merged,
        "labels": {key: fields[key][0] for key in merged},
        "placeholders": {key: placeholder(*fields[key]) for key in merged},
        "rows": out_rows, "invalid": invalid, "total": len(rows),
        "unmatched": [h for h in headers if h not in mapping],
    }


def _file_stem(index: int, values: dict, fields: list) -> str:
    first = next((values[k] for k in fields if values.get(k)), "")
    ascii_name = unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode("ascii")   # Peña → Pena
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")[:40]
    return f"{index:03d}_{slug}" if slug else f"{index:03d}"


def zip_layouts(session, fmt: str = "png", progress=None) -> str:
    """Renders the session's current layout once per merge row (PNG at 2×
    or PDF) into a ZIP in the session's folder, and returns its path (a
    ZIP of PNGs can pass 100 MB, too much to hold in memory).
    progress(done, total) is called after each row."""
    merge = session.merge
    out_dir = os.path.join(session.output_dir, "mail_merge")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(session.output_dir, f"ThemeSync_{session.stem}_mail_merge_{fmt}.zip")
    rows = merge["rows"]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, values in enumerate(rows, start=1):
            stem = _file_stem(i, values, merge["fields"])
            svg = session.render_merged(values, os.path.join(out_dir, f"{stem}.svg"))
            path = rasterize.svg_to_pdf(svg) if fmt == "pdf" else rasterize.svg_to_png(svg, scale=2.0)
            zf.write(path, os.path.basename(path))
            os.remove(svg)
            os.remove(path)
            if progress:
                progress(i, len(rows))
    return zip_path
