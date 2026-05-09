#!/usr/bin/env python3
"""
Walk /Users/dusanmunizaba/repo/salt/salt/states/*.py and emit
data/salt-states.json with hand-curated category/OS/summary metadata
plus auto-extracted function signatures and YAML examples.

Run from the saltify repo root:
    python3 scripts/build-states-json.py

The output JSON is what salt-states-map.html fetches at runtime.
"""

import ast
import json
import re
import sys
from pathlib import Path

SALT_REPO = Path("/Users/dusanmunizaba/repo/salt/salt/states")
DOC_URL = "https://docs.saltproject.io/en/master/ref/states/all/salt.states.{name}.html"

CATEGORIES = [
    {"id": "packages",     "label": "Packages & software install",
     "blurb": "Install, update, and remove software via OS package managers, language toolchains, and Windows update systems."},
    {"id": "files",        "label": "Files, archives, filesystems",
     "blurb": "Manage files, directories, archives, mounts, block devices, LVM, and Git checkouts as state."},
    {"id": "services",     "label": "Services & scheduling",
     "blurb": "Start, stop, and reload daemons; manage cron, scheduled tasks, beacons, and event triggers."},
    {"id": "networking",   "label": "Networking & firewalls",
     "blurb": "Hosts files, network interfaces, firewall rules, and NAPALM-managed network device config."},
    {"id": "auth",         "label": "Users, auth, certificates, ACLs",
     "blurb": "Local accounts, SSH/PGP keys, X.509 PKI, TLS, SELinux, Windows DACL/LGPO, mac keychain."},
    {"id": "data",         "label": "Web servers, databases, message brokers",
     "blurb": "Apache, IIS, PostgreSQL, RabbitMQ."},
    {"id": "sysconfig",    "label": "System config & tuning",
     "blurb": "sysctl, environment variables, locale, timezone, kernel modules, log rotation, Windows tasks."},
    {"id": "salt-meta",    "label": "Salt-on-Salt, orchestration, meta",
     "blurb": "Cross-minion orchestration, calling other configuration tools (Ansible, idem), and stateconf glue."},
    {"id": "monitoring",   "label": "Monitoring & observability",
     "blurb": "Web-server uptime monitoring (and the only state-modules monitoring entry left in core after the saltext purge)."},
]

