"""
backend/services/report_service.py

Report Service.

Generates a PDF attendance/attention report via reportlab — this was a
declared dependency (reportlab==4.2.2 in requirements.txt) with no actual
code using it anywhere in the project; this module is the real
implementation, not a stub.

The report covers a date range and includes: attendance totals per
student, class-wide attendance rate, and current attention analytics
(pulled from the live ClassroomPipeline class summary, since attention
history is a live/session concept rather than a stored-per-date one in
this build — see the docstring on `generate_attendance_report` for the
exact scope, so the PDF's contents are never a surprise relative to what
it claims to show).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

logger = logging.getLogger("smart_classroom.report_service")

_REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports_output"


class ReportServiceError(Exception):
    pass


class ReportService:
    def __init__(self, attendance_manager, firebase_service=None, pipeline=None):
        self._attendance_manager = attendance_manager
        self._firebase = firebase_service
        self._pipeline = pipeline
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def generate_attendance_report(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Builds a PDF covering [start_date, end_date] (inclusive, both
        YYYY-MM-DD). Defaults to the last 7 days if not given.

        Data sources, explicitly:
          - Attendance totals: Firestore if configured (real date-range
            query), otherwise only today's in-memory attendance is
            available and the PDF says so rather than fabricating history
            for dates the backend was never running to observe.
          - Attention snapshot: the live class summary at generation time
            (not a historical attention series — attention history is
            per-session/live in this build).
        """
        end_date = end_date or date.today().isoformat()
        start_date = start_date or (date.today() - timedelta(days=7)).isoformat()
        if start_date > end_date:
            raise ReportServiceError("'start_date' must not be after 'end_date'")

        attendance_records, data_note = self._gather_attendance(start_date, end_date)
        per_student = self._aggregate_per_student(attendance_records)
        class_summary = self._pipeline.get_class_summary() if self._pipeline else None

        buffer = BytesIO()
        self._render_pdf(buffer, start_date, end_date, per_student, class_summary, data_note)
        buffer.seek(0)

        filename = f"attendance_report_{start_date}_to_{end_date}.pdf"
        out_path = _REPORTS_DIR / filename
        with open(out_path, "wb") as f:
            f.write(buffer.getvalue())

        logger.info(
            "Generated report %s covering %d attendance record(s) across %d student(s)",
            filename, len(attendance_records), len(per_student),
        )
        return {"filename": filename, "path": str(out_path), "student_count": len(per_student)}

    # ------------------------------------------------------------------
    def _gather_attendance(self, start_date: str, end_date: str):
        if self._firebase is not None:
            try:
                records = self._firebase.get_attendance_range(start_date, end_date)
                return records, "Firestore attendance history for the selected range."
            except Exception:
                logger.exception("Firestore read failed while generating report")
        # Fallback: only today's in-memory data is available.
        today = date.today().isoformat()
        if start_date <= today <= end_date:
            records = [
                {
                    "student_id": r.student_id, "name": r.name, "roll_number": r.roll_number,
                    "date": r.date, "status": r.status,
                }
                for r in self._attendance_manager.get_today_records()
            ]
            note = (
                "Firestore unavailable — showing only today's in-memory attendance; "
                "earlier dates in the requested range are not available without "
                "a configured database."
            )
        else:
            records = []
            note = (
                "Firestore unavailable and the requested range does not include "
                "today, so no attendance data could be retrieved."
            )
        return records, note

    def _aggregate_per_student(self, records: List[Dict]) -> List[Dict[str, Any]]:
        by_student: Dict[str, Dict[str, Any]] = {}
        for r in records:
            sid = r.get("student_id")
            if not sid:
                continue
            entry = by_student.setdefault(
                sid, {"name": r.get("name", "Unknown"), "roll_number": r.get("roll_number", "-"),
                      "present_days": 0, "absent_days": 0}
            )
            if r.get("status") == "present":
                entry["present_days"] += 1
            elif r.get("status") == "absent":
                entry["absent_days"] += 1

        results = []
        for entry in by_student.values():
            total = entry["present_days"] + entry["absent_days"]
            rate = (entry["present_days"] / total * 100) if total > 0 else 0.0
            results.append({**entry, "attendance_rate": round(rate, 1)})
        results.sort(key=lambda e: e["name"])
        return results

    def _render_pdf(self, buffer, start_date, end_date, per_student, class_summary, data_note):
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=4,
        )
        note_style = ParagraphStyle(
            "Note", parent=styles["Italic"], fontSize=9, textColor=colors.HexColor("#666666"),
        )

        elements = [
            Paragraph("Smart Classroom — Attendance Report", title_style),
            Paragraph(f"Period: {start_date} to {end_date}", styles["Normal"]),
            Spacer(1, 6),
            Paragraph(data_note, note_style),
            Spacer(1, 16),
        ]

        if class_summary:
            elements.append(Paragraph("Current Attention Snapshot", styles["Heading2"]))
            summary_data = [
                ["Metric", "Value"],
                ["Average Attention", f"{class_summary.get('avg_attention', 0)}%"],
                ["Low Attention Count", str(class_summary.get("low_attention_count", 0))],
                ["Sleeping Count", str(class_summary.get("sleeping_count", 0))],
                ["Yawning Count", str(class_summary.get("yawning_count", 0))],
            ]
            elements.append(self._styled_table(summary_data, [3 * inch, 2 * inch]))
            elements.append(Spacer(1, 16))

        elements.append(Paragraph("Attendance by Student", styles["Heading2"]))
        if per_student:
            table_data = [["Name", "Roll No.", "Present", "Absent", "Rate"]]
            for s in per_student:
                table_data.append([
                    s["name"], s["roll_number"], str(s["present_days"]),
                    str(s["absent_days"]), f"{s['attendance_rate']}%",
                ])
            elements.append(self._styled_table(
                table_data, [2 * inch, 1.3 * inch, 1 * inch, 1 * inch, 1 * inch]
            ))
        else:
            elements.append(Paragraph("No attendance records available for this period.", styles["Normal"]))

        doc.build(elements)

    @staticmethod
    def _styled_table(data: List[List[str]], col_widths: List[float]) -> Table:
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6D5EF5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5FA")]),
        ]))
        return table
