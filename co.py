#!/usr/bin/env python3
"""
Suricata Eve.json Correlation Engine
Maps raw Suricata logs to a structured attack chain automatically.
No rules or alerts required — works purely from logged events.

Usage:
    python3 correlate.py /var/log/suricata/eve.json
    python3 correlate.py /var/log/suricata/eve.json --attacker 192.168.1.10
    python3 correlate.py /var/log/suricata/eve.json --output report.json
    python3 correlate.py /var/log/suricata/eve.json --format json
"""

import json
import sys
import argparse
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address

# ---------------------------------------------------------------------------
# MITRE ATT&CK mapping
# ---------------------------------------------------------------------------
MITRE = {
    "ping_sweep":      ("T1595.001", "Active Scanning: ICMP"),
    "port_scan":       ("T1046",     "Network Service Discovery"),
    "web_recon":       ("T1595.003", "Web Crawl / Active Recon"),
    "sqli":            ("T1190",     "Exploit Public-Facing Application"),
    "exfil":           ("T1041",     "Exfiltration Over C2 Channel"),
    "dns_recon":       ("T1590.002", "DNS-based Recon"),
    "cred_brute":      ("T1110",     "Brute Force"),
    "lateral_move":    ("T1021",     "Remote Services"),
    "file_download":   ("T1105",     "Ingress Tool Transfer"),
    "tls_fingerprint": ("T1071.001", "App Layer Protocol: Web"),
}

# ---------------------------------------------------------------------------
# Thresholds (tune to your environment)
# ---------------------------------------------------------------------------
SCAN_PORT_THRESHOLD   = 50
PING_SWEEP_THRESHOLD  = 3
SQLI_URI_KEYWORDS     = ["union", "select", "insert", "drop", "sleep(",
                          "benchmark(", "' or ", "1=1", "--", "/*",
                          "xp_cmdshell", "information_schema"]
BURP_UA_HINTS         = ["burp", "intruder", "scanner", "nikto", "dirbuster",
                          "gobuster", "wfuzz", "ffuf", "sqlmap",
                          "nmap scripting"]
LARGE_RESP_BYTES      = 50_000

# ANSI colors
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

