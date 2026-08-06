import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from api_test.config import MAYAJAL_OPENSEARCH_INDEX, MAYAJAL_OPENSEARCH_URL


def _opensearch_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = MAYAJAL_OPENSEARCH_URL.rstrip("/") + path
    data = json.dumps(payload).encode()
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace") or str(exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OpenSearch query failed: " + detail) from exc
    except (OSError, URLError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telemetry search is not available. Start the OpenSearch stack and try again.") from exc


def search_session_events(session_id: str, size: int = 200) -> list[dict[str, Any]]:
    query = {
        "size": size,
        "sort": [{"@timestamp": {"order": "asc", "unmapped_type": "date"}}],
        "query": {
            "bool": {
                "minimum_should_match": 1,
                "should": [
                    {"term": {"session_id.keyword": session_id}},
                    {"term": {"session_id": session_id}},
                    {"term": {"SESSIONID.keyword": session_id}},
                    {"term": {"SESSIONID": session_id}},
                    {"term": {"mayajal_session_id.keyword": session_id}},
                    {"term": {"mayajal_session_id": session_id}},
                    {"match_phrase": {"session_id": session_id}},
                    {"match_phrase": {"SESSIONID": session_id}},
                    {"match_phrase": {"mayajal_session_id": session_id}},
                ],
            }
        },
    }
    result = _opensearch_request("/" + MAYAJAL_OPENSEARCH_INDEX + "/_search", query)
    return [
        {"index": hit.get("_index"), "id": hit.get("_id"), "score": hit.get("_score"), **hit.get("_source", {})}
        for hit in result.get("hits", {}).get("hits", [])
    ]


def _event_text(event: dict[str, Any]) -> str:
    alert = event.get("alert") if isinstance(event.get("alert"), dict) else {}
    parts = [
        str(event.get("event_type", "")),
        str(alert.get("signature", "")),
        str(alert.get("category", "")),
        str(event.get("log", "")),
        str(event.get("message", "")),
        str(event.get("http", "")),
        str(event.get("dns", "")),
    ]
    return " ".join(parts).lower()


def _field_value(event: dict[str, Any], dotted_field: str) -> str:
    value: Any = event
    for part in dotted_field.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(part)
    return "" if value is None else str(value)


def apply_log_detection_rules(events: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for original in events:
        event = dict(original)
        event_source = " ".join(str(event.get(key, "")) for key in ("telemetry_source", "log_source", "tag", "source")).lower()
        for rule in rules:
            source = str(rule.get("source", "application"))
            if source == "application" and any(token in event_source for token in ("suricata", "system", "syslog", "journald")):
                continue
            if source == "system" and not any(token in event_source for token in ("system", "syslog", "journald", "audit")):
                continue
            if re.search(str(rule["pattern"]), _field_value(event, str(rule["field"])), flags=re.IGNORECASE):
                event["mayajal_detection"] = {
                    key: rule[key]
                    for key in ("id", "tactic", "technique_id", "technique", "rationale", "source", "rule_file")
                    if key in rule
                }
                break
        enriched.append(event)
    return enriched


def _classify_event(event: dict[str, Any]) -> tuple[str, str, str, str]:
    detection = event.get("mayajal_detection") if isinstance(event.get("mayajal_detection"), dict) else None
    if detection:
        return (
            str(detection["tactic"]),
            str(detection["technique_id"]),
            str(detection["technique"]),
            str(detection["rationale"]),
        )
    alert = event.get("alert") if isinstance(event.get("alert"), dict) else {}
    text = _event_text(event)
    if any(token in text for token in ["nmap", "masscan", "nikto", "gobuster", "dirb", "scan", "sweep", "probe"]):
        return ("Reconnaissance", "T1595", "Active Scanning", "Scanning or probing activity was observed.")
    if any(token in text for token in ["sql injection", "sqli", "xss", "traversal", "lfi", "rfi", "exploit", "shellshock", "web attack"]):
        return ("Initial Access", "T1190", "Exploit Public-Facing Application", "Exploit-like traffic targeted a lab service.")
    if any(token in text for token in ["cmd.exe", "powershell", "bash", "sh -c", "reverse shell", "webshell", "wget", "curl"]):
        return ("Execution", "T1059", "Command and Scripting Interpreter", "Command execution indicators were observed.")
    if any(token in text for token in ["password", "credential", "bruteforce", "brute force", "login failed", "ssh"]):
        return ("Credential Access", "T1110", "Brute Force", "Authentication or credential-oriented activity was observed.")
    if any(token in text for token in ["dns", "http", "tls", "flow"]):
        return ("Discovery", "T1046", "Network Service Discovery", "Network service or protocol activity was observed.")
    return ("Unmapped", "UNMAPPED", "Needs analyst review", "No confident ATT&CK mapping was inferred.")


def build_attack_report(session_id: str, events: list[dict[str, Any]], log_rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    events = apply_log_detection_rules(events, log_rules or [])
    phases: dict[str, dict[str, Any]] = {}
    for event in events:
        tactic, technique_id, technique, rationale = _classify_event(event)
        phase = phases.setdefault(
            tactic,
            {
                "tactic": tactic,
                "technique_id": technique_id,
                "technique": technique,
                "rationale": rationale,
                "event_count": 0,
                "evidence": [],
            },
        )
        phase["event_count"] += 1
        if len(phase["evidence"]) < 5:
            alert = event.get("alert") if isinstance(event.get("alert"), dict) else {}
            detection = event.get("mayajal_detection") if isinstance(event.get("mayajal_detection"), dict) else {}
            phase["evidence"].append(
                {
                    "timestamp": event.get("@timestamp") or event.get("timestamp"),
                    "source_ip": event.get("src_ip") or event.get("source_ip"),
                    "destination_ip": event.get("dest_ip") or event.get("destination_ip"),
                    "event_type": event.get("event_type") or event.get("telemetry_source"),
                    "signature_id": alert.get("signature_id") or alert.get("sid") or detection.get("id") or event.get("signature_id") or event.get("sid"),
                    "signature": alert.get("signature") or detection.get("id") or event.get("log") or event.get("message"),
                    "rule_file": detection.get("rule_file"),
                }
            )
    order = ["Reconnaissance", "Initial Access", "Execution", "Persistence", "Privilege Escalation", "Defense Evasion", "Credential Access", "Discovery", "Lateral Movement", "Command and Control", "Exfiltration", "Impact", "Unmapped"]
    ordered_phases = sorted(phases.values(), key=lambda item: order.index(item["tactic"]) if item["tactic"] in order else len(order))
    return {
        "session_id": session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "summary": "No telemetry events were found for this session." if not events else f"Reconstructed {len(ordered_phases)} ATT&CK phases from {len(events)} telemetry events.",
        "attack_chain": ordered_phases,
    }
