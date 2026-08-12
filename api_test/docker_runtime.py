import asyncio
import hashlib
import ipaddress
import json
import re
import shutil
import socket
import subprocess
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import HTTPException, status
from jinja2 import Template

from api_test.config import ASSETS_DIR, LAB_RUNTIME_DIR, MAYAJAL_DETECTION_ENGINE_MODE, MAYAJAL_MASTER_URL, MAYAJAL_TELEMETRY_HOST, MAYAJAL_TELEMETRY_PORT
from api_test.detection_packs import build_detection_bundle, install_bundle
from api_test.models import Lab, Machine


class DockerProcessError(RuntimeError):
    def __init__(self, message: str, output: str):
        super().__init__(message)
        self.output = output


def _compose_available(command: list[str]) -> bool:
    try:
        result = subprocess.run(
            [*command, "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _docker_compose_prefix() -> list[str]:
    if shutil.which("docker") and _compose_available(["docker", "compose"]):
        return ["docker", "compose"]
    if shutil.which("docker-compose") and _compose_available(["docker-compose"]):
        return ["docker-compose"]
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Docker Compose is not available on this host.",
    )


def _service_name(machine: Machine) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", machine.name.lower()).strip("-_")
    suffix = hashlib.sha1(machine.id.encode()).hexdigest()[:8]
    return (base or "machine") + "-" + suffix


def _clean_list(values: list[str] | None) -> list[str]:
    return [value.strip() for value in values or [] if value and value.strip()]


def _clean_dict(values: dict[str, str] | None) -> dict[str, str]:
    return {key.strip(): value.strip() for key, value in (values or {}).items() if key.strip()}


def _machine_build_context(machine: Machine) -> str | None:
    if machine.build_context:
        context = Path(machine.build_context).resolve()
        return str(context) if context.is_dir() and (context / "Dockerfile").is_file() else None
    return None


def _imported_suricata_rules(lab: Lab) -> list[tuple[Path, str]]:
    rules: list[tuple[Path, str]] = []
    for machine in lab.machines:
        if not machine.build_context or not machine.detection_rules:
            continue
        context = Path(machine.build_context).resolve()
        for index, relative in enumerate(machine.detection_rules.get("suricata", [])):
            source = (context / relative).resolve()
            try:
                source.relative_to(context)
            except ValueError:
                continue
            if source.is_file():
                rules.append((source, f"machine-{machine.id}-{index}.rules"))
    return rules


def instance_id(lab: Lab, user_id: str) -> str:
    return f"{lab.id}-{user_id}"


def _lab_subnet(project_id: str, existing_subnet: str | None = None) -> str:
    digest = hashlib.sha1(project_id.encode()).digest()
    existing = _docker_network_subnets(exclude_names={project_id, f"{project_id}_telemetry"})
    if existing_subnet:
        try:
            reusable = ipaddress.ip_network(existing_subnet, strict=False)
        except ValueError:
            reusable = None
        if isinstance(reusable, ipaddress.IPv4Network) and not any(reusable.overlaps(network) for network in existing):
            return str(reusable)
    for offset in range(4096):
        value = (int.from_bytes(digest[:2], "big") + offset) % 4096
        second = 200 + value // 256
        third = value % 256
        candidate = ipaddress.ip_network(f"10.{second}.{third}.0/24")
        if not any(candidate.overlaps(network) for network in existing):
            return str(candidate)
    raise RuntimeError("Could not allocate a non-overlapping lab subnet.")


def _docker_network_subnets(exclude_names: set[str] | None = None) -> list[ipaddress.IPv4Network]:
    exclude_names = exclude_names or set()
    reserved = [
        ipaddress.ip_network("172.17.0.0/16"),
        ipaddress.ip_network("172.18.0.0/16"),
    ]
    if not shutil.which("docker"):
        return reserved
    try:
        result = subprocess.run(
            ["docker", "network", "inspect", *subprocess.check_output(["docker", "network", "ls", "-q"], text=True).split()],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return reserved
    if result.returncode:
        return reserved
    try:
        networks = json.loads(result.stdout)
    except json.JSONDecodeError:
        return reserved
    subnets = list(reserved)
    for network in networks:
        if network.get("Name") in exclude_names:
            continue
        for item in network.get("IPAM", {}).get("Config", []) or []:
            subnet = item.get("Subnet")
            if not subnet:
                continue
            try:
                parsed = ipaddress.ip_network(subnet, strict=False)
            except ValueError:
                continue
            if isinstance(parsed, ipaddress.IPv4Network):
                subnets.append(parsed)
    return subnets


def _wireguard_subnet(project_id: str) -> str:
    digest = hashlib.sha1(project_id.encode()).digest()
    second = 64 + digest[2] % 16
    third = digest[3]
    return f"10.{second}.{third}.0/24"


def _wireguard_lab_ip(lab_subnet: str) -> str:
    network = ipaddress.ip_network(lab_subnet)
    return str(network.broadcast_address - 1)


def _vpn_port(project_id: str) -> str:
    digest = hashlib.sha1(project_id.encode()).digest()
    return str(52000 + int.from_bytes(digest[:2], "big") % 10000)


def _master_url() -> str:
    if MAYAJAL_MASTER_URL:
        return MAYAJAL_MASTER_URL
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _ensure_suricata_http_eve_logging(config: str) -> None:
    eve_index = config.find("- eve-log:")
    http_index = config.find("- http:", eve_index)
    if eve_index == -1 or http_index == -1:
        raise RuntimeError("Suricata EVE HTTP logging is not configured.")
    http_section = config[http_index:config.find("\n        - ", http_index + 1)]
    if "enabled: yes" not in http_section:
        raise RuntimeError("Suricata EVE HTTP logging is disabled.")


def _render_suricata_config(base_config: str, lab_subnet: str, rule_files: list[str]) -> str:
    rendered = base_config.replace("HOME_NET: \"[172.30.20.0/24]\"", f"HOME_NET: \"[{lab_subnet}]\"")
    if rule_files:
        rule_lines = "\n".join(f"  - {rule_file}" for rule_file in rule_files)
        rendered = rendered.replace("rule-files:\n  - suricata.rules", "rule-files:\n  - suricata.rules\n" + rule_lines)
    return rendered


def prepare_lab_runtime(lab: Lab, project_id: str, peer_id: str, session_id: str, refresh_vpn_config: bool = False) -> Path:
    lab_dir = LAB_RUNTIME_DIR / project_id
    lab_dir.mkdir(parents=True, exist_ok=True)
    existing_lab_subnet = None
    existing_env = lab_dir / ".env"
    if existing_env.is_file():
        for line in existing_env.read_text().splitlines():
            if line.startswith("LABSUBNET="):
                existing_lab_subnet = line.split("=", 1)[1].strip()
                break
    lab_subnet = _lab_subnet(project_id, existing_lab_subnet)
    wireguard_subnet = _wireguard_subnet(project_id)
    if refresh_vpn_config:
        shutil.rmtree(lab_dir / "config" / "wireguard", ignore_errors=True)

    wireguard_templates_dir = lab_dir / "config" / "wireguard" / "templates"
    wireguard_templates_dir.mkdir(parents=True, exist_ok=True)
    (wireguard_templates_dir / "server.conf").write_text(
        "\n".join([
            "[Interface]",
            "Address = ${INTERFACE}.1",
            "ListenPort = 51820",
            "PrivateKey = $(cat /config/server/privatekey-server)",
            "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT",
            "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT",
            "",
        ])
    )

    env_template = Template((ASSETS_DIR / "env.j2").read_text())
    (lab_dir / ".env").write_text(
        env_template.render(
            LABID=project_id,
            LABROOT=str(LAB_RUNTIME_DIR),
            LABSUBNET=lab_subnet,
            LABGATEWAY=_wireguard_lab_ip(lab_subnet),
            WGSUBNET=wireguard_subnet,
            PEERS="peer1",
            MASTERURL=_master_url(),
            VPNPORT=_vpn_port(project_id),
            SESSIONID=session_id,
            LAB_UUID=lab.id,
            USERID=peer_id,
            TELEMETRY_HOST=MAYAJAL_TELEMETRY_HOST,
            TELEMETRY_PORT=MAYAJAL_TELEMETRY_PORT,
        )
    )

    fluent_bit_dir = lab_dir / "generated" / "fluent-bit"
    fluent_bit_dir.mkdir(parents=True, exist_ok=True)
    (fluent_bit_dir / "fluent-bit.conf").write_text((ASSETS_DIR / "fluent-bit" / "lab-fluent-bit.conf").read_text())
    (lab_dir / "state").mkdir(parents=True, exist_ok=True)

    suricata_dir = lab_dir / "generated" / "suricata"
    suricata_dir.mkdir(parents=True, exist_ok=True)
    imported_rules = _imported_suricata_rules(lab) if MAYAJAL_DETECTION_ENGINE_MODE == "legacy" else []
    rules_dir = suricata_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "suricata.rules").write_text("")
    pack_rule_files: list[str] = []
    if MAYAJAL_DETECTION_ENGINE_MODE in {"shadow", "packs"}:
        pack_rule_files = install_bundle(build_detection_bundle(lab.machines), rules_dir)
    for source, filename in imported_rules:
        shutil.copyfile(source, rules_dir / filename)
    suricata_config = ASSETS_DIR / "config" / "suricata" / "suricata.yaml"
    rendered_suricata = _render_suricata_config(
        suricata_config.read_text(),
        lab_subnet,
        [*pack_rule_files, *[filename for _, filename in imported_rules]],
    )
    _ensure_suricata_http_eve_logging(rendered_suricata)
    (suricata_dir / "suricata.yaml").write_text(rendered_suricata)

    machine_template = Template((ASSETS_DIR / "machine_template.yml.j2").read_text())
    for machine in lab.machines:
        (lab_dir / f"{machine.id}.yml").write_text(
            machine_template.render(
                name=_service_name(machine),
                image=machine.image_url,
                build_context=_machine_build_context(machine),
                hostname=machine.hostname,
                command=machine.command,
                entrypoint=machine.entrypoint,
                working_dir=machine.working_dir,
                run_as=machine.run_as,
                env=_clean_dict(machine.environment),
                labels=_clean_dict(machine.labels),
                ports=_clean_list(machine.ports),
                volumes=_clean_list(machine.volumes),
                dns=_clean_list(machine.dns),
                extra_hosts=_clean_list(machine.extra_hosts),
                cap_add=_clean_list(machine.cap_add),
                network_aliases=_clean_list(machine.network_aliases),
                privileged=machine.privileged,
                tty=machine.tty,
                stdin_open=machine.stdin_open,
                restart_policy=machine.restart_policy or "unless-stopped",
                memory_limit=machine.memory_limit or "512m",
                cpu_limit=machine.cpu_limit or 1.0,
            )
        )
    return lab_dir


def compose_command(lab: Lab, action: str, project_id: str, peer_id: str, session_id: str) -> list[str]:
    command = compose_base_command(lab, project_id, peer_id, session_id, refresh_vpn_config=action == "start")
    if action == "start":
        command.extend(["up", "-d"])
    elif action == "stop":
        command.extend(["down", "--remove-orphans"])
    else:
        raise ValueError("Unsupported compose action: " + action)
    return command


def compose_base_command(lab: Lab, project_id: str, peer_id: str, session_id: str, refresh_vpn_config: bool = False) -> list[str]:
    lab_dir = prepare_lab_runtime(lab, project_id, peer_id, session_id, refresh_vpn_config=refresh_vpn_config)
    command = _docker_compose_prefix()
    command.extend(["-f", str(ASSETS_DIR / "base_compose.yml")])
    for machine in lab.machines:
        command.extend(["-f", str(lab_dir / f"{machine.id}.yml")])
    command.extend(["--env-file", str(lab_dir / ".env"), "-p", project_id])
    return command


def expected_services(lab: Lab) -> set[str]:
    return {"wireguard", "suricata", "fluent-bit", *[_service_name(machine) for machine in lab.machines]}


def expected_container_names(lab: Lab, project_id: str) -> list[str]:
    return [f"{project_id}_{service}" for service in sorted(expected_services(lab))]


async def stream_process(command: list[str]) -> AsyncIterator[str]:
    yield "$ " + " ".join(command) + "\n"
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if process.stdout is not None:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            yield line.decode(errors="replace")
    return_code = await process.wait()
    yield f"\nProcess exited with code {return_code}\n"
    if return_code:
        raise DockerProcessError("Docker Compose exited with code " + str(return_code), "")


async def run_process(command: list[str], expose_output: bool = False) -> str:
    output: list[str] = []
    try:
        async for chunk in stream_process(command):
            output.append(chunk)
    except DockerProcessError as exc:
        detail = "\n".join(output) + "\n" + str(exc)
        if not expose_output:
            detail = "Lab containers could not complete the requested operation. Ask an administrator to review the container output."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc
    return "".join(output) if expose_output else ""


async def run_process_capture(command: list[str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode(errors="replace")
    if process.returncode:
        raise DockerProcessError("Docker Compose exited with code " + str(process.returncode), output)
    return output


def parse_compose_ps(output: str) -> list[dict]:
    text = output.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        items = []
        for line in text.splitlines():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items


async def verify_compose_project(lab: Lab, project_id: str, timeout_seconds: int = 45) -> str:
    if not shutil.which("docker"):
        raise DockerProcessError("Docker is not available for container state inspection.", "")
    expected = expected_container_names(lab, project_id)
    deadline = time.monotonic() + timeout_seconds
    last_output = ""
    while time.monotonic() < deadline:
        lines = []
        missing = []
        for name in expected:
            try:
                state = (await run_process_capture(["docker", "inspect", "-f", "{{.State.Running}}", name])).strip()
            except DockerProcessError as exc:
                state = exc.output.strip() or "missing"
            lines.append(name + "=" + state)
            if state.lower() != "true":
                missing.append(name)
        last_output = "\n".join(lines)
        if not missing:
            return last_output
        await asyncio.sleep(1)
    raise DockerProcessError("Compose project did not reach running state.", last_output)


async def wait_for_wireguard_config(project_id: str, timeout_seconds: int = 60) -> str:
    config = LAB_RUNTIME_DIR / project_id / "config" / "wireguard" / "peer_peer1" / "peer_peer1.conf"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if config.is_file() and config.stat().st_size > 0:
            return config.read_text()
        await asyncio.sleep(1)
    raise DockerProcessError("WireGuard peer configuration was not generated.", str(config))
