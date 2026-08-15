from pathlib import Path
from types import SimpleNamespace

import pytest

from api_test.detection_packs import DetectionPackError, build_detection_bundle, bundle_registry, resolve_detection_packs
from api_test.telemetry import build_attack_report


def machine(**overrides):
    values = {
        "id": "machine-1",
        "name": "DVWA",
        "image_url": "vulnerables/web-dvwa",
        "os_type": "Linux",
        "description": "Web target with authentication",
        "ports": ["8080:80"],
        "detection_profile": None,
        "build_context": None,
        "detection_rules": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_resolver_selects_profiles_without_machine_manifest_changes():
    packs = resolve_detection_packs([machine(), machine(id="attacker", name="Kali", image_url="kalilinux/kali", description="Pentest workstation")])
    selected = {pack.id: pack.reason for pack in packs}
    assert set(selected) == {"baseline", "credential-attacks", "reconnaissance", "web"}
    assert selected["web"] == "A selected machine exposes a web service"


def test_bundle_is_content_addressed_and_reproducible(tmp_path: Path):
    first = build_detection_bundle([machine()], bundle_root=tmp_path)
    second = build_detection_bundle([machine()], bundle_root=tmp_path)
    assert first == second
    assert (tmp_path / first["digest"] / "registry.json").is_file()
    assert first["rule_files"]
    assert bundle_registry(first["digest"], tmp_path)["9100101"]["technique_id"] == "T1190"


def test_bundle_rejects_machine_sid_collision(tmp_path: Path):
    context = tmp_path / "machine"
    rule_dir = context / "detections" / "network"
    rule_dir.mkdir(parents=True)
    (rule_dir / "collision.rules").write_text('alert tcp any any -> any any (msg:"collision"; sid:9100101; rev:1;)')
    target = machine(build_context=str(context), detection_rules={"suricata": ["detections/network/collision.rules"]})
    with pytest.raises(DetectionPackError, match="Duplicate Suricata SID 9100101"):
        build_detection_bundle([target], bundle_root=tmp_path / "bundles")


def test_pack_mode_maps_known_sid_and_does_not_guess_from_dns():
    events = [
        {"event_type": "alert", "alert": {"signature_id": 9100001, "signature": "anything"}},
        {"event_type": "dns", "dns": {"query": "example.test"}},
    ]
    report = build_attack_report("session", events, mode="packs")
    phases = {phase["tactic"]: phase for phase in report["attack_chain"]}
    assert phases["Reconnaissance"]["technique_id"] == "T1595"
    assert "Unmapped" not in phases
    assert report["telemetry_event_count"] == 2
    assert report["event_count"] == 1


def test_shadow_mode_prefers_registered_sid_over_legacy_keywords():
    report = build_attack_report(
        "session",
        [{"event_type": "alert", "alert": {"signature_id": 9001001, "signature": "Brute Force Attempt"}, "http": {"user_agent": "curl"}}],
        detection_registry={"9001001": {
            "tactic": "Credential Access",
            "technique_id": "T1110",
            "technique": "Brute Force",
            "rationale": "Machine-specific authentication detection.",
        }},
        mode="shadow",
    )
    assert report["attack_chain"][0]["tactic"] == "Credential Access"
    assert report["attack_chain"][0]["technique_id"] == "T1110"


def test_unregistered_alert_fallback_uses_signature_not_http_metadata():
    report = build_attack_report(
        "session",
        [{"event_type": "alert", "alert": {"signature_id": 9001001, "signature": "Brute Force Attempt"}, "http": {"user_agent": "curl"}}],
        detection_registry={},
        mode="shadow",
    )
    assert report["attack_chain"][0]["tactic"] == "Credential Access"


def test_raw_protocol_telemetry_is_not_reported_as_a_detection():
    report = build_attack_report("session", [{"event_type": "dns", "dns": {"query": "example.test"}}], mode="legacy")
    assert report["event_count"] == 0
    assert report["telemetry_event_count"] == 1
    assert report["attack_chain"] == []


def test_stdout_url_does_not_create_a_discovery_phase():
    report = build_attack_report("session", [{"source": "stdout", "log": "Running on http://127.0.0.1:8080"}], mode="shadow")
    assert report["event_count"] == 0
    assert report["attack_chain"] == []