# Hand-curated metadata for core modules. Format:
#   filename_stem -> {"category": id, "os": [...], "summary": "...", "main": "name.fn"}
# Modules not in this dict are auto-extracted with category="uncategorized"
# and a best-effort first-sentence summary — they won't render until curated.
CURATION = {
    # ── Packages ─────────────────────────────────────────────────────────
    "pkg":                  {"category": "packages", "os": ["cross-platform"], "main": "pkg.installed",
                             "summary": "Install, upgrade, and remove software via the OS package manager — apt, yum, dnf, zypper, pacman, brew, choco, and friends."},
    "pkgrepo":              {"category": "packages", "os": ["linux"],          "main": "pkgrepo.managed",
                             "summary": "Add, remove, and refresh apt or yum-style repository definitions before installing packages from them."},
    "pkgbuild":             {"category": "packages", "os": ["linux"],          "main": "pkgbuild.built",
                             "summary": "Build .rpm or .deb packages from source SPEC/control files for hosting in your own internal repo."},
    "pkgng":                {"category": "packages", "os": ["freebsd"],        "main": "pkgng.installed",
                             "summary": "Install and manage packages on FreeBSD via the pkgng (pkg-ng) package manager."},
    "chocolatey":           {"category": "packages", "os": ["windows"],        "main": "chocolatey.installed",
                             "summary": "Install Windows software via Chocolatey — the de-facto Windows package manager for ops automation."},
    "macpackage":           {"category": "packages", "os": ["mac"],            "main": "macpackage.installed",
                             "summary": "Install .pkg, .dmg, or .app bundles on macOS minions."},
    "winrepo":              {"category": "packages", "os": ["windows"],        "main": "winrepo.genrepo",
                             "summary": "Maintain the Salt winrepo cache so win_pkg can install Windows software fleet-wide from your own repo."},
    "win_appx":             {"category": "packages", "os": ["windows"],        "main": "win_appx.absent",
                             "summary": "Remove or block Windows Appx packages — the modern Microsoft Store / UWP app format."},
    "win_dism":             {"category": "packages", "os": ["windows"],        "main": "win_dism.feature_installed",
                             "summary": "Install Windows features and capabilities via DISM (Deployment Image Servicing and Management)."},
    "win_wua":              {"category": "packages", "os": ["windows"],        "main": "win_wua.installed",
                             "summary": "Install Windows Updates via the Windows Update Agent — patch installation, deferral, history."},
    "win_wusa":             {"category": "packages", "os": ["windows"],        "main": "win_wusa.installed",
                             "summary": "Install standalone Microsoft Update (.msu) packages via the Windows Update Standalone Installer."},
    "win_servermanager":    {"category": "packages", "os": ["windows"],        "main": "win_servermanager.installed",
                             "summary": "Add and remove Windows Server roles and features via the ServerManager PowerShell module."},
    "pip_state":            {"category": "packages", "os": ["cross-platform"], "main": "pip.installed",
                             "summary": "Install Python packages with pip — into the system Python, a virtualenv, or a specific interpreter."},
    "pyenv":                {"category": "packages", "os": ["cross-platform"], "main": "pyenv.installed",
                             "summary": "Manage Python interpreter installs and version switching via pyenv."},
    "virtualenv_mod":       {"category": "packages", "os": ["cross-platform"], "main": "virtualenv.managed",
                             "summary": "Create and manage Python virtual environments — the foundation for app-level Python isolation."},

    # ── Files, archives, filesystems ─────────────────────────────────────
    "file":                 {"category": "files", "os": ["cross-platform"], "main": "file.managed",
                             "summary": "Manage files and directories on disk — content, ownership, permissions, templating, line/block replacement. The most-used state module by a wide margin."},
    "archive":              {"category": "files", "os": ["cross-platform"], "main": "archive.extracted",
                             "summary": "Extract tar/zip/rar/etc archives idempotently with checksum verification."},
    "mount":                {"category": "files", "os": ["cross-platform"], "main": "mount.mounted",
                             "summary": "Manage filesystem mounts — fstab entries plus the live mount state in one shot."},
    "git":                  {"category": "files", "os": ["cross-platform"], "main": "git.latest",
                             "summary": "Manage Git repository checkouts on disk — clone, pull, branch, sparse checkouts."},
    "blockdev":             {"category": "files", "os": ["linux"]},
    "disk":                 {"category": "files", "os": ["cross-platform"]},
    "ini_manage":           {"category": "files", "os": ["cross-platform"]},
    "lvm":                  {"category": "files", "os": ["linux"]},
    "makeconf":             {"category": "files", "os": ["linux"]},
    "mdadm_raid":           {"category": "files", "os": ["linux"]},
    "quota":                {"category": "files", "os": ["linux"]},
    "sysfs":                {"category": "files", "os": ["linux"]},

    # ── Services & scheduling ────────────────────────────────────────────
    "service":              {"category": "services", "os": ["cross-platform"], "main": "service.running",
                             "summary": "Start, stop, restart, enable, and disable system services across systemd, sysvinit, upstart, launchd, and Windows."},
    "cron":                 {"category": "services", "os": ["cross-platform"], "main": "cron.present",
                             "summary": "Add and remove cron jobs declaratively — full crontab management plus individual entries."},
    "schedule":             {"category": "services", "os": ["cross-platform"], "main": "schedule.present",
                             "summary": "Manage Salt's own scheduler — recurring jobs that run on the minion without needing system cron."},
    "beacon":               {"category": "services", "os": ["cross-platform"], "main": "beacon.present",
                             "summary": "Configure Salt beacons — minion-side watchers that emit events on file/process/inotify/log changes."},
    "event":                {"category": "services", "os": ["cross-platform"], "main": "event.send",
                             "summary": "Fire arbitrary events into Salt's event bus from inside a state run — useful for triggering reactors."},
    "process":              {"category": "services", "os": ["cross-platform"]},
    "loop":                 {"category": "services", "os": ["cross-platform"]},
    "at":                   {"category": "services", "os": ["linux"]},

    # ── Networking & firewalls ───────────────────────────────────────────
    "host":                 {"category": "networking", "os": ["cross-platform"], "main": "host.present",
                             "summary": "Add and remove entries in /etc/hosts (and the Windows hosts file)."},
    "network":              {"category": "networking", "os": ["cross-platform"], "main": "network.managed",
                             "summary": "Configure network interfaces — RHEL ifcfg, Debian /etc/network/interfaces, and Windows network adapters."},
    "ntp":                  {"category": "networking", "os": ["cross-platform"], "main": "ntp.managed",
                             "summary": "Manage NTP servers and clients — set the active time source on the minion."},
    "iptables":             {"category": "networking", "os": ["linux"], "main": "iptables.append",
                             "summary": "Manage Linux iptables firewall rules — chains, rules, policies, persistence."},
    "firewalld":            {"category": "networking", "os": ["linux"], "main": "firewalld.present",
                             "summary": "Manage firewalld zones, services, and rules on RHEL/CentOS/Fedora — the modern replacement for raw iptables on those distros."},
    "firewall":             {"category": "networking", "os": ["cross-platform"]},
    "nftables":             {"category": "networking", "os": ["linux"]},
    "ipset":                {"category": "networking", "os": ["linux"]},
    "http":                 {"category": "networking", "os": ["cross-platform"]},
    "win_firewall":         {"category": "networking", "os": ["windows"]},
    "win_dns_client":       {"category": "networking", "os": ["windows"]},
    "win_network":          {"category": "networking", "os": ["windows"]},
    "win_smtp_server":      {"category": "networking", "os": ["windows"]},
    "win_snmp":             {"category": "networking", "os": ["windows"]},
    "netacl":               {"category": "networking", "os": ["network-device"], "main": "netacl.managed",
                             "summary": "Push firewall ACL config to network devices (Cisco, Juniper, etc.) via NAPALM, generated by Capirca."},
    "netconfig":            {"category": "networking", "os": ["network-device"]},
    "netntp":               {"category": "networking", "os": ["network-device"]},
    "netsnmp":              {"category": "networking", "os": ["network-device"]},
    "netusers":             {"category": "networking", "os": ["network-device"]},

    # ── Users, auth, certificates, ACLs ──────────────────────────────────
    "user":                 {"category": "auth", "os": ["cross-platform"], "main": "user.present",
                             "summary": "Create, modify, and remove local user accounts — uid/gid, groups, home, shell, password."},
    "group":                {"category": "auth", "os": ["cross-platform"], "main": "group.present",
                             "summary": "Manage local groups and their membership."},
    "ssh_auth":             {"category": "auth", "os": ["cross-platform"], "main": "ssh_auth.present",
                             "summary": "Manage entries in users' ~/.ssh/authorized_keys files."},
    "ssh_known_hosts":      {"category": "auth", "os": ["cross-platform"], "main": "ssh_known_hosts.present",
                             "summary": "Manage entries in users' ~/.ssh/known_hosts files — fingerprint pinning for SSH peers."},
    "ssh_pki":              {"category": "auth", "os": ["cross-platform"]},
    "gpg":                  {"category": "auth", "os": ["cross-platform"], "main": "gpg.present",
                             "summary": "Manage GnuPG keypairs in keyrings — import, trust, sign. The same GPG you use to encrypt pillar."},
    "x509":                 {"category": "auth", "os": ["cross-platform"], "main": "x509.certificate_managed",
                             "summary": "Legacy X.509 PKI module — generate keys, CSRs, sign against a Salt-managed CA. Prefer x509_v2 for new work."},
    "x509_v2":              {"category": "auth", "os": ["cross-platform"], "main": "x509_v2.certificate_managed",
                             "summary": "Modern X.509 PKI module — generate keys, CSRs, sign against a Salt-managed CA. Use this over x509 for new work."},
    "tls":                  {"category": "auth", "os": ["cross-platform"]},
    "linux_acl":            {"category": "auth", "os": ["linux"]},
    "selinux":              {"category": "auth", "os": ["linux"]},
    "win_dacl":             {"category": "auth", "os": ["windows"]},
    "win_lgpo":             {"category": "auth", "os": ["windows"]},
    "win_lgpo_reg":         {"category": "auth", "os": ["windows"]},
    "win_pki":              {"category": "auth", "os": ["windows"]},
    "win_certutil":         {"category": "auth", "os": ["windows"]},
    "mac_keychain":         {"category": "auth", "os": ["mac"]},
    "mac_assistive":        {"category": "auth", "os": ["mac"]},

    # ── Web servers, databases, message brokers ─────────────────────────
    "apache":               {"category": "data", "os": ["linux"]},
    "apache_conf":          {"category": "data", "os": ["linux"]},
    "apache_module":        {"category": "data", "os": ["linux"]},
    "apache_site":          {"category": "data", "os": ["linux"]},
    "win_iis":              {"category": "data", "os": ["windows"]},
    "postgres_database":    {"category": "data", "os": ["cross-platform"], "main": "postgres_database.present",
                             "summary": "Create, drop, and configure PostgreSQL databases."},
    "postgres_user":        {"category": "data", "os": ["cross-platform"], "main": "postgres_user.present",
                             "summary": "Manage PostgreSQL user accounts (roles), passwords, and login privileges."},
    "postgres_cluster":     {"category": "data", "os": ["cross-platform"]},
    "postgres_extension":   {"category": "data", "os": ["cross-platform"]},
    "postgres_group":       {"category": "data", "os": ["cross-platform"]},
    "postgres_initdb":      {"category": "data", "os": ["cross-platform"]},
    "postgres_language":    {"category": "data", "os": ["cross-platform"]},
    "postgres_privileges":  {"category": "data", "os": ["cross-platform"]},
    "postgres_schema":      {"category": "data", "os": ["cross-platform"]},
    "postgres_tablespace":  {"category": "data", "os": ["cross-platform"]},
    "rabbitmq_user":        {"category": "data", "os": ["cross-platform"], "main": "rabbitmq_user.present",
                             "summary": "Manage RabbitMQ user accounts, passwords, tags, and permissions."},
    "rabbitmq_vhost":       {"category": "data", "os": ["cross-platform"], "main": "rabbitmq_vhost.present",
                             "summary": "Manage RabbitMQ virtual hosts — the namespace boundary for exchanges, queues, and bindings."},
    "rabbitmq_cluster":     {"category": "data", "os": ["cross-platform"]},
    "rabbitmq_plugin":      {"category": "data", "os": ["cross-platform"]},
    "rabbitmq_policy":      {"category": "data", "os": ["cross-platform"]},
    "rabbitmq_upstream":    {"category": "data", "os": ["cross-platform"]},

    # ── System config & tuning ───────────────────────────────────────────
    "sysctl":               {"category": "sysconfig", "os": ["linux"], "main": "sysctl.present",
                             "summary": "Manage kernel parameters via sysctl — runtime + /etc/sysctl.conf for boot persistence."},
    "timezone":             {"category": "sysconfig", "os": ["cross-platform"], "main": "timezone.system",
                             "summary": "Set the system timezone."},
    "logrotate":            {"category": "sysconfig", "os": ["linux"], "main": "logrotate.set",
                             "summary": "Manage logrotate config files — keep services from filling disks with their own logs."},
    "alias":                {"category": "sysconfig", "os": ["cross-platform"]},
    "environ":              {"category": "sysconfig", "os": ["cross-platform"]},
    "grains":               {"category": "sysconfig", "os": ["cross-platform"]},
    "keyboard":             {"category": "sysconfig", "os": ["linux"]},
    "kmod":                 {"category": "sysconfig", "os": ["linux"]},
    "locale":               {"category": "sysconfig", "os": ["cross-platform"]},
    "proxy":                {"category": "sysconfig", "os": ["cross-platform"]},
    "reg":                  {"category": "sysconfig", "os": ["windows"], "main": "reg.present",
                             "summary": "Manage Windows registry keys and values — the Windows answer to /etc."},
    "syslog_ng":            {"category": "sysconfig", "os": ["linux"]},
    "macdefaults":          {"category": "sysconfig", "os": ["mac"], "main": "macdefaults.write",
                             "summary": "Write/read entries from macOS user defaults (the `defaults` system) — per-app preferences as state."},
    "mac_xattr":            {"category": "sysconfig", "os": ["mac"]},
    "win_path":             {"category": "sysconfig", "os": ["windows"]},
    "win_powercfg":         {"category": "sysconfig", "os": ["windows"]},
    "win_system":           {"category": "sysconfig", "os": ["windows"]},
    "win_task":             {"category": "sysconfig", "os": ["windows"]},
    "win_shortcut":         {"category": "sysconfig", "os": ["windows"]},
    "win_license":          {"category": "sysconfig", "os": ["windows"]},

    # ── Salt-on-Salt, orchestration, meta ────────────────────────────────
    "saltmod":              {"category": "salt-meta", "os": ["cross-platform"], "main": "salt.state",
                             "summary": "Run Salt commands across the fleet from inside a state — orchestration glue for sequencing changes across many minions."},
    "cmd":                  {"category": "salt-meta", "os": ["cross-platform"], "main": "cmd.run",
                             "summary": "Run shell commands — only when something has changed (cmd.run with onchanges) or unconditionally (cmd.wait)."},
    "module":               {"category": "salt-meta", "os": ["cross-platform"], "main": "module.run",
                             "summary": "Call any Salt execution module function from inside a state — escape hatch for things without dedicated state coverage."},
    "saltutil":             {"category": "salt-meta", "os": ["cross-platform"]},
    "salt_proxy":           {"category": "salt-meta", "os": ["cross-platform"]},
    "stateconf":            {"category": "salt-meta", "os": ["cross-platform"]},
    "ansiblegate":          {"category": "salt-meta", "os": ["cross-platform"]},
    "idem":                 {"category": "salt-meta", "os": ["cross-platform"]},
    "cloud":                {"category": "salt-meta", "os": ["cross-platform"]},
    "etcd_mod":             {"category": "salt-meta", "os": ["cross-platform"]},
    "highstate_doc":        {"category": "salt-meta", "os": ["cross-platform"]},
    "test":                 {"category": "salt-meta", "os": ["cross-platform"]},
    "status":               {"category": "salt-meta", "os": ["cross-platform"]},

    # ── Monitoring (one in core; rest are extensions) ────────────────────
    "uptime":               {"category": "monitoring", "os": ["cross-platform"]},
}

