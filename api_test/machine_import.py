from __future__ import annotations

import io
import hashlib
import json
import re
import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from api_test.config import IMPORTED_MACHINES_DIR

MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MACHINE_MANIFEST = "machine.json"
LOG_RULE_FIELDS = {"id", "field", "pattern", "tactic", "technique_id", "technique", "rationale"}


class MachineImportError(ValueError):
    pass


def machine_content_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def github_repository(value: str) -> tuple[str, str]:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.query or parsed.fragment:
        raise MachineImportError("Repository URL must be an HTTPS github.com repository URL.")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise MachineImportError("Repository URL must have the form https://github.com/owner/repository.")
    owner, repository = parts
    repository = repository.removesuffix(".git")
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in (owner, repository)):
        raise MachineImportError("Repository owner or name is invalid.")
    return owner, repository


def validate_ref(value: str) -> str:
    ref = value.strip()
    if not ref or not re.fullmatch(r"[A-Za-z0-9._/-]+", ref) or ".." in ref or ref.startswith("/"):
        raise MachineImportError("Repository ref is invalid.")
    return ref


def validate_folder(value: str) -> PurePosixPath:
    folder = PurePosixPath(value.strip().strip("/"))
    if not folder.parts or any(part in {"", ".", ".."} for part in folder.parts):
        raise MachineImportError("Machine folder must be a relative repository path.")
    return folder


def download_github_archive(repository_url: str, ref: str) -> bytes:
    owner, repository = github_repository(repository_url)
    safe_ref = validate_ref(ref)
    request = urllib.request.Request(
        f"https://codeload.github.com/{owner}/{repository}/tar.gz/{safe_ref}",
        headers={"User-Agent": "Mayajal-Machine-Importer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_ARCHIVE_BYTES:
            raise MachineImportError("Repository archive is too large.")
        archive = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise MachineImportError("Repository archive is too large.")
    return archive


def install_machine_archive(archive: bytes, machine_folder: str, destination: Path) -> dict:
    folder = validate_folder(machine_folder)
    destination.mkdir(parents=True, exist_ok=False)
    extracted_size = 0
    found_files: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            members = bundle.getmembers()
            if not members:
                raise MachineImportError("Repository archive is empty.")
            root = PurePosixPath(members[0].name).parts[0]
            prefix = PurePosixPath(root) / folder
            for member in members:
                member_path = PurePosixPath(member.name)
                try:
                    relative = member_path.relative_to(prefix)
                except ValueError:
                    continue
                if not relative.parts or member.isdir():
                    continue
                if member.issym() or member.islnk() or not member.isfile() or ".." in relative.parts:
                    raise MachineImportError("Machine folders may contain only regular files and directories.")
                extracted_size += member.size
                if extracted_size > MAX_EXTRACTED_BYTES:
                    raise MachineImportError("Machine folder is too large after extraction.")
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise MachineImportError("Unable to read a machine file from the repository archive.")
                with target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                found_files.add(relative.as_posix())
        if "Dockerfile" not in found_files:
            raise MachineImportError("Machine folder must contain a file named Dockerfile.")
        if MACHINE_MANIFEST not in found_files:
            raise MachineImportError("Machine folder must contain machine.json.")
        manifest = json.loads((destination / MACHINE_MANIFEST).read_text(encoding="utf-8"))
        required = {"name", "image", "os_type", "description"}
        if not isinstance(manifest, dict) or not required.issubset(manifest):
            raise MachineImportError("machine.json is missing required metadata.")
        detection = manifest.get("detection")
        if not isinstance(detection, dict):
            raise MachineImportError("machine.json must declare detection rules.")
        network = detection.get("network", {})
        logs = detection.get("logs", {})
        if not isinstance(network, dict) or not isinstance(logs, dict):
            raise MachineImportError("Detection network and logs declarations must be objects.")
        suricata_rules = network.get("suricata", [])
        if not isinstance(suricata_rules, list):
            raise MachineImportError("detection.network.suricata must be a list.")
        normalized_suricata: list[str] = []
        for rule_path in suricata_rules:
            path = PurePosixPath(str(rule_path))
            if path.suffix != ".rules" or path.parts[:2] != ("detections", "network") or path.as_posix() not in found_files:
                raise MachineImportError("Every Suricata rule must be a .rules file under detections/network/.")
            normalized_suricata.append(path.as_posix())
        normalized_logs: list[dict] = []
        for source in ("application", "system"):
            declared = logs.get(source, [])
            if not isinstance(declared, list):
                raise MachineImportError(f"detection.logs.{source} must be a list.")
            for rule_path in declared:
                path = PurePosixPath(str(rule_path))
                expected_prefix = ("detections", f"{source}-logs")
                if path.suffix != ".json" or path.parts[:2] != expected_prefix or path.as_posix() not in found_files:
                    raise MachineImportError(f"Every {source} log rule must be JSON under detections/{source}-logs/.")
                rule = json.loads((destination.joinpath(*path.parts)).read_text(encoding="utf-8"))
                rules = rule if isinstance(rule, list) else [rule]
                for item in rules:
                    if not isinstance(item, dict) or not LOG_RULE_FIELDS.issubset(item):
                        raise MachineImportError(f"Log rule {path.as_posix()} is missing required fields.")
                    try:
                        re.compile(str(item["pattern"]))
                    except re.error as exc:
                        raise MachineImportError(f"Log rule {path.as_posix()} contains an invalid regular expression.") from exc
                    normalized_logs.append({**item, "source": source, "rule_file": path.as_posix()})
        if not normalized_suricata and not normalized_logs:
            raise MachineImportError("Each machine must provide at least one network or log detection rule.")
        manifest["detection_rules"] = {"suricata": normalized_suricata, "logs": normalized_logs}
        attachments = sorted(
            path.relative_to(destination).as_posix()
            for path in (destination / "attachments").rglob("*")
            if path.is_file()
        ) if (destination / "attachments").is_dir() else []
        manifest["attachments"] = attachments
        return manifest
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
