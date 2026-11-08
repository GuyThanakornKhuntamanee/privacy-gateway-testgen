"""Synthetic infrastructure entity factories.

All networks, hosts and cloud resources are fictional.  IPv4 uses RFC 1918
space, IPv6 uses the ULA range, cloud account IDs are all zeroes, and internal
DNS names live under reserved ``.internal``/``.example`` names.
"""

from __future__ import annotations

import random

from ..models import Entity
from . import common


def _ipv4(rng: random.Random, ctx) -> Entity:
    return Entity("infrastructure", "internal_ipv4", f"10.{rng.choice([10, 20, 30, 40])}.{rng.randint(0, 20)}.{rng.randint(2, 250)}")


def _ipv6(rng: random.Random, ctx) -> Entity:
    return Entity(
        "infrastructure",
        "internal_ipv6",
        f"fd00:{common.hexstr(rng, 4)}:{common.hexstr(rng, 4)}::{common.hexstr(rng, 4)}",
    )


def _network(rng: random.Random, ctx) -> Entity:
    second = rng.choice([10, 20, 30, 40])
    return Entity("infrastructure", "private_network", f"10.{second}.0.0/16")


def _hostname(rng: random.Random, ctx) -> Entity:
    svc = rng.choice(common.SERVICES)
    return Entity(
        "infrastructure",
        "internal_hostname",
        f"{svc}-{rng.randint(1, 24):02d}.{ctx.org['slug']}.internal",
    )


def _dns(rng: random.Random, ctx) -> Entity:
    svc = rng.choice(common.SERVICES)
    return Entity(
        "infrastructure",
        "internal_dns_name",
        f"{svc}.svc.{ctx.org['slug']}.internal",
    )


def _url(rng: random.Random, ctx) -> Entity:
    svc = rng.choice(common.SERVICES)
    path = rng.choice(["api/v1/orders", "api/v2/customers", "health", "admin/metrics", "internal/report"])
    return Entity(
        "infrastructure",
        "internal_url",
        f"https://{svc}.{ctx.org['slug']}.internal/{path}",
    )


def _topology(rng: random.Random, ctx) -> Entity:
    net = f"10.{rng.choice([10, 20, 30])}.0.0/16"
    value = (
        f"{net} -> edge-router -> app-subnet -> "
        f"db-primary.{ctx.org['slug']}.internal:5432"
    )
    return Entity("infrastructure", "network_topology", value)


def _port(rng: random.Random, ctx) -> Entity:
    port, service = rng.choice(
        [(5432, "postgresql"), (3306, "mysql"), (6379, "redis"), (9200, "elasticsearch"), (8080, "http-alt")]
    )
    return Entity("infrastructure", "service_endpoint", f"{port}/tcp ({service})")


def _firewall(rng: random.Random, ctx) -> Entity:
    value = (
        f"allow tcp from 10.{rng.choice([10, 20, 30])}.0.0/16 "
        f"to 10.20.{rng.randint(0, 20)}.{rng.randint(2, 250)} port {rng.choice([443, 5432, 8443])}"
    )
    return Entity("infrastructure", "firewall_rule", value)


def _routing(rng: random.Random, ctx) -> Entity:
    value = (
        f"ip route 10.{rng.choice([10, 20, 30])}.0.0/16 "
        f"via 10.20.0.1 dev eth0"
    )
    return Entity("infrastructure", "routing_configuration", value)


def _k8s(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        f"  name: {rng.choice(common.SERVICES)}-service\n"
        f"  namespace: {slug}-prod\n"
        "spec:\n"
        "  replicas: 3\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        f"      - image: registry.{slug}.internal/platform/app:1.4.2\n"
        "        envFrom:\n"
        "        - secretRef:\n"
        "            name: example-fake-db-credentials"
    )
    return Entity("infrastructure", "kubernetes_manifest", value)


def _docker(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        "FROM registry." + slug + ".internal/base/python:3.12-slim\n"
        "COPY . /app\n"
        "RUN pip install -r requirements.txt\n"
        "CMD [\"python\", \"-m\", \"app\"]"
    )
    return Entity("infrastructure", "docker_configuration", value)


