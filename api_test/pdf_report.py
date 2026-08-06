from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 46


def _pdf_text(value: Any) -> str:
    text = str("Not recorded" if value is None else value)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\r", " ").replace("\n", " ")


def _display_time(value: Any) -> str:
    if not value:
        return "Not recorded"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return str(value)


def _evidence_summary(evidence: dict[str, Any]) -> str:
    endpoints = " -> ".join(value for value in [evidence.get("source_ip"), evidence.get("destination_ip")] if value)
    parts = [
        _display_time(evidence.get("timestamp")),
        str(evidence.get("event_type") or "event"),
        endpoints,
        str(evidence.get("signature") or evidence.get("signature_id") or "No signature text"),
    ]
    return " | ".join(part for part in parts if part)


def _report_lines(report: dict[str, Any], metadata: dict[str, Any]) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = [
        ("title", "MAYAJAL ATTACK-CHAIN REPORT"),
        ("subtitle", "Authorized cyber-lab telemetry reconstruction"),
        ("space", ""),
        ("heading", "REPORT OVERVIEW"),
        ("body", f"Lab: {metadata.get('lab_name', 'Unknown lab')}"),
        ("body", f"Student: {metadata.get('student_name', 'Unknown student')}"),
        ("body", f"Session ID: {report.get('session_id', 'Unknown')}"),
        ("body", f"Session started: {_display_time(metadata.get('started_at'))}"),
        ("body", f"Session stopped: {_display_time(metadata.get('stopped_at'))}"),
        ("body", f"Report generated: {_display_time(report.get('generated_at'))}"),
        ("body", f"Telemetry events analyzed: {report.get('event_count', 0)}"),
        ("space", ""),
        ("heading", "EXECUTIVE SUMMARY"),
        ("body", str(report.get("summary") or "No summary is available.")),
        ("space", ""),
        ("heading", "ATT&CK CHAIN"),
    ]
    phases = report.get("attack_chain") or []
    if not phases:
        lines.append(("body", "No ATT&CK phases were reconstructed from the available telemetry."))
    for index, phase in enumerate(phases, start=1):
        lines.extend([
            ("phase", f"{index}. {phase.get('tactic', 'Unmapped')}  |  {phase.get('technique_id', 'UNMAPPED')}  |  {phase.get('technique', 'Needs review')}"),
            ("body", f"Observed events: {phase.get('event_count', 0)}"),
            ("body", f"Assessment: {phase.get('rationale', 'No rationale recorded.')}"),
            ("label", "Evidence samples"),
        ])
        evidence = phase.get("evidence") or []
        if evidence:
            lines.extend(("evidence", f"- {_evidence_summary(item)}") for item in evidence)
        else:
            lines.append(("evidence", "- No evidence sample was retained for this phase."))
        lines.append(("space", ""))
    lines.extend([
        ("heading", "ANALYST NOTES"),
        ("body", "This report is an automated reconstruction from lab telemetry. ATT&CK mappings indicate observed behavior and should be reviewed alongside the original events before drawing operational conclusions."),
    ])
    return lines


def render_attack_report_pdf(report: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    styles = {
        "title": (18, 24, "F2", 46),
        "subtitle": (10, 20, "F1", 70),
        "heading": (11, 22, "F2", 82),
        "phase": (10, 18, "F2", 76),
        "label": (9, 15, "F2", 88),
        "body": (9, 14, "F1", 92),
        "evidence": (8, 12, "F1", 108),
        "space": (6, 10, "F1", 1),
    }
    pages: list[list[str]] = [[]]
    y = PAGE_HEIGHT - MARGIN

    def new_page() -> None:
        nonlocal y
        pages.append([])
        y = PAGE_HEIGHT - MARGIN

    for style, value in _report_lines(report, metadata):
        size, leading, font, width = styles[style]
        wrapped = [""] if style == "space" else textwrap.wrap(str(value), width=width, break_long_words=True, break_on_hyphens=False) or [""]
        required = leading * len(wrapped)
        if y - required < 54:
            new_page()
        for line in wrapped:
            pages[-1].append(f"BT /{font} {size} Tf {MARGIN} {y} Td ({_pdf_text(line)}) Tj ET")
            y -= leading

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_object_numbers = [5 + index * 2 for index in range(len(pages))]
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for page_index, commands in enumerate(pages, start=1):
        footer = f"BT /F1 8 Tf {MARGIN} 28 Td (Mayajal internal report | Page {page_index} of {len(pages)}) Tj ET"
        stream = ("\n".join(commands + [footer]) + "\n").encode("latin-1", errors="replace")
        content_number = page_object_numbers[page_index - 1] + 1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_number} 0 R >>".encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)