# Curated extension modules — modules that ship in saltext-* packages, not in
# the core Salt repo. We don't have their source locally, so we only ship a
# name + 1-line summary + link to the official docs.
# Format: (name, category, os, summary)
EXTENSIONS = []  # All saltext-* extensions removed; master docs scope only.


def extract_module(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    module_doc = ast.get_docstring(tree) or ""

    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append({
                "name": node.name,
                "signature": format_signature(node),
            })

    examples = extract_yaml_blocks(module_doc)

    return {
        "name": path.stem,
        "filename": path.name,
        "doc_first_line": first_sentence(module_doc),
        "functions": functions,
        "examples": examples[:2],
        "docs_url": DOC_URL.format(name=path.stem),
    }


def format_signature(node: ast.FunctionDef) -> str:
    args = node.args
    parts = []
    pos_total = len(args.args)
    defaults_total = len(args.defaults)
    pos_defaults_start = pos_total - defaults_total
    for i, a in enumerate(args.args):
        if i >= pos_defaults_start:
            d = args.defaults[i - pos_defaults_start]
            parts.append(f"{a.arg}={ast.unparse(d)}")
        else:
            parts.append(a.arg)
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    for i, a in enumerate(args.kwonlyargs):
        kd = args.kw_defaults[i]
        if kd is not None:
            parts.append(f"{a.arg}={ast.unparse(kd)}")
        else:
            parts.append(a.arg)
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return f"({', '.join(parts)})"


def extract_yaml_blocks(doc: str) -> list:
    """Pull out RST `.. code-block:: yaml` snippets, dedented and trimmed."""
    pattern = re.compile(
        r'\.\. code-block::\s*yaml\s*\n((?:[ \t]*\n)*)((?:[ \t]+[^\n]*\n?)+)',
        re.MULTILINE
    )
    blocks = []
    for m in pattern.finditer(doc):
        block = m.group(2)
        lines = block.splitlines()
        non_empty = [l for l in lines if l.strip()]
        if not non_empty:
            continue
        common = min(len(l) - len(l.lstrip()) for l in non_empty)
        dedented = "\n".join(l[common:] if l.strip() else "" for l in lines)
        blocks.append(dedented.rstrip())
    return blocks


def first_sentence(doc: str) -> str:
    """Best-effort first sentence, skipping RST title underlines."""
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    content = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if content:
                break
            continue
        if re.match(r'^[=\-~^"\'+#`*]+$', stripped):
            continue
        content.append(stripped)
    text = " ".join(content)
    m = re.match(r'(.+?[.!?])(\s|$)', text)
    return m.group(1) if m else text[:160]


def main():
    out_path = Path(__file__).resolve().parent.parent / "data" / "salt-states.json"
    out_path.parent.mkdir(exist_ok=True)

    if not SALT_REPO.exists():
        print(f"!! Salt repo not found at {SALT_REPO}", file=sys.stderr)
        sys.exit(1)

    modules = []
    for py in sorted(SALT_REPO.glob("*.py")):
        if py.stem == "__init__":
            continue
        try:
            data = extract_module(py)
        except Exception as e:
            print(f"!! {py.name}: {e}", file=sys.stderr)
            continue

        cur = CURATION.get(py.stem)
        if cur:
            data["category"] = cur["category"]
            data["os"] = cur["os"]
            data["summary"] = cur.get("summary") or data["doc_first_line"] or "(No description available.)"
            data["main"] = cur.get("main") or (
                f"{py.stem}.{data['functions'][0]['name']}" if data["functions"] else py.stem
            )
        else:
            data["category"] = "uncategorized"
            data["os"] = ["unknown"]
            data["summary"] = data["doc_first_line"] or "(No description available.)"
            data["main"] = data["functions"][0]["name"] if data["functions"] else ""
            data["main"] = f"{py.stem}.{data['main']}" if data["main"] else ""

        modules.append(data)

    # Extensions list is empty in the master-scope build — see EXTENSIONS = []
    # at the top of this file. The 233 historical entries were removed when
    # the Salt project moved them out of the main docs into saltext-* packages.
    extensions = []

    output = {
        "categories": CATEGORIES,
        "modules": modules,
        "extensions": extensions,
        "stats": {
            "core_total": len(modules),
            "core_curated": sum(1 for m in modules if m["category"] != "uncategorized"),
            "extensions_total": len(extensions),
        },
    }

    out_path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {out_path}")
    print(f"  core modules: {output['stats']['core_total']} total, "
          f"{output['stats']['core_curated']} curated")
    print(f"  extensions:   {output['stats']['extensions_total']}")


if __name__ == "__main__":
    main()
