"""Configurable policy evaluation and action precedence.

The default policy is an illustrative test configuration, not legal advice and
not a claim about any jurisdiction.  Deployments are expected to ship their own
policy file.
"""

from __future__ import annotations

import json
from typing import Dict, Iterable, List

from .models import ACTIONS, Entity

DEFAULT_ACTION_ORDER = list(ACTIONS)


def load_policy(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as handle:
        policy = json.load(handle)
    validate_policy(policy)
    return policy


def validate_policy(policy: dict) -> None:
    order = policy.get("action_order", DEFAULT_ACTION_ORDER)
    if set(order) != set(ACTIONS) or len(order) != len(ACTIONS):
        raise ValueError("policy.action_order must contain each action exactly once")
    scenarios = policy.get("scenarios")
    if not scenarios:
        raise ValueError("policy.scenarios must be a non-empty object")
    for name, scenario in scenarios.items():
        if scenario.get("routing") not in ("external", "local"):
            raise ValueError(f"scenario {name}: routing must be 'external' or 'local'")
        min_action = scenario.get("min_action", "ALLOW")
        if min_action not in ACTIONS:
            raise ValueError(f"scenario {name}: unknown min_action {min_action}")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("policy.rules must be a non-empty array")
    for rule in rules:
        if rule.get("action", "ALLOW") not in ACTIONS:
            raise ValueError(f"rule {rule.get('id')}: unknown action")
        for action in rule.get("by_entity", {}).values():
            if action not in ACTIONS:
                raise ValueError(f"rule {rule.get('id')}: unknown entity action {action}")
        if not rule.get("domains") and not rule.get("entity_types"):
            raise ValueError(f"rule {rule.get('id')}: rule must scope domains or entity_types")


def _strictest(actions: Iterable[str], order: List[str]) -> str:
    rank = {action: index for index, action in enumerate(order)}
    actions = list(actions) or ["ALLOW"]
    return max(actions, key=lambda action: rank[action])


def _match(rule: dict, entity: Entity) -> bool:
    domains = rule.get("domains")
    if domains and entity.domain not in domains:
        return False
    types = rule.get("entity_types")
    if types and entity.entity_type not in types:
        return False
    return True


def resolve_policy(entities: List[Entity], scenario_name: str, policy: dict) -> dict:
    order = policy.get("action_order", DEFAULT_ACTION_ORDER)
    scenario = policy["scenarios"][scenario_name]
    min_action = scenario.get("min_action", "ALLOW")

    per_type: Dict[str, str] = {}
    matched_rules = set()
    for entity in entities:
        actions = []
        for rule in policy["rules"]:
            if _match(rule, entity):
                matched_rules.add(rule["id"])
                actions.append(rule.get("by_entity", {}).get(entity.entity_type, rule.get("action", "ALLOW")))
        action = _strictest(actions, order)
        if entities:
            action = _strictest([action, min_action], order)
        per_type[entity.entity_type] = action

    overall = _strictest(per_type.values(), order) if per_type else "ALLOW"
    if not per_type:
        # A scenario floor only applies when sensitive data is actually present.
        matched_rules.clear()

    if overall == "BLOCK":
        routing = "blocked"
    elif overall == "LOCAL_ONLY":
        routing = "local"
    else:
        routing = scenario["routing"]

    transformation = [
        {"entity_type": entity_type, "action": action}
        for entity_type, action in sorted(per_type.items())
    ]
    return {
        "policy_scenario": scenario_name,
        "policy_decision_expected": overall,
        "action_expected": dict(sorted(per_type.items())),
        "routing_expected": routing,
        "transformation_expected": transformation,
        "policy_rule_ids": sorted(matched_rules),
    }
