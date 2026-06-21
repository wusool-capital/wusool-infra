#!/usr/bin/env python3
"""Convert the AWS R&D Word document to Markdown with embedded images."""

import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def extract_images(docx_path: str, images_dir: str) -> Dict[str, str]:
    """Extract embedded images and return rId -> relative markdown path."""
    os.makedirs(images_dir, exist_ok=True)
    image_map: Dict[str, str] = {}

    with zipfile.ZipFile(docx_path) as zf:
        rels_root = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
        rel_targets = {
            rel.get("Id"): rel.get("Target")
            for rel in rels_root.findall(f"{{{REL_NS}}}Relationship")
        }

        image_index = 0
        for rid, target in rel_targets.items():
            if not target or "media/" not in target.replace("\\", "/"):
                continue

            image_index += 1
            filename = os.path.basename(target)
            out_name = f"image-{image_index:02d}-{filename}"
            out_path = os.path.join(images_dir, out_name)

            media_path = f"word/{target.replace('media/', 'media/')}"
            if target.startswith("media/"):
                media_path = f"word/{target}"
            else:
                media_path = target.lstrip("/")

            try:
                data = zf.read(media_path)
            except KeyError:
                continue

            with open(out_path, "wb") as handle:
                handle.write(data)

            image_map[rid] = f"images/{out_name}"

        # Word stores a preview thumbnail separately from document media.
        try:
            thumb_data = zf.read("docProps/thumbnail.jpeg")
            thumb_path = os.path.join(images_dir, "document-thumbnail.jpeg")
            with open(thumb_path, "wb") as handle:
                handle.write(thumb_data)
            image_map["__thumbnail__"] = "images/document-thumbnail.jpeg"
        except KeyError:
            pass

    return image_map


def text_of(element: ET.Element) -> str:
    parts: List[str] = []
    if element.text:
        parts.append(element.text)

    for child in element:
        if child.tag == w("t"):
            if child.text:
                parts.append(child.text)
            if child.tail:
                parts.append(child.tail)
        elif child.tag == w("tab"):
            parts.append("    ")
        elif child.tag == w("br"):
            parts.append("\n")
        else:
            parts.append(text_of(child))
            if child.tail:
                parts.append(child.tail)

    return "".join(parts)


def run_is_bold(run: ET.Element) -> bool:
    rpr = run.find(w("rPr"))
    return rpr is not None and rpr.find(w("b")) is not None


def run_text(run: ET.Element) -> str:
    text = text_of(run)
    if not text:
        return ""
    if run_is_bold(run) and text.strip() and not text.strip().endswith(":"):
        return f"**{text}**"
    return text


def para_style(paragraph: ET.Element) -> Optional[str]:
    ppr = paragraph.find(w("pPr"))
    if ppr is None:
        return None
    style = ppr.find(w("pStyle"))
    if style is None:
        return None
    return style.get(w("val"))


def drawing_image_markdown(paragraph: ET.Element, image_map: Dict[str, str]) -> str:
    for blip in paragraph.iter(f"{{{A_NS}}}blip"):
        embed = blip.get(f"{{{R_NS}}}embed")
        if embed and embed in image_map:
            path = image_map[embed]
            return f"\n![Diagram]({path})\n\n"
    return ""


def convert_paragraph(paragraph: ET.Element, image_map: Dict[str, str]) -> str:
    image_md = drawing_image_markdown(paragraph, image_map)
    if image_md:
        return image_md

    style = para_style(paragraph)
    parts: List[str] = []
    for child in paragraph:
        if child.tag == w("r"):
            parts.append(run_text(child))
        elif child.tag == w("hyperlink"):
            parts.append(text_of(child))

    content = "".join(parts).strip()
    if not content:
        return ""

    if style == "Title":
        return f"# {content}\n\n"
    if style == "Heading1":
        return f"## {content}\n\n"
    if style == "Heading2":
        return f"### {content}\n\n"
    if style == "Heading3":
        return f"#### {content}\n\n"

    if content.startswith("- "):
        return f"{content}\n"
    if re.match(r"^[•]\s", content):
        return f"- {content.lstrip('•').strip()}\n"
    if re.match(r"^\d+\.\s", content):
        return f"{content}\n"

    return f"{content}\n\n"


def convert_table(table: ET.Element) -> str:
    rows: List[List[str]] = []
    for tr in table.findall(w("tr")):
        row: List[str] = []
        for tc in tr.findall(w("tc")):
            cell_parts = [text_of(p).strip() for p in tc.findall(w("p"))]
            row.append(" ".join(part for part in cell_parts if part))
        rows.append(row)

    if not rows:
        return ""

    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n\n"


def convert_docx(docx_path: str, output_path: str, images_dir: str) -> None:
    image_map = extract_images(docx_path, images_dir)

    with zipfile.ZipFile(docx_path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))

    body = root.find(w("body"))
    if body is None:
        raise ValueError("Document body not found")

    lines: List[str] = []
    for element in body:
        if element.tag == w("p"):
            lines.append(convert_paragraph(element, image_map))
        elif element.tag == w("tbl"):
            lines.append(convert_table(element))

    markdown = "".join(lines)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip() + "\n"

    # Prepend thumbnail only when no inline document images were embedded.
    embedded = [path for rid, path in image_map.items() if rid != "__thumbnail__"]
    if not embedded and "__thumbnail__" in image_map:
        thumb = image_map["__thumbnail__"]
        markdown = (
            f"![Document preview]({thumb})\n\n"
            f"> Preview thumbnail exported from the source Word document.\n\n"
            f"{markdown}"
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docx_path = os.path.join(
        repo_root, "DOCS", "AWS_Infrastructure_Design_and_RnD_Document_v2.docx"
    )
    output_path = os.path.join(
        repo_root, "docs", "aws-infrastructure-design-and-rnd.md"
    )
    images_dir = os.path.join(repo_root, "docs", "images")

    if not os.path.exists(docx_path):
        print(f"Missing source document: {docx_path}", file=sys.stderr)
        return 1

    convert_docx(docx_path, output_path, images_dir)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
