"""Microsoft Agent Framework collector.

Reads: tools registered at build time, the agent's instructions, and its model deployment.

Agent Framework agents are code, not configuration, which is the hardest case for a design-time
gate: there is no manifest to read, and running the code to find out is exactly what Preflight
refuses to do. So this collector reads code the way a reviewer would, and says plainly what it
could not resolve.

Two inputs, strongest first:

1. **An exported definition**, ``agent-framework.json`` next to the code, written by the build. This
   is the reliable path, and `docs/USAGE.md` shows the six lines that produce it.
2. **A static read of the source**, for projects that export nothing. Python only, parsed rather
   than executed: decorated tool functions, and the agent constructor's literal arguments.

What a static read cannot see is recorded rather than assumed away. A tool registered through a
variable, a loop or a plugin import shows up in ``tags['unresolvedRegistrations']``, and the BOM
says the tool list is partial. A partial list is honest; a silently short one is not.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from preflight.bom.models import (
    Agent,
    AgentBOM,
    Generator,
    Guards,
    Identity,
    Instructions,
    Model,
    Tool,
    ToolAuth,
    ToolSource,
)
from preflight.collectors.base import AgentRef, Scope

#: Decorators that register a function as a tool the model may call.
_TOOL_DECORATORS = {"ai_function", "tool", "kernel_function", "function_tool"}
#: Constructors that create an agent in the Agent Framework.
_AGENT_CTORS = {"ChatAgent", "AzureAIAgent", "Agent", "AgentBuilder", "ChatClientAgent"}
_EXPORT = "agent-framework.json"


def _tokens(text: str | None) -> int | None:
    return max(1, round(len(text) / 4)) if text else None


def _decorator_names(node: ast.AST) -> set[str]:
    out = set()
    for d in getattr(node, "decorator_list", []):
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Name):
            out.add(target.id)
        elif isinstance(target, ast.Attribute):
            out.add(target.attr)
    return out


def _literal(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


class _Source:
    """One parsed Python file: its tool functions, its agent constructions, and what it hid."""

    def __init__(self, path: Path):
        self.path = path
        self.tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.tools: list[tuple[str, str | None]] = []
        self.agents: list[dict[str, str | None]] = []
        self.unresolved: list[str] = []
        self._walk()

    def _walk(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _decorator_names(node) & _TOOL_DECORATORS:
                    self.tools.append((node.name, ast.get_docstring(node)))
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                if name not in _AGENT_CTORS:
                    continue
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                self.agents.append({
                    "name": _literal(kw.get("name")) or self.path.stem,
                    "instructions": _literal(kw.get("instructions")) or _literal(kw.get("system_prompt")),
                    "model": _literal(kw.get("model")) or _literal(kw.get("deployment_name")) or _literal(kw.get("model_id")),
                })
                tools_arg = kw.get("tools")
                if tools_arg is not None and not isinstance(tools_arg, (ast.List, ast.Tuple)):
                    self.unresolved.append(f"{self.path.name}: tools= is not a literal list")
                elif isinstance(tools_arg, (ast.List, ast.Tuple)):
                    for el in tools_arg.elts:
                        if not isinstance(el, ast.Name):
                            self.unresolved.append(f"{self.path.name}: a tool in tools= is computed, not a plain name")


class AgentFrameworkCollector:
    platform = "agent-framework"
    version = "agent_framework@0.2.0"

    def available(self) -> tuple[bool, str]:
        return True, "reads an exported definition, or the source without running it"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        root = Path(scope.path or ".")
        seen: set[str] = set()
        for f in sorted(root.rglob(_EXPORT)):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            aid = str(d.get("id") or d.get("name") or f.parent.name)
            seen.add(str(f.parent))
            yield AgentRef(id=aid, platform=self.platform, name=d.get("name"), scope=Scope(path=str(f)))
        for f in sorted(root.rglob("*.py")):
            if str(f.parent) in seen or ".venv" in f.parts or "site-packages" in f.parts:
                continue
            try:
                src = _Source(f)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for a in src.agents:
                yield AgentRef(id=f"{f.stem}:{a['name']}", platform=self.platform, name=a["name"],
                               scope=Scope(path=str(f)))

    def collect(self, ref: AgentRef) -> AgentBOM:
        path = Path(ref.scope.path)
        return (self._from_export(path, ref) if path.name == _EXPORT else self._from_source(path, ref))

    # --- the two inputs ------------------------------------------------------------------

    def _from_export(self, path: Path, ref: AgentRef) -> AgentBOM:
        d = json.loads(path.read_text(encoding="utf-8"))
        instructions = d.get("instructions") or ""
        tools = [
            Tool(
                id=f"fn:{t.get('name')}",
                kind=t.get("kind") or "function",
                name=t.get("name") or "tool",
                description=t.get("description"),
                descriptionTokens=_tokens(t.get("description")),
                approval=t.get("approval"),
                source=ToolSource(server=t.get("server")),
                auth=ToolAuth(mode=(t.get("auth") or {}).get("mode", "unknown"),
                              secretRef=(t.get("auth") or {}).get("secretRef")),
            )
            for t in d.get("tools") or []
        ]
        model = d.get("model") or {}
        return self._bom(ref.id, d.get("name"), instructions, tools,
                         model.get("deployment") or model.get("name"), str(path),
                         partial=False, unresolved=[])

    def _from_source(self, path: Path, ref: AgentRef) -> AgentBOM:
        src = _Source(path)
        wanted = ref.name or ref.id.split(":", 1)[-1]
        spec = next((a for a in src.agents if a["name"] == wanted), src.agents[0] if src.agents else {})
        tools = [
            Tool(id=f"fn:{name}", kind="function", name=name, description=doc,
                 descriptionTokens=_tokens(doc))
            for name, doc in src.tools
        ]
        return self._bom(ref.id, spec.get("name"), spec.get("instructions") or "", tools,
                         spec.get("model"), str(path), partial=True, unresolved=src.unresolved)

    def _bom(self, aid: str, name: str | None, instructions: str, tools: list[Tool],
             model: str | None, source: str, *, partial: bool, unresolved: list[str]) -> AgentBOM:
        return AgentBOM(
            generated=datetime.now(UTC),
            generator=Generator(collector=self.version),
            agent=Agent(
                id=aid,
                platform=self.platform,
                name=name,
                sourceFile=source,
                identity=Identity(kind="unknown"),
                instructions=Instructions(
                    hash="sha256:" + hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
                    tokens=_tokens(instructions),
                ) if instructions else Instructions(),
            ),
            models=[Model(deployment=model, model=model)] if model else [],
            tools=tools,
            guards=Guards(),
            tags={
                # Read from source rather than from an export: the tool list is what could be seen
                # statically, which is a floor, not a total.
                "toolListPartial": str(partial),
                "unresolvedRegistrations": "; ".join(unresolved) or "none",
            },
        )
