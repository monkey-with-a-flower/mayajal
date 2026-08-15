from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api_test import config
from api_test.models import LabSession, LabSubmission


_templates = Environment(
    loader=FileSystemLoader(config.ASSETS_DIR),
    autoescape=select_autoescape(("html", "xml", "j2")),
)


def _display_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _duration(session: LabSession) -> str:
    end = session.stopped_at or datetime.now(timezone.utc)
    start = session.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    minutes = max(0, int((end - start).total_seconds() // 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _grade_letter(percentage: float) -> str:
    if percentage >= 85:
        return "HD"
    if percentage >= 75:
        return "D"
    if percentage >= 65:
        return "C"
    if percentage >= 50:
        return "P"
    return "F"


def _professional_context(session: LabSession, report: dict[str, Any], generated_by: str) -> dict[str, Any]:
    phases = []
    for phase in report["attack_chain"]:
        phases.append({
            **phase,
            "technique_name": phase["technique"],
            "evidence": [{
                **evidence,
                "src_ip": evidence.get("source_ip"),
                "dst_ip": evidence.get("destination_ip"),
                "sid": evidence.get("signature_id"),
            } for evidence in phase["evidence"]],
        })
    unmapped = sum(phase["event_count"] for phase in phases if phase["tactic"] == "Unmapped")
    return {
        "report_title": "Professional Security Report",
        "platform_name": "Mayajal",
        "classification": "Authorized Lab Use",
        "session_id": session.id,
        "report_id": f"MAYA-{session.id[:8].upper()}",
        "generated_at": report["generated_at"],
        "generated_by": generated_by,
        "detection_engine_mode": config.MAYAJAL_DETECTION_ENGINE_MODE,
        "lab_name": session.lab.name,
        "lab_id": session.lab.id,
        "project_id": f"{session.lab.id}-{session.student_id}",
        "student_name": session.student.name,
        "session_status": session.status.value.title(),
        "start_time": _display_time(session.started_at),
        "end_time": _display_time(session.stopped_at),
        "duration": _duration(session),
        "machine_count": len(session.lab.machines),
        "total_events": report["telemetry_event_count"],
        "mapped_events": report["event_count"] - unmapped,
        "unmapped_events": unmapped,
        "phases": phases,
        "executive_summary": report["summary"],
        "bundle_digest": session.detection_bundle_digest,
        "opensearch_index": config.MAYAJAL_OPENSEARCH_INDEX,
        "analyst_notes": "Only explicit IDS alerts and structured application detections are included as findings. Untriggered phases are not inferred.",
    }


def _academic_context(session: LabSession, submission: LabSubmission | None) -> dict[str, Any]:
    score = (submission.final_score if submission and submission.final_score is not None else submission.auto_score if submission else 0)
    maximum = submission.max_score if submission else sum(task.points for task in session.lab.tasks)
    percentage = round(score * 100 / maximum, 1) if maximum else 0
    result_by_task = {item.get("task_id"): item for item in (submission.results or [])} if submission else {}
    tasks = []
    for task in session.lab.tasks:
        result = result_by_task.get(task.id, {})
        reviewed = task.grading_type == "manual" or not submission
        correct = bool(result.get("correct"))
        tasks.append({
            "position": task.position + 1,
            "prompt": task.prompt,
            "grading_type": task.grading_type,
            "points_awarded": result.get("awarded_points", 0),
            "points_possible": task.points,
            "status": "Pending review" if reviewed else "Correct" if correct else "Incorrect",
            "status_class": "review" if reviewed else "correct" if correct else "incorrect",
            "feedback": "Instructor review required" if reviewed else "Automatically graded",
        })
    completed = sum(1 for task in tasks if task["status"] == "Correct")
    return {
        "report_title": "Academic Lab Performance Report",
        "platform_name": "Mayajal",
        "institution_name": "Mayajal Cyber Range",
        "student_name": session.student.name,
        "student_id": session.student.id,
        "lab_name": session.lab.name,
        "teacher_name": session.lab.owner.name,
        "date_completed": _display_time(session.stopped_at or session.started_at),
        "submission_status": (submission.status.replace("_", " ").title() if submission else "Not submitted"),
        "grade_letter": _grade_letter(percentage) if submission else "—",
        "total_score": score,
        "max_score": maximum,
        "percentage": percentage,
        "learning_objectives": [task.prompt for task in session.lab.tasks],
        "lab_description": session.lab.description,
        "machine_count": len(session.lab.machines),
        "duration": _duration(session),
        "attempt_count": 1,
        "tasks_completed": completed,
        "tasks": tasks,
        "teacher_feedback": submission.feedback if submission else None,
        "generated_at": _display_time(datetime.now(timezone.utc)),
    }


def render_report_html(
    report_type: str,
    session: LabSession,
    report: dict[str, Any],
    submission: LabSubmission | None,
    generated_by: str,
) -> str:
    if report_type == "academic":
        template = _templates.get_template("academic_report_template.html.j2")
        context = _academic_context(session, submission)
    else:
        template = _templates.get_template("attack_report_template.html.j2")
        context = _professional_context(session, report, generated_by)
    return template.render(**context)
