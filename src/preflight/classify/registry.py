"""Tier 1: curated classification of Microsoft first-party tools.

Finite and enumerable, which is exactly why it belongs in a table rather than a heuristic. It is
also the most obviously contributable artifact in the project.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    untrusted_input: bool
    irreversible_action: bool
    rationale: str


FIRST_PARTY: dict[str, Entry] = {
    "bing_grounding": Entry(True, False, "Returns attacker-influenceable web content."),
    "bing_custom_search": Entry(True, False, "Narrower domain set, still external content."),
    "browser_automation": Entry(True, True, "Reads the open web and acts on it."),
    "computer_use": Entry(True, True, "Reads a screen and drives arbitrary UI."),
    "code_interpreter": Entry(True, True, "Executes code over supplied content and writes files."),
    "deep_research": Entry(True, False, "Multi-step web research."),
    "file_search": Entry(True, False, "Content is user-supplied; treat as untrusted input."),
    "sharepoint": Entry(True, False, "Tenant content, still authored by people."),
    "fabric": Entry(False, False, "Structured query over governed data."),
    "image_generation": Entry(False, False, "Produces content, reaches nothing."),
    "azure_function": Entry(False, True, "Arbitrary code with side effects."),
    "logic_app": Entry(False, True, "Connector actions, assumed state-changing."),
    "web_search": Entry(True, False, "Open web content, attacker-influenceable."),
    "graph_connectors": Entry(True, False, "Indexed third-party content, authored by people."),
    "email": Entry(True, False, "Inbound mail is the classic untrusted channel."),
    "teams_messages": Entry(True, False, "Message content is user-authored."),
    "people": Entry(False, False, "Directory lookup."),
    "dataverse": Entry(False, False, "Structured query over governed data."),
}
