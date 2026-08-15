from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api_test.config import DETECTION_BUNDLES_DIR, DETECTION_PACKS_DIR


class DetectionPackError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedPack:
    id: str
    version: str
    reason: str
    directory: Path
    manifest: dict


def _machine_text(machine: object) -> str:
    values = [
        getattr(machine, "name", ""),
        getattr(machine, "image_url", ""),
        getattr(machine, "os_type", ""),
        getattr(machine, "description", ""),
        " ".join(getattr(machine, "ports", None) or []),
        getattr(machine, "detection_profile", "") or "",
    ]
    return " ".join(str(value) for value in values).lower()


def load_pack_catalogue(root: Path = DETECTION_PACKS_DIR) -> dict[str, tuple[Path, dict]]:
    catalogue: dict[str, tuple[Path, dict]] = {}
    if not root.is_dir():
        return catalogue
    for manifest_path in sorted(root.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pack_id = str(manifest.get("id", "")).strip()
        if not pack_id or pack_id in catalogue:
            raise DetectionPackError(f"Invalid or duplicate detection pack ID in {manifest_path}.")
        catalogue[pack_id] = (manifest_path.parent, manifest)
    return catalogue


def resolve_detection_packs(machines: Iterable[object], root: Path = DETECTION_PACKS_DIR) -> list[ResolvedPack]:
    catalogue = load_pack_catalogue(root)
    machine_texts = [_machine_text(machine) for machine in machines]
    selected: dict[str, str] = {
        "baseline": "Required by platform policy",
        "reconnaissance": "Common network reconnaissance coverage required by platform policy",
    }
    combined = " ".join(machine_texts)
    if re.search(r"http|https|web|dvwa|nginx|apache|wordpress|8080|:80\b", combined):
        selected["web"] = "A selected machine exposes a web service"
    if re.search(r"login|authentication|credential|ssh|rdp|active directory|domain controller", combined):
        selected["credential-attacks"] = "A selected machine exposes authentication services"
    resolved: list[ResolvedPack] = []
    for pack_id in sorted(selected):
        if pack_id not in catalogue:
            raise DetectionPackError(f"Required detection pack '{pack_id}' is not installed.")
        directory, manifest = catalogue[pack_id]
        resolved.append(ResolvedPack(pack_id, str(manifest.get("version", "0")), selected[pack_id], directory, manifest))
    return resolved


def _pack_rule_files(pack: ResolvedPack) -> list[Path]:
    files: list[Path] = []
    for relative in pack.manifest.get("rules", {}).get("suricata", []):
        source = (pack.directory / relative).resolve()
        try:
            source.relative_to(pack.directory.resolve())
        except ValueError as exc:
            raise DetectionPackError(f"Pack {pack.id} contains an unsafe rule path.") from exc
        if source.suffix != ".rules" or not source.is_file():
            raise DetectionPackError(f"Pack {pack.id} references missing rule file {relative}.")
        files.append(source)
    return files


def build_detection_bundle(machines: Iterable[object], root: Path = DETECTION_PACKS_DIR, bundle_root: Path = DETECTION_BUNDLES_DIR) -> dict:
    machines = list(machines)
    packs = resolve_detection_packs(machines, root)
    sid_sources: dict[int, str] = {}
    files: list[tuple[str, bytes]] = []
    registry: dict[str, dict] = {}
    for pack in packs:
        for sid, metadata in pack.manifest.get("detections", {}).items():
            sid_number = int(sid)
            if sid_number in sid_sources:
                raise DetectionPackError(f"Duplicate Suricata SID {sid_number} in {pack.id} and {sid_sources[sid_number]}.")
            sid_sources[sid_number] = pack.id
            registry[str(sid_number)] = {**metadata, "pack_id": pack.id, "pack_version": pack.version}
        for source in _pack_rule_files(pack):
            content = source.read_bytes()
            for raw_sid in re.findall(rb"\bsid\s*:\s*(\d+)\s*;", content):
                sid = int(raw_sid)
                if str(sid) not in registry:
                    raise DetectionPackError(f"Rule SID {sid} in {pack.id} has no detection metadata.")
            files.append((f"pack-{pack.id}-{source.name}", content))
    for machine in machines:
        context_value = getattr(machine, "build_context", None)
        detection_rules = getattr(machine, "detection_rules", None) or {}
        if not context_value:
            continue
        context = Path(context_value).resolve()
        for index, relative in enumerate(detection_rules.get("suricata", [])):
            source = (context / relative).resolve()
            try:
                source.relative_to(context)
            except ValueError as exc:
                raise DetectionPackError("A machine contains an unsafe detection rule path.") from exc
            if not source.is_file() or source.suffix != ".rules":
                raise DetectionPackError(f"Machine rule {relative} is missing.")
            content = source.read_bytes()
            source_name = f"machine-{getattr(machine, 'id', 'unknown')}-{index}"
            for raw_sid in re.findall(rb"\bsid\s*:\s*(\d+)\s*;", content):
                sid = int(raw_sid)
                if sid in sid_sources:
                    raise DetectionPackError(f"Duplicate Suricata SID {sid} in {source_name} and {sid_sources[sid]}.")
                sid_sources[sid] = source_name
            files.append((source_name + ".rules", content))
    digest = hashlib.sha256()
    for name, content in sorted(files):
        digest.update(name.encode() + b"\0" + content)
    digest.update(json.dumps(registry, sort_keys=True).encode())
    bundle_id = digest.hexdigest()
    bundle_dir = bundle_root / bundle_id
    if not bundle_dir.exists():
        bundle_dir.mkdir(parents=True)
        for name, content in files:
            (bundle_dir / name).write_bytes(content)
        (bundle_dir / "registry.json").write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")
        (bundle_dir / "bundle.json").write_text(json.dumps({
            "digest": bundle_id,
            "packs": [{"id": pack.id, "version": pack.version, "reason": pack.reason} for pack in packs],
            "rule_files": [name for name, _ in files],
        }, indent=2, sort_keys=True), encoding="utf-8")
    return json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))


def detection_registry(root: Path = DETECTION_PACKS_DIR) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for pack_id, (_, manifest) in load_pack_catalogue(root).items():
        for sid, metadata in manifest.get("detections", {}).items():
            if str(sid) in registry:
                raise DetectionPackError(f"Duplicate detection SID {sid} in the pack catalogue.")
            registry[str(sid)] = {**metadata, "pack_id": pack_id, "pack_version": str(manifest.get("version", "0"))}
    return registry


def bundle_registry(bundle_digest: str, bundle_root: Path = DETECTION_BUNDLES_DIR) -> dict[str, dict]:
    path = bundle_root / bundle_digest / "registry.json"
    if not path.is_file():
        raise DetectionPackError(f"Detection bundle {bundle_digest} is not available.")
    return json.loads(path.read_text(encoding="utf-8"))


def install_bundle(bundle: dict, destination: Path, bundle_root: Path = DETECTION_BUNDLES_DIR) -> list[str]:
    source_dir = bundle_root / bundle["digest"]
    installed = []
    for filename in bundle["rule_files"]:
        shutil.copyfile(source_dir / filename, destination / filename)
        installed.append(filename)
    shutil.copyfile(source_dir / "registry.json", destination.parent / "detection-registry.json")
    shutil.copyfile(source_dir / "bundle.json", destination.parent / "detection-bundle.json")
    return installed
