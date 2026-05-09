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
DOC_URL = "https://docs.saltproject.io/en/3006/ref/states/all/salt.states.{name}.html"

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
     "blurb": "Apache, IIS, PostgreSQL, RabbitMQ — and the long-tail database/MQ extensions."},
    {"id": "sysconfig",    "label": "System config & tuning",
     "blurb": "sysctl, environment variables, locale, timezone, kernel modules, log rotation, Windows tasks."},
    {"id": "salt-meta",    "label": "Salt-on-Salt, orchestration, meta",
     "blurb": "Cross-minion orchestration, calling other configuration tools (Ansible, idem), and stateconf glue."},
    {"id": "cloud",        "label": "Cloud platforms",
     "blurb": "AWS (boto), Azure ARM, libcloud, F5 BIG-IP — provision and manage cloud-native resources."},
    {"id": "containers",   "label": "Containers & VMs",
     "blurb": "Docker, LXD — declarative container and lightweight VM lifecycle."},
    {"id": "monitoring",   "label": "Monitoring & observability",
     "blurb": "Zabbix, Grafana, PagerDuty, Splunk — define alerts, dashboards, and on-call routing as code."},
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
EXTENSIONS = [
    # ── Cloud platforms — AWS (boto / boto3) ─────────────────────────────
    ("boto_apigateway",         "cloud", ["cross-platform"], "Manage AWS API Gateway REST APIs, deployments, stages, and resources."),
    ("boto_asg",                "cloud", ["cross-platform"], "Manage AWS Auto Scaling Groups, launch configs, scheduled actions."),
    ("boto_cfn",                "cloud", ["cross-platform"], "Deploy and manage AWS CloudFormation stacks."),
    ("boto_cloudfront",         "cloud", ["cross-platform"], "Manage AWS CloudFront CDN distributions."),
    ("boto_cloudtrail",         "cloud", ["cross-platform"], "Manage AWS CloudTrail audit logging trails."),
    ("boto_cloudwatch_alarm",   "cloud", ["cross-platform"], "Manage AWS CloudWatch metric alarms."),
    ("boto_cloudwatch_event",   "cloud", ["cross-platform"], "Manage AWS CloudWatch Events rules and targets."),
    ("boto_cognitoidentity",    "cloud", ["cross-platform"], "Manage AWS Cognito identity pools."),
    ("boto_datapipeline",       "cloud", ["cross-platform"], "Manage AWS Data Pipeline definitions."),
    ("boto_dynamodb",           "cloud", ["cross-platform"], "Manage AWS DynamoDB tables, indexes, and capacity."),
    ("boto_ec2",                "cloud", ["cross-platform"], "Manage AWS EC2 instances, key pairs, EIPs, and snapshots."),
    ("boto_elasticache",        "cloud", ["cross-platform"], "Manage AWS ElastiCache clusters, subnet groups, and parameter groups."),
    ("boto_elasticsearch_domain","cloud", ["cross-platform"], "Manage AWS Elasticsearch (now OpenSearch) domains."),
    ("boto_elb",                "cloud", ["cross-platform"], "Manage AWS Classic Elastic Load Balancers."),
    ("boto_elbv2",              "cloud", ["cross-platform"], "Manage AWS Application and Network Load Balancers (ELBv2)."),
    ("boto_iam",                "cloud", ["cross-platform"], "Manage AWS IAM users, groups, policies, and access keys."),
    ("boto_iam_role",           "cloud", ["cross-platform"], "Manage AWS IAM roles and their attached policies."),
    ("boto_iot",                "cloud", ["cross-platform"], "Manage AWS IoT things, policies, and topic rules."),
    ("boto_kinesis",            "cloud", ["cross-platform"], "Manage AWS Kinesis data streams."),
    ("boto_kms",                "cloud", ["cross-platform"], "Manage AWS KMS encryption keys and key policies."),
    ("boto_lambda",             "cloud", ["cross-platform"], "Deploy and manage AWS Lambda functions, aliases, and triggers."),
    ("boto_lc",                 "cloud", ["cross-platform"], "Manage AWS Auto Scaling launch configurations."),
    ("boto_rds",                "cloud", ["cross-platform"], "Manage AWS RDS database instances, subnet groups, and parameter groups."),
    ("boto_route53",            "cloud", ["cross-platform"], "Manage AWS Route53 DNS hosted zones and record sets."),
    ("boto_s3",                 "cloud", ["cross-platform"], "Manage AWS S3 object state at the file level."),
    ("boto_s3_bucket",          "cloud", ["cross-platform"], "Manage AWS S3 buckets — policy, lifecycle, versioning, encryption."),
    ("boto_secgroup",           "cloud", ["cross-platform"], "Manage AWS EC2 security groups and ingress/egress rules."),
    ("boto_sns",                "cloud", ["cross-platform"], "Manage AWS SNS topics and subscriptions."),
    ("boto_sqs",                "cloud", ["cross-platform"], "Manage AWS SQS queues and policies."),
    ("boto_vpc",                "cloud", ["cross-platform"], "Manage AWS VPCs, subnets, route tables, and network ACLs."),
    ("boto3_elasticache",       "cloud", ["cross-platform"], "Manage AWS ElastiCache resources via boto3."),
    ("boto3_elasticsearch",     "cloud", ["cross-platform"], "Manage AWS Elasticsearch domains via boto3."),
    ("boto3_route53",           "cloud", ["cross-platform"], "Manage AWS Route53 zones and records via boto3."),
    ("boto3_sns",               "cloud", ["cross-platform"], "Manage AWS SNS topics and subscriptions via boto3."),
    ("aws_sqs",                 "cloud", ["cross-platform"], "Manage AWS SQS queues (legacy module — boto_sqs is preferred for new work)."),

    # ── Cloud platforms — Azure ─────────────────────────────────────────
    ("azurearm_compute",        "cloud", ["cross-platform"], "Manage Azure VMs, scale sets, and availability sets via Azure Resource Manager."),
    ("azurearm_dns",            "cloud", ["cross-platform"], "Manage Azure DNS zones and record sets."),
    ("azurearm_network",        "cloud", ["cross-platform"], "Manage Azure VNets, subnets, NICs, and network security groups."),
    ("azurearm_resource",       "cloud", ["cross-platform"], "Manage Azure Resource Groups and template-based deployments."),

    # ── Cloud platforms — OpenStack ──────────────────────────────────────
    ("keystone",                "cloud", ["cross-platform"], "Manage OpenStack Keystone identity service — projects, roles, services."),
    ("keystone_domain",         "cloud", ["cross-platform"], "Manage OpenStack Keystone domains."),
    ("keystone_endpoint",       "cloud", ["cross-platform"], "Manage OpenStack Keystone service endpoints."),
    ("keystone_group",          "cloud", ["cross-platform"], "Manage OpenStack Keystone groups."),
    ("keystone_project",        "cloud", ["cross-platform"], "Manage OpenStack Keystone projects (formerly tenants)."),
    ("keystone_role",           "cloud", ["cross-platform"], "Manage OpenStack Keystone roles."),
    ("keystone_role_grant",     "cloud", ["cross-platform"], "Grant OpenStack Keystone roles to users on projects."),
    ("keystone_service",        "cloud", ["cross-platform"], "Register OpenStack Keystone services."),
    ("keystone_user",           "cloud", ["cross-platform"], "Manage OpenStack Keystone users."),
    ("neutron_network",         "cloud", ["cross-platform"], "Manage OpenStack Neutron networks."),
    ("neutron_secgroup",        "cloud", ["cross-platform"], "Manage OpenStack Neutron security groups."),
    ("neutron_secgroup_rule",   "cloud", ["cross-platform"], "Manage OpenStack Neutron security group rules."),
    ("neutron_subnet",          "cloud", ["cross-platform"], "Manage OpenStack Neutron subnets."),
    ("glance_image",            "cloud", ["cross-platform"], "Manage OpenStack Glance VM images."),
    ("heat",                    "cloud", ["cross-platform"], "Manage OpenStack Heat orchestration stacks."),
    ("openstack_config",        "cloud", ["cross-platform"], "Manage OpenStack service configuration files."),

    # ── Cloud platforms — other ──────────────────────────────────────────
    ("libcloud_dns",            "cloud", ["cross-platform"], "Manage DNS records across many providers via Apache libcloud."),
    ("libcloud_loadbalancer",   "cloud", ["cross-platform"], "Manage load balancers across many providers via Apache libcloud."),
    ("libcloud_storage",        "cloud", ["cross-platform"], "Manage object storage across many providers via Apache libcloud."),
    ("bigip",                   "cloud", ["cross-platform"], "Manage F5 BIG-IP load balancer config — virtual servers, pools, monitors."),
    ("pyrax_queues",            "cloud", ["cross-platform"], "Manage Rackspace Cloud Queues."),

    # ── Containers & VMs ─────────────────────────────────────────────────
    ("docker_container",        "containers", ["cross-platform"], "Manage Docker containers — start, stop, recreate-on-change with image/env/volume drift detection."),
    ("docker_image",            "containers", ["cross-platform"], "Pull, build, tag, and remove Docker images."),
    ("docker_network",          "containers", ["cross-platform"], "Manage Docker networks and network connections."),
    ("docker_volume",           "containers", ["cross-platform"], "Manage Docker volumes."),
    ("lxd",                     "containers", ["linux"], "Manage LXD daemon configuration."),
    ("lxd_container",           "containers", ["linux"], "Manage LXD system containers."),
    ("lxd_image",               "containers", ["linux"], "Manage LXD container images."),
    ("lxd_profile",             "containers", ["linux"], "Manage LXD profiles — shared config applied to multiple containers."),
    ("lxc",                     "containers", ["linux"], "Manage Linux Containers (LXC) — predecessor to LXD."),
    ("virt",                    "containers", ["linux"], "Manage libvirt-backed virtual machines (KVM/QEMU)."),
    ("kubernetes",              "containers", ["cross-platform"], "Manage Kubernetes resources — namespaces, deployments, services, secrets."),
    ("helm",                    "containers", ["cross-platform"], "Manage Helm chart releases on Kubernetes."),
    ("marathon_app",            "containers", ["cross-platform"], "Manage app definitions on Mesos Marathon."),
    ("chronos_job",             "containers", ["cross-platform"], "Manage scheduled jobs on Mesos Chronos."),
    ("vbox_guest",              "containers", ["cross-platform"], "Install VirtualBox guest additions inside a VM."),
    ("vagrant",                 "containers", ["cross-platform"], "Manage Vagrant VMs from Salt."),
    ("esxi",                    "containers", ["cross-platform"], "Manage VMware ESXi host configuration."),
    ("esxcluster",              "containers", ["cross-platform"], "Manage VMware vSphere clusters."),
    ("esxdatacenter",           "containers", ["cross-platform"], "Manage VMware vSphere datacenters."),
    ("esxvm",                   "containers", ["cross-platform"], "Manage VMware ESXi virtual machines."),
    ("dvs",                     "containers", ["cross-platform"], "Manage VMware Distributed Virtual Switches."),

    # ── Monitoring & observability ───────────────────────────────────────
    ("zabbix_action",           "monitoring", ["cross-platform"], "Manage Zabbix actions — alerts and remote command triggers."),
    ("zabbix_host",             "monitoring", ["cross-platform"], "Register and configure hosts in Zabbix."),
    ("zabbix_hostgroup",        "monitoring", ["cross-platform"], "Manage Zabbix host groups."),
    ("zabbix_mediatype",        "monitoring", ["cross-platform"], "Manage Zabbix media types — email, SMS, webhooks for alerts."),
    ("zabbix_template",         "monitoring", ["cross-platform"], "Import and manage Zabbix monitoring templates."),
    ("zabbix_user",             "monitoring", ["cross-platform"], "Manage Zabbix front-end user accounts."),
    ("zabbix_usergroup",        "monitoring", ["cross-platform"], "Manage Zabbix user groups."),
    ("zabbix_usermacro",        "monitoring", ["cross-platform"], "Manage Zabbix user-level macros (config substitution)."),
    ("zabbix_valuemap",         "monitoring", ["cross-platform"], "Manage Zabbix value maps — translate raw metric values to human labels."),
    ("grafana",                 "monitoring", ["cross-platform"], "Generic Grafana state — overarching alias used by older configs."),
    ("grafana_datasource",      "monitoring", ["cross-platform"], "Manage Grafana data sources."),
    ("grafana_dashboard",       "monitoring", ["cross-platform"], "Push Grafana dashboards as JSON."),
    ("grafana4_datasource",     "monitoring", ["cross-platform"], "Manage Grafana 4.x data sources."),
    ("grafana4_dashboard",      "monitoring", ["cross-platform"], "Manage Grafana 4.x dashboards."),
    ("grafana4_org",            "monitoring", ["cross-platform"], "Manage Grafana 4.x organizations."),
    ("grafana4_user",           "monitoring", ["cross-platform"], "Manage Grafana 4.x users."),
    ("pagerduty",               "monitoring", ["cross-platform"], "Send incident notifications to PagerDuty."),
    ("pagerduty_escalation_policy", "monitoring", ["cross-platform"], "Manage PagerDuty escalation policies."),
    ("pagerduty_schedule",      "monitoring", ["cross-platform"], "Manage PagerDuty on-call schedules."),
    ("pagerduty_service",       "monitoring", ["cross-platform"], "Manage PagerDuty services (alert routing endpoints)."),
    ("pagerduty_user",          "monitoring", ["cross-platform"], "Manage PagerDuty users."),
    ("splunk",                  "monitoring", ["cross-platform"], "Send log events to Splunk."),
    ("splunk_search",           "monitoring", ["cross-platform"], "Manage saved Splunk searches."),
    ("monit",                   "monitoring", ["linux"], "Manage Monit process supervision config."),
    ("icinga2",                 "monitoring", ["linux"], "Manage Icinga2 monitoring config — hosts, services, templates."),
    ("kapacitor",               "monitoring", ["cross-platform"], "Manage Kapacitor stream/batch processing tasks for InfluxDB."),
    ("telemetry_alert",         "monitoring", ["cross-platform"], "Configure alerts in the Telemetry monitoring service."),
    ("victorops",               "monitoring", ["cross-platform"], "Send alerts to VictorOps incident management."),
    ("opsgenie",                "monitoring", ["cross-platform"], "Send alerts to Opsgenie."),
    ("ifttt",                   "monitoring", ["cross-platform"], "Trigger IFTTT applets from Salt events."),
    ("pushover",                "monitoring", ["cross-platform"], "Send push notifications via Pushover."),
    ("statuspage",              "monitoring", ["cross-platform"], "Manage Atlassian Statuspage components and incidents."),
    ("slack",                   "monitoring", ["cross-platform"], "Send messages to Slack channels — handy for state-run notifications."),
    ("msteams",                 "monitoring", ["cross-platform"], "Send messages to Microsoft Teams channels."),
    ("xmpp",                    "monitoring", ["cross-platform"], "Send messages over XMPP (Jabber)."),
    ("smtp",                    "monitoring", ["cross-platform"], "Send email notifications via SMTP."),
    ("github",                  "monitoring", ["cross-platform"], "Manage GitHub repos, teams, and members."),
    ("zenoss",                  "monitoring", ["cross-platform"], "Manage devices in the Zenoss monitoring platform."),
    ("serverdensity_device",    "monitoring", ["cross-platform"], "Register devices with ServerDensity (now StackPath)."),
    ("probes",                  "monitoring", ["cross-platform"], "Define network device probes (ping/traceroute/etc.) via NAPALM/probes_."),
    ("testinframod",            "monitoring", ["cross-platform"], "Run testinfra-style infrastructure tests as part of state runs."),

    # ── Networking — additions ───────────────────────────────────────────
    ("net_napalm_yang",         "networking", ["network-device"], "Push YANG-modelled config to network devices via NAPALM."),
    ("nxos",                    "networking", ["network-device"], "Manage Cisco Nexus switches via NX-OS API."),
    ("nxos_upgrade",            "networking", ["network-device"], "Run controlled NX-OS image upgrades on Cisco Nexus."),
    ("junos",                   "networking", ["network-device"], "Manage Juniper devices via NETCONF (Junos PyEZ)."),
    ("panos",                   "networking", ["network-device"], "Manage Palo Alto Networks firewalls via PAN-OS XML API."),
    ("restconf",                "networking", ["network-device"], "Manage network device config via the RESTCONF protocol."),
    ("cisconso",                "networking", ["network-device"], "Manage devices via Cisco Network Services Orchestrator."),
    ("cimc",                    "networking", ["network-device"], "Manage Cisco UCS C-Series via the Integrated Management Controller."),
    ("openvswitch_bridge",      "networking", ["linux"], "Manage Open vSwitch bridges."),
    ("openvswitch_db",          "networking", ["linux"], "Manage Open vSwitch database records."),
    ("openvswitch_port",        "networking", ["linux"], "Manage Open vSwitch ports and tags."),
    ("modjk",                   "networking", ["linux"], "Manage mod_jk Apache → Tomcat connector worker config."),
    ("modjk_worker",            "networking", ["linux"], "Manage individual mod_jk worker definitions."),
    ("lvs_server",              "networking", ["linux"], "Manage Linux Virtual Server backend servers."),
    ("lvs_service",             "networking", ["linux"], "Manage Linux Virtual Server virtual services."),
    ("ethtool",                 "networking", ["linux"], "Manage NIC settings via ethtool — speed, duplex, offload features."),
    ("ddns",                    "networking", ["cross-platform"], "Update DNS records via dynamic DNS (RFC 2136)."),
    ("infoblox_a",              "networking", ["cross-platform"], "Manage A records in Infoblox DDI."),
    ("infoblox_cname",          "networking", ["cross-platform"], "Manage CNAME records in Infoblox DDI."),
    ("infoblox_host_record",    "networking", ["cross-platform"], "Manage host records in Infoblox DDI."),
    ("infoblox_range",          "networking", ["cross-platform"], "Manage IP address ranges in Infoblox DDI."),
    ("csf",                     "networking", ["linux"], "Manage ConfigServer Security & Firewall (CSF) rules."),

    # ── Hardware management ─ kept under sysconfig ────────────────────────
    ("dellchassis",             "sysconfig", ["cross-platform"], "Manage Dell PowerEdge chassis (CMC) via WSMAN/RACADM."),
    ("drac",                    "sysconfig", ["cross-platform"], "Manage Dell iDRAC remote management controllers."),
    ("ipmi",                    "sysconfig", ["cross-platform"], "Manage IPMI-controlled hardware (BMC) — boot device, power state, BIOS."),
    ("powerpath",               "sysconfig", ["linux"], "Manage EMC PowerPath storage multipath licensing/state."),

    # ── Auth additions ───────────────────────────────────────────────────
    ("ldap",                    "auth", ["cross-platform"], "Manage LDAP entries declaratively."),
    ("vault",                   "auth", ["cross-platform"], "Manage HashiCorp Vault policies and secrets."),
    ("pdbedit",                 "auth", ["linux"], "Manage Samba's local user/password database (pdbedit)."),
    ("keystore",                "auth", ["cross-platform"], "Manage entries in Java keystores."),
    ("rbac_solaris",            "auth", ["cross-platform"], "Manage Solaris RBAC profiles, roles, and authorizations."),
    ("acme",                    "auth", ["cross-platform"], "Issue and renew TLS certificates via ACME (Let's Encrypt and friends)."),
    ("cryptdev",                "auth", ["linux"], "Manage encrypted block devices in /etc/crypttab — LUKS-style disk encryption."),

    # ── Web servers, databases, message brokers — additions ──────────────
    ("mysql_database",          "data", ["cross-platform"], "Manage MySQL/MariaDB databases."),
    ("mysql_grants",            "data", ["cross-platform"], "Manage MySQL/MariaDB user privileges."),
    ("mysql_query",             "data", ["cross-platform"], "Run arbitrary SQL on MySQL/MariaDB as a state."),
    ("mysql_user",              "data", ["cross-platform"], "Manage MySQL/MariaDB user accounts."),
    ("mssql_database",          "data", ["windows"], "Manage Microsoft SQL Server databases."),
    ("mssql_login",             "data", ["windows"], "Manage MSSQL server logins."),
    ("mssql_role",              "data", ["windows"], "Manage MSSQL roles."),
    ("mssql_user",              "data", ["windows"], "Manage MSSQL database-level users."),
    ("mongodb_database",        "data", ["cross-platform"], "Manage MongoDB databases."),
    ("mongodb_user",            "data", ["cross-platform"], "Manage MongoDB user accounts."),
    ("elasticsearch",           "data", ["cross-platform"], "Manage Elasticsearch clusters at a high level (settings, snapshots)."),
    ("elasticsearch_index",     "data", ["cross-platform"], "Manage individual Elasticsearch indexes."),
    ("elasticsearch_index_template", "data", ["cross-platform"], "Manage Elasticsearch index templates."),
    ("influxdb_database",       "data", ["cross-platform"], "Manage InfluxDB databases."),
    ("influxdb_retention_policy","data", ["cross-platform"], "Manage InfluxDB retention policies."),
    ("influxdb_continuous_query","data", ["cross-platform"], "Manage InfluxDB continuous queries."),
    ("influxdb_user",           "data", ["cross-platform"], "Manage InfluxDB users and grants."),
    ("influxdb08_database",     "data", ["cross-platform"], "Manage InfluxDB 0.8.x databases (legacy)."),
    ("influxdb08_user",         "data", ["cross-platform"], "Manage InfluxDB 0.8.x users (legacy)."),
    ("redismod",                "data", ["cross-platform"], "Manage Redis keys and config (Salt's Redis state — module is named redismod to avoid clashing with `redis` execution module)."),
    ("sqlite3",                 "data", ["cross-platform"], "Manage SQLite databases — schema, tables, and rows."),
    ("memcached",               "data", ["cross-platform"], "Manage Memcached entries from state."),
    ("zookeeper",               "data", ["cross-platform"], "Manage ZooKeeper znodes."),
    ("solrcloud",               "data", ["cross-platform"], "Manage Apache Solr cloud collections and configs."),
    ("tomcat",                  "data", ["cross-platform"], "Deploy and manage Apache Tomcat web apps (.war files)."),
    ("jboss7",                  "data", ["cross-platform"], "Deploy apps and config to JBoss/WildFly 7+."),
    ("glassfish",               "data", ["cross-platform"], "Manage GlassFish/Payara Java EE app server resources."),
    ("jenkins",                 "data", ["cross-platform"], "Manage Jenkins CI server jobs and config."),
    ("wordpress",               "data", ["linux"], "Manage WordPress sites — plugins, themes, options."),
    ("supervisord",             "data", ["cross-platform"], "Manage processes under the supervisord process supervisor."),
    ("ceph",                    "data", ["linux"], "Manage Ceph storage cluster config."),
    ("pbm",                     "data", ["cross-platform"], "Manage Percona Backup for MongoDB (PBM)."),

    # ── Packages — additions ─────────────────────────────────────────────
    ("aptpkg",                  "packages", ["linux"], "Manage Debian/Ubuntu apt-pinning preferences and apt config."),
    ("alternatives",            "packages", ["linux"], "Manage update-alternatives selections (e.g., default editor, default Java)."),
    ("artifactory",             "packages", ["cross-platform"], "Pull artifacts from a JFrog Artifactory repository."),
    ("nexus",                   "packages", ["cross-platform"], "Pull artifacts from a Sonatype Nexus repository."),
    ("ports",                   "packages", ["freebsd"], "Manage FreeBSD ports compilation options."),
    ("portage_config",          "packages", ["linux"], "Manage Gentoo Portage package config — USE flags, keywords, masks."),
    ("layman",                  "packages", ["linux"], "Manage Gentoo Portage overlay repositories via layman."),
    ("npm",                     "packages", ["cross-platform"], "Install Node.js packages via npm — globally or into a project."),
    ("gem",                     "packages", ["cross-platform"], "Install Ruby gems."),
    ("bower",                   "packages", ["cross-platform"], "Install front-end packages via Bower (legacy — most projects have moved to npm)."),
    ("cabal",                   "packages", ["cross-platform"], "Install Haskell packages via Cabal."),
    ("composer",                "packages", ["cross-platform"], "Install PHP dependencies via Composer."),
    ("pecl",                    "packages", ["cross-platform"], "Install PHP extensions from PECL."),
    ("rvm",                     "packages", ["cross-platform"], "Manage Ruby installations and gemsets via RVM."),
    ("rbenv",                   "packages", ["cross-platform"], "Manage Ruby installations via rbenv."),
    ("cyg",                     "packages", ["windows"], "Install packages on Windows via Cygwin."),
    ("zcbuildout",              "packages", ["cross-platform"], "Run zc.buildout for Python projects."),
    ("virtualenv",              "packages", ["cross-platform"], "Manage Python virtual environments (alt to virtualenv_mod)."),
    ("kernelpkg",               "packages", ["linux"], "Manage Linux kernel package install + active kernel selection."),

    # ── Files & filesystems — additions ──────────────────────────────────
    ("zfs",                     "files", ["cross-platform"], "Manage ZFS datasets — properties, snapshots, mountpoints."),
    ("zpool",                   "files", ["cross-platform"], "Manage ZFS storage pools."),
    ("btrfs",                   "files", ["linux"], "Manage Btrfs subvolumes and properties."),
    ("glusterfs",               "files", ["linux"], "Manage GlusterFS distributed filesystem volumes."),
    ("snapper",                 "files", ["linux"], "Manage Btrfs/LVM snapshots via Snapper (SUSE's snapshot tool)."),
    ("nfs_export",              "files", ["linux"], "Manage NFS server export rules in /etc/exports."),
    ("xml",                     "files", ["cross-platform"], "Edit XML files — set element values and attributes."),
    ("rsync",                   "files", ["cross-platform"], "Run rsync as a state — sync directories with idempotency."),
    ("svn",                     "files", ["cross-platform"], "Manage Subversion working copy checkouts."),
    ("hg",                      "files", ["cross-platform"], "Manage Mercurial working copy checkouts."),
    ("incron",                  "files", ["linux"], "Manage incron entries — cron triggered by inotify file events."),
    ("logadm",                  "files", ["cross-platform"], "Manage Solaris log rotation via logadm."),
    # ── System config additions ──────────────────────────────────────────
    ("consul",                  "sysconfig", ["cross-platform"], "Manage HashiCorp Consul config and KV entries."),
    ("tuned",                   "sysconfig", ["linux"], "Manage RHEL/CentOS tuned profile selection."),
    ("gnomedesktop",            "sysconfig", ["linux"], "Manage GNOME desktop dconf settings."),
    ("sysrc",                   "sysconfig", ["freebsd"], "Manage FreeBSD /etc/rc.conf entries via sysrc."),
    ("debconfmod",              "sysconfig", ["linux"], "Set Debian debconf answers — pre-seed package config."),
    ("augeas",                  "sysconfig", ["linux"], "Edit config files in-place using Augeas lenses."),
    ("chef",                    "sysconfig", ["cross-platform"], "Run Chef client/solo from inside Salt — for hybrid environments."),
    ("rdp",                     "sysconfig", ["windows"], "Enable/disable Windows Remote Desktop."),
    ("pcs",                     "sysconfig", ["linux"], "Manage Pacemaker/Corosync HA cluster config via pcs."),
    ("eselect",                 "sysconfig", ["linux"], "Manage Gentoo eselect choices (e.g., active Java/Python alternatives)."),
    ("smartos",                 "sysconfig", ["cross-platform"], "Manage SmartOS global zone config and platform settings."),
    ("webutil",                 "sysconfig", ["linux"], "Manage Apache htpasswd-style password files via webutil."),

    # ── Salt-meta additions ──────────────────────────────────────────────
    ("trafficserver",           "salt-meta", ["linux"], "Manage Apache Traffic Server (HTTP cache/proxy)."),
    ("zone",                    "salt-meta", ["cross-platform"], "Manage Solaris zones."),
    ("zk_concurrency",          "salt-meta", ["cross-platform"], "Use ZooKeeper for cross-minion locking/leader election in state runs."),
]


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

    # Load cached extension examples (built by fetch-extension-examples.py)
    examples_cache = {}
    cache_path = Path(__file__).resolve().parent.parent / "data" / "salt-states-extension-examples.json"
    if cache_path.exists():
        examples_cache = json.loads(cache_path.read_text())

    extensions = [
        {
            "name": name,
            "category": cat,
            "os": oses,
            "summary": summary,
            "is_extension": True,
            "docs_url": DOC_URL.format(name=name),
            "examples": examples_cache.get(name, [])[:2],
        }
        for name, cat, oses, summary in EXTENSIONS
    ]

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