def _cloud_id(rng: random.Random, ctx) -> Entity:
    return Entity(
        "infrastructure",
        "cloud_resource_id",
        f"arn:aws:ec2:ap-southeast-1:000000000000:instance/i-examplefake{common.hexstr(rng, 8)}",
    )


def _db_endpoint(rng: random.Random, ctx) -> Entity:
    name = rng.choice(["db-primary", "db-replica", "db-analytics"])
    return Entity(
        "infrastructure",
        "database_endpoint",
        f"{name}.{ctx.org['slug']}.internal:5432",
    )


def _architecture(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        f"Three-tier web platform: public load balancer -> {slug}-api "
        f"service -> {rng.choice(common.SERVICES)} worker -> db-primary.{slug}.internal"
    )
    return Entity("infrastructure", "system_architecture", value)


def _terraform(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        'resource "aws_db_instance" "main" {\n'
        '  engine         = "postgres"\n'
        '  instance_class = "db.t3.medium"\n'
        f'  identifier     = "{slug}-{rng.choice(["prod", "staging"])}-db"\n'
        '  skip_final_snapshot = true\n'
        "}"
    )
    return Entity("infrastructure", "terraform_configuration", value)


def _deployment(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        "service: orders-api\n"
        "environment: production\n"
        f"cluster: {slug}-prod\n"
        f"database: db-primary.{slug}.internal\n"
        "replicas: 3"
    )
    return Entity("infrastructure", "deployment_configuration", value)


def _log(rng: random.Random, ctx) -> Entity:
    return Entity(
        "infrastructure",
        "internal_log_entry",
        f"2026-03-14T09:12:44Z INFO worker-3 request routed to 10.20.1.{rng.randint(2, 250)} status=200",
    )


def _inventory(rng: random.Random, ctx) -> Entity:
    return Entity(
        "infrastructure",
        "server_inventory_entry",
        f"app-{rng.randint(1, 24):02d} | 10.20.1.{rng.randint(2, 250)} | Ubuntu 22.04 | role=app",
    )


def _diagram(rng: random.Random, ctx) -> Entity:
    value = (
        "[internet]\n"
        "    |\n"
        "[edge-router 10.20.0.1]\n"
        "    |\n"
        "[app-subnet 10.20.1.0/24] -- [db-primary 10.20.2.10]"
    )
    return Entity("infrastructure", "network_diagram_text", value)


def _blueprint(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        f"System blueprint: {slug} order platform. "
        "Ingress terminates at edge-router; application pods run in the app subnet; "
        "database tier is isolated behind a private subnet with no public route."
    )
    return Entity("infrastructure", "system_blueprint", value)


def _metadata(rng: random.Random, ctx) -> Entity:
    slug = ctx.org["slug"]
    value = (
        '{"cluster":"' + slug + '-prod","region":"ap-southeast-1",'
        '"owner":"platform-team","cost_center":"CC-1042"}'
    )
    return Entity("infrastructure", "infrastructure_metadata", value)


GENERATORS = {
    "internal_ipv4": (16, _ipv4),
    "internal_ipv6": (5, _ipv6),
    "private_network": (6, _network),
    "internal_hostname": (13, _hostname),
    "internal_dns_name": (7, _dns),
    "internal_url": (10, _url),
    "network_topology": (3, _topology),
    "service_endpoint": (7, _port),
    "firewall_rule": (5, _firewall),
    "routing_configuration": (4, _routing),
    "kubernetes_manifest": (4, _k8s),
    "docker_configuration": (3, _docker),
    "cloud_resource_id": (5, _cloud_id),
    "database_endpoint": (8, _db_endpoint),
    "system_architecture": (3, _architecture),
    "terraform_configuration": (3, _terraform),
    "deployment_configuration": (3, _deployment),
    "internal_log_entry": (5, _log),
    "server_inventory_entry": (4, _inventory),
    "network_diagram_text": (2, _diagram),
    "system_blueprint": (2, _blueprint),
    "infrastructure_metadata": (4, _metadata),
}