SEV_COLOR = {
    "CRITICAL": RED, "HIGH": RED, "MEDIUM": YELLOW,
    "LOW": BLUE, "INFO": CYAN
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_events(path: str) -> list:
    events = []
    with open(path, "r", errors="replace") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [warn] line {i}: {e}", file=sys.stderr)
    return events


def parse_ts(ts: str) -> datetime:
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def fmt_ts(dt: datetime) -> str:
    if dt == datetime.min.replace(tzinfo=timezone.utc):
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# Core correlation
# ---------------------------------------------------------------------------

def correlate(events: list, attacker_hint: str = None) -> dict:
    # Bucket by event_type
    flows     = [e for e in events if e.get("event_type") == "flow"]
    http_evs  = [e for e in events if e.get("event_type") == "http"]
    dns_evs   = [e for e in events if e.get("event_type") == "dns"]
    tls_evs   = [e for e in events if e.get("event_type") == "tls"]
    alerts    = [e for e in events if e.get("event_type") == "alert"]
    ssh_evs   = [e for e in events if e.get("event_type") == "ssh"]
    anomalies = [e for e in events if e.get("event_type") == "anomaly"]
    files_evs = [e for e in events if e.get("event_type") == "fileinfo"]

    all_ipv4_tcp = [f for f in flows
                    if f.get("ip_v") == 4 and f.get("proto") == "TCP"]

    # Infer attacker IP: IPv4 source touching the most distinct destinations
    if attacker_hint:
        attacker_ip = attacker_hint
    else:
        src_dst_map = defaultdict(set)
        for f in all_ipv4_tcp:
            src_dst_map[f.get("src_ip", "")].add(f.get("dest_ip", ""))
        attacker_ip = max(src_dst_map, key=lambda k: len(src_dst_map[k]),
                          default=None)

    # Time range across all events
    all_ts = [parse_ts(e["timestamp"]) for e in events if "timestamp" in e]
    t_start = fmt_ts(min(all_ts)) if all_ts else "unknown"
    t_end   = fmt_ts(max(all_ts)) if all_ts else "unknown"

    stats = {
        "total_events": len(events),
        "attacker_ip":  attacker_ip,
        "time_range":   {"start": t_start, "end": t_end},
        "event_counts": {
            "flow": len(flows), "http": len(http_evs), "dns": len(dns_evs),
            "tls": len(tls_evs), "alert": len(alerts), "ssh": len(ssh_evs),
            "anomaly": len(anomalies), "fileinfo": len(files_evs),
        },
    }

    if not attacker_ip:
        return {"stats": stats, "chain": [], "recommendations": build_recs(stats)}

    atk_tcp = [f for f in all_ipv4_tcp if f.get("src_ip") == attacker_ip]
    chain   = []

    # ================================================================
    # Phase 1 — ICMP Ping Sweep
    # ================================================================
    icmp_flows = [f for f in flows
                  if f.get("proto") == "ICMP"
                  and f.get("icmp_type") == 8
                  and f.get("src_ip") == attacker_ip]
    if icmp_flows:
        ts_list = [parse_ts(f["timestamp"]) for f in icmp_flows]
        chain.append({
            "phase":      "Host Discovery (Ping Sweep)",
            "mitre_id":   MITRE["ping_sweep"][0],
            "mitre_name": MITRE["ping_sweep"][1],
            "severity":   "MEDIUM",
            "src_ip":     attacker_ip,
            "dst_ips":    sorted(set(f["dest_ip"] for f in icmp_flows)),
            "first_seen": fmt_ts(min(ts_list)),
            "last_seen":  fmt_ts(max(ts_list)),
            "evidence":   [
                f"ICMP echo-request → {f['dest_ip']} at {f['timestamp']} "
                f"(bytes={f.get('flow',{}).get('bytes_toserver',0)})"
                for f in icmp_flows
            ],
            "gaps": [],
        })

    # ================================================================
    # Phase 2 — Port Scan
    # ================================================================
    dst_port_map = defaultdict(list)
    for f in atk_tcp:
        dst_port_map[f.get("dest_ip", "")].append(f)

    scan_targets = {}
    for dst, flist in dst_port_map.items():
        ports = [f.get("dest_port") for f in flist if f.get("dest_port")]
        if len(set(ports)) >= SCAN_PORT_THRESHOLD:
            ts_list = sorted(parse_ts(f["timestamp"]) for f in flist)
            scan_targets[dst] = {
                "ports":     sorted(set(ports)),
                "count":     len(set(ports)),
                "first":     ts_list[0],
                "last":      ts_list[-1],
                "window_s":  (ts_list[-1] - ts_list[0]).total_seconds(),
                "flows":     flist,
            }

    if scan_targets:
        all_dst  = list(scan_targets.keys())
        all_ts_s = [t for s in scan_targets.values() for t in [s["first"], s["last"]]]
        evidence = []
        for dst, s in scan_targets.items():
            interesting = [p for p in s["ports"] if p in
                           [21,22,23,25,53,80,110,139,143,443,445,1433,
                            1521,3306,3389,5432,5900,8080,8443]]
            evidence.append(
                f"{s['count']} unique ports → {dst} in {s['window_s']:.0f}s "
                f"({fmt_ts(s['first'])})"
            )
            if interesting:
                evidence.append(f"  Notable ports: {interesting}")
        chain.append({
            "phase":      "Port Scan",
            "mitre_id":   MITRE["port_scan"][0],
            "mitre_name": MITRE["port_scan"][1],
            "severity":   "HIGH",
            "src_ip":     attacker_ip,
            "dst_ips":    all_dst,
            "first_seen": fmt_ts(min(all_ts_s)),
            "last_seen":  fmt_ts(max(all_ts_s)),
            "evidence":   evidence,
            "gaps":       [],
        })

    # ================================================================
    # Phase 3 — Web Recon (Burp / active scanner)
    # ================================================================
    web_evidence = []
    web_dst      = []
    web_ts       = []
    web_gaps     = []

    attacker_http = [e for e in http_evs if e.get("src_ip") == attacker_ip]
    if attacker_http:
        for e in attacker_http:
            h   = e.get("http", {})
            ua  = h.get("http_user_agent", "")
            url = h.get("url", "")
            entry = (f"{h.get('http_method')} "
                     f"http://{e.get('dest_ip')}:{e.get('dest_port')}{url} "
                     f"→ {h.get('status')}")
            if any(hint in ua.lower() for hint in BURP_UA_HINTS):
                entry += f"  [TOOL UA: {ua}]"
            web_evidence.append(entry)
            web_dst.append(e.get("dest_ip", ""))
            web_ts.append(parse_ts(e["timestamp"]))
    else:
        # Fallback: TCP flows to web ports
        http_port_flows = [f for f in atk_tcp
                           if f.get("dest_port") in [80, 8080, 8000, 8443, 3000]]
        for f in http_port_flows:
            flow = f.get("flow", {})
            web_evidence.append(
                f"TCP → {f['dest_ip']}:{f['dest_port']} "
                f"bytes_toserver={flow.get('bytes_toserver')} "
                f"bytes_toclient={flow.get('bytes_toclient')} "
                f"state={flow.get('state')}"
            )
            web_dst.append(f.get("dest_ip", ""))
            web_ts.append(parse_ts(f["timestamp"]))
        if http_port_flows:
            web_gaps.append(
                "HTTP app-layer logging disabled: URIs, User-Agents, "
                "and response codes not recorded. "
                "Fix: enable 'http: enabled: yes' in suricata.yaml outputs."
            )

    if web_evidence:
        chain.append({
            "phase":      "Web Recon (Burp Suite)",
            "mitre_id":   MITRE["web_recon"][0],
            "mitre_name": MITRE["web_recon"][1],
            "severity":   "HIGH",
            "src_ip":     attacker_ip,
            "dst_ips":    sorted(set(web_dst)),
            "first_seen": fmt_ts(min(web_ts)) if web_ts else "unknown",
            "last_seen":  fmt_ts(max(web_ts)) if web_ts else "unknown",
            "evidence":   web_evidence,
            "gaps":       web_gaps,
        })

    # ================================================================
    # Phase 4 — SQL Injection
    # ================================================================
    sqli_evidence = []
    sqli_dst      = []
    sqli_ts_list  = []
    sqli_gaps     = []

    # From HTTP event URIs
    for e in http_evs:
        h   = e.get("http", {})
        uri = (h.get("url") or "").lower()
        ua  = (h.get("http_user_agent") or "").lower()
        if any(kw in uri for kw in SQLI_URI_KEYWORDS) or "sqlmap" in ua:
            sqli_dst.append(e.get("dest_ip", ""))
            sqli_ts_list.append(parse_ts(e["timestamp"]))
            sqli_evidence.append(
                f"SQLi URI: {h.get('http_method')} {h.get('url')} "
                f"(UA: {h.get('http_user_agent')})"
            )

    # From alert signatures
    for a in alerts:
        sig = a.get("alert", {}).get("signature", "").lower()
        if any(kw in sig for kw in ["sql", "injection", "union", "sqlmap"]):
            sqli_dst.append(a.get("dest_ip", ""))
            sqli_ts_list.append(parse_ts(a["timestamp"]))
            sqli_evidence.append(
                f"ALERT: {a['alert']['signature']} "
                f"(sev={a['alert'].get('severity')})"
            )

    # Infer from post-scan HTTP flows when no HTTP logs available
    if not sqli_evidence and scan_targets:
        latest_scan = max(s["last"] for s in scan_targets.values())
        post_scan   = [f for f in atk_tcp
                       if f.get("dest_port") in [80, 8080, 8000, 8443]
                       and parse_ts(f["timestamp"]) > latest_scan]
        for f in post_scan:
            sqli_dst.append(f.get("dest_ip", ""))
            sqli_ts_list.append(parse_ts(f["timestamp"]))
            sqli_evidence.append(
                f"Post-scan HTTP flow → {f['dest_ip']}:{f['dest_port']} "
                f"(bytes_toserver={f.get('flow',{}).get('bytes_toserver')})"
            )
        if post_scan:
            sqli_gaps.append(
                "No HTTP logs: SQLi payloads not recorded. "
                "Enable HTTP logging + ET Open SQLi rules to capture injections."
            )

    if sqli_evidence:
        chain.append({
            "phase":      "SQL Injection (sqlmap)",
            "mitre_id":   MITRE["sqli"][0],
            "mitre_name": MITRE["sqli"][1],
            "severity":   "CRITICAL",
            "src_ip":     attacker_ip,
            "dst_ips":    sorted(set(sqli_dst)),
            "first_seen": fmt_ts(min(sqli_ts_list)) if sqli_ts_list else "unknown",
            "last_seen":  fmt_ts(max(sqli_ts_list)) if sqli_ts_list else "unknown",
            "evidence":   sqli_evidence,
            "gaps":       sqli_gaps,
        })

    # ================================================================
    # Phase 5 — Data Exfiltration
    # ================================================================
    exfil_evidence = []
    exfil_dst      = []
    exfil_ts_list  = []
    exfil_gaps     = []

    # Large HTTP responses
    for e in http_evs:
        resp_bytes = e.get("http", {}).get("response_bodylen", 0) or 0
        if resp_bytes > LARGE_RESP_BYTES:
            exfil_dst.append(e.get("src_ip", ""))
            exfil_ts_list.append(parse_ts(e["timestamp"]))
            exfil_evidence.append(
                f"Large HTTP response {resp_bytes:,} bytes from "
                f"{e.get('src_ip')} URL={e.get('http',{}).get('url')}"
            )

    # Large toclient in flow events
    for f in all_ipv4_tcp:
        if (f.get("flow", {}).get("bytes_toclient", 0) > LARGE_RESP_BYTES
                and f.get("dest_ip") == attacker_ip):
            exfil_dst.append(f.get("src_ip", ""))
            exfil_ts_list.append(parse_ts(f["timestamp"]))
            exfil_evidence.append(
                f"Large flow from {f['src_ip']}:{f.get('src_port')} → attacker "
                f"({f['flow']['bytes_toclient']:,} bytes)"
            )

    # File events
    for fe in files_evs:
        fi = fe.get("fileinfo", {})
        if fi.get("size", 0) > 10_000:
            exfil_evidence.append(
                f"File: {fi.get('filename')} "
                f"({fi.get('size',0):,} bytes, md5={fi.get('md5')})"
            )

    if not exfil_evidence and sqli_evidence:
        exfil_gaps.append(
            "Data dump not directly observed. HTTP response bodies require "
            "stream reassembly depth=0 and HTTP extended logging to capture."
        )
        exfil_evidence.append(
            "Inferred: data dump likely followed SQLi phase (not directly recorded)"
        )
        exfil_ts_list = sqli_ts_list[-1:] if sqli_ts_list else []

    if exfil_evidence:
        chain.append({
            "phase":      "Data Exfiltration (table dump)",
            "mitre_id":   MITRE["exfil"][0],
            "mitre_name": MITRE["exfil"][1],
            "severity":   "CRITICAL",
            "src_ip":     attacker_ip,
            "dst_ips":    sorted(set(exfil_dst)),
            "first_seen": fmt_ts(min(exfil_ts_list)) if exfil_ts_list else "unknown",
            "last_seen":  fmt_ts(max(exfil_ts_list)) if exfil_ts_list else "unknown",
            "evidence":   exfil_evidence,
            "gaps":       exfil_gaps,
        })

    # ================================================================
    # Phase 6 — DNS Recon (bonus)
    # ================================================================
    attacker_dns = [e for e in dns_evs
                    if e.get("src_ip") == attacker_ip
                    and e.get("dns", {}).get("type") == "query"]
    if attacker_dns:
        domains = [e["dns"].get("rrname") for e in attacker_dns]
        ts_list = [parse_ts(e["timestamp"]) for e in attacker_dns]
        chain.append({
            "phase":      "DNS Reconnaissance",
            "mitre_id":   MITRE["dns_recon"][0],
            "mitre_name": MITRE["dns_recon"][1],
            "severity":   "LOW",
            "src_ip":     attacker_ip,
            "dst_ips":    sorted(set(e.get("dest_ip","") for e in attacker_dns)),
            "first_seen": fmt_ts(min(ts_list)),
            "last_seen":  fmt_ts(max(ts_list)),
            "evidence":   [f"DNS query: {d}" for d in domains[:20]],
            "gaps":       [],
        })

    # ================================================================
    # Phase 7 — TLS / JA3 Fingerprinting
    # ================================================================
    attacker_tls = [e for e in tls_evs if e.get("src_ip") == attacker_ip]
    if attacker_tls:
        ja3s = set()
        snis = set()
        for e in attacker_tls:
            tls = e.get("tls", {})
            ja3_hash = tls.get("ja3", {}).get("hash")
            if ja3_hash:
                ja3s.add(ja3_hash)
            if tls.get("sni"):
                snis.add(tls["sni"])
        ts_list = [parse_ts(e["timestamp"]) for e in attacker_tls]
        chain.append({
            "phase":      "TLS Fingerprinting",
            "mitre_id":   MITRE["tls_fingerprint"][0],
            "mitre_name": MITRE["tls_fingerprint"][1],
            "severity":   "INFO",
            "src_ip":     attacker_ip,
            "dst_ips":    sorted(set(e.get("dest_ip","") for e in attacker_tls)),
            "first_seen": fmt_ts(min(ts_list)),
            "last_seen":  fmt_ts(max(ts_list)),
            "evidence":   [
                f"JA3 hashes: {', '.join(ja3s) or 'none'}",
                f"SNI values: {', '.join(snis) or 'none'}",
            ],
            "gaps": [],
        })

    return {
        "stats":           stats,
        "chain":           chain,
        "recommendations": build_recs(stats, http_evs, alerts, all_ipv4_tcp),
    }


def build_recs(stats: dict, http_evs=None, alerts=None, tcp_flows=None) -> list:
    recs = []
    ev = stats.get("event_counts", {})

    if ev.get("http", 0) == 0:
        recs.append({
            "priority": "CRITICAL",
            "action":   "Enable HTTP app-layer logging",
            "detail":   (
                "Your eve.json has zero HTTP events. "
                "In suricata.yaml, under outputs > eve-log > types, add:\n"
                "  - http:\n      enabled: yes\n      extended: yes\n"
                "Also ensure app-layer > protocols > http > enabled: yes "
                "and add port 8080 to detection-ports."
            ),
        })
    if ev.get("alert", 0) == 0:
        recs.append({
            "priority": "HIGH",
            "action":   "Load Emerging Threats Open ruleset",
            "detail":   (
                "Zero alerts fired — no detection rules loaded. "
                "Run: suricata-update add-source et/open && suricata-update\n"
                "ET Open covers SQLi, scanners, web shells, brute force, exfil."
            ),
        })
    if tcp_flows and all(
        f.get("flow", {}).get("bytes_toclient", 0) < 200 for f in tcp_flows
    ):
        recs.append({
            "priority": "HIGH",
            "action":   "Set stream reassembly depth to 0",
            "detail":   (
                "All toclient payloads show <200 bytes — response bodies are "
                "truncated. In suricata.yaml:\n"
                "  stream:\n    reassembly:\n      depth: 0"
            ),
        })
    if ev.get("tls", 0) == 0:
        recs.append({
            "priority": "MEDIUM",
            "action":   "Enable TLS logging with JA3/JA4 fingerprints",
            "detail":   (
                "No TLS events logged. JA3 fingerprints identify tools "
                "(Burp, nmap, sqlmap) by handshake pattern without decryption.\n"
                "In suricata.yaml app-layer > protocols > tls:\n"
                "  ja3-fingerprints: yes\n  ja4-fingerprints: yes"
            ),
        })
    if ev.get("dns", 0) == 0:
        recs.append({
            "priority": "LOW",
            "action":   "Enable DNS logging",
            "detail":   (
                "No DNS events. DNS queries during recon reveal target domains. "
                "Add 'dns: enabled: yes' under eve-log types."
            ),
        })
    return recs


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(result: dict):
    stats = result["stats"]
    chain = result["chain"]
    recs  = result["recommendations"]

    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

    print("\n" + "=" * 70)
    print("  SURICATA ATTACK CHAIN CORRELATION REPORT")
    print("=" * 70)
    print(f"  Attacker IP : {stats['attacker_ip']}")
    print(f"  Time range  : {stats['time_range']['start']}  →  {stats['time_range']['end']}")
    print(f"  Events      : {stats['total_events']:,} total")
    ev = stats["event_counts"]
    print(f"  Types       : flow={ev['flow']} http={ev['http']} "
          f"dns={ev['dns']} tls={ev['tls']} alert={ev['alert']} "
          f"ssh={ev['ssh']} anomaly={ev['anomaly']}")
    print()

    for i, phase in enumerate(
        sorted(chain, key=lambda p: sev_order.get(p["severity"], 5)), 1
    ):
        sev = phase["severity"]
        col = SEV_COLOR.get(sev, "")
        print(f"{col}[{i}] {phase['phase']}{RESET}")
        print(f"    MITRE    : {phase['mitre_id']} — {phase['mitre_name']}")
        print(f"    Severity : {col}{sev}{RESET}")
        print(f"    Target(s): {', '.join(phase['dst_ips']) or 'n/a'}")
        print(f"    Time     : {phase['first_seen']}  →  {phase['last_seen']}")
        print("    Evidence :")
        for ev_line in phase["evidence"][:6]:
            print(f"      • {ev_line}")
        if len(phase["evidence"]) > 6:
            print(f"      ... and {len(phase['evidence'])-6} more")
        if phase["gaps"]:
            print("    Gaps :")
            for g in phase["gaps"]:
                print(f"      ⚠ {g}")
        print()

    if recs:
        print("-" * 70)
        print("  RECOMMENDATIONS")
        print("-" * 70)
        for r in recs:
            col = SEV_COLOR.get(r["priority"], "")
            print(f"{col}[{r['priority']}]{RESET} {r['action']}")
            for line in r["detail"].split("\n"):
                print(f"  {line}")
            print()

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Suricata eve.json Attack Chain Correlation Engine"
    )
    parser.add_argument("eve_file",  help="Path to Suricata eve.json")
    parser.add_argument("--attacker", help="Override attacker IP auto-detection")
    parser.add_argument("--output",   help="Write JSON report to this file")
    parser.add_argument("--format",   choices=["table", "json"], default="table")
    args = parser.parse_args()

    print(f"Loading {args.eve_file} ...", file=sys.stderr)
    events = load_events(args.eve_file)
    print(f"Loaded {len(events):,} events. Correlating ...", file=sys.stderr)

    result = correlate(events, attacker_hint=args.attacker)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"JSON report → {args.output}", file=sys.stderr)

    if args.format == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        print_table(result)


if __name__ == "__main__":
    main()
