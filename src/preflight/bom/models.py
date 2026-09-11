"""AgentBOM data model, mirroring schema/agentbom-0.1.json.

The schema is the contract; these models are the convenient view of it. A test validates generated
BOMs against the JSON Schema so the two cannot drift silently.

``None`` means the definition does not say. It is never a substitute for zero or false.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["foundry", "copilot-studio", "m365-declarative", "agent-framework", "external"]
AuthMode = Literal["none", "key", "managed-identity", "obo", "unknown"]
EdgeConfidence = Literal["proven", "matched", "probed", "suspected"]
ToolKind = Literal["mcp", "openapi", "builtin", "connector", "function", "code-interpreter", "a2a"]


class Classification(BaseModel):
    untrustedInput: bool
    irreversibleAction: bool
    source: Literal["policy", "registry", "protocol", "failclosed"]
    confidence: Literal["high", "medium", "low"] = "medium"
    rationale: str | None = None


class Annotations(BaseModel):
    """MCP ToolAnnotations. ``readOnlyHint`` defaults to false per the spec."""

    readOnlyHint: bool = False
    destructiveHint: bool | None = None
    idempotentHint: bool | None = None
    openWorldHint: bool | None = None


class ToolSource(BaseModel):
    server: str | None = None
    manifestHash: str | None = None
    trusted: bool = False
    toolbox: str | None = None
    pinned: bool | None = None
    allowlist: bool | None = None
    httpMethod: str | None = None
    builtinId: str | None = None


class ToolAuth(BaseModel):
    mode: AuthMode = "unknown"
    scopes: list[str] = Field(default_factory=list)
    secretRef: str | None = None


class Tool(BaseModel):
    id: str
    kind: ToolKind
    name: str
    descriptionTokens: int | None = None
    approval: bool | None = None
    referencedInInstructions: bool | None = None
    source: ToolSource = Field(default_factory=ToolSource)
    auth: ToolAuth = Field(default_factory=ToolAuth)
    annotations: Annotations | None = None
    classification: Classification | None = None


class Identity(BaseModel):
    kind: Literal["entra-agent", "app-registration", "shared", "none", "unknown"] = "unknown"
    objectId: str | None = None
    appId: str | None = None
    blueprint: str | None = None
    mode: Literal["obo", "autonomous", "unknown"] = "unknown"
    owner: str | None = None
    sponsor: str | None = None


class Instructions(BaseModel):
    hash: str | None = None
    tokens: int | None = None
    capChars: int | None = None


class Agent(BaseModel):
    id: str
    platform: Platform
    name: str | None = None
    description: str | None = None
    environment: str | None = None
    endpoints: list[str] = Field(default_factory=list)
    inboundAuth: AuthMode = "unknown"
    sourceFile: str | None = None
    identity: Identity = Field(default_factory=Identity)
    instructions: Instructions = Field(default_factory=Instructions)


class Model(BaseModel):
    deployment: str
    model: str
    version: str | None = None
    sku: str | None = None
    region: str | None = None
    capacity: int | None = None
    contextWindow: int | None = None
    status: Literal["current", "deprecated", "retired", "unknown"] = "unknown"


class Knowledge(BaseModel):
    id: str
    kind: Literal["ai-search", "sharepoint", "files", "fabric", "bing", "web", "other"]
    region: str | None = None
    citationsRequired: bool | None = None
    chunkTokens: int | None = None
    chunksPerTurn: int | None = None


class Storage(BaseModel):
    kind: Literal["thread", "memory", "vector", "logs"]
    resource: str | None = None
    region: str | None = None
    retentionDays: int | None = None
    sanitised: bool | None = None


class Guards(BaseModel):
    contentFilter: Literal["default", "custom", "none", "unknown"] = "unknown"
    promptShields: bool | None = None
    humanInTheLoop: bool | None = None
    tokenCap: int | None = None
    rateLimit: int | None = None
    maxTurns: int | None = None
    historySummarisation: bool | None = None


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    tool: str | None = None
    via: Literal["connected-agent", "a2a", "http-action", "openapi", "mcp", "connector"]
    endpoint: str | None = None
    auth: AuthMode = "unknown"
    crossPlatform: bool = False
    crossRegion: bool = False
    crossTenant: bool = False
    signal: Literal["identity", "endpoint", "probe"]
    confidence: EdgeConfidence

    model_config = {"populate_by_name": True}


class Cost(BaseModel):
    value: float
    currency: str = "USD"


class Economics(BaseModel):
    instructionTokens: int | None = None
    toolDescriptionTokens: int | None = None
    groundingTokensPerTurn: int | None = None
    fanoutFactor: float | None = None
    estimatedCostPerInteraction: Cost | None = None


class Residency(BaseModel):
    declared: str | None = None
    observed: list[str] = Field(default_factory=list)


class Generator(BaseModel):
    tool: str = "preflight"
    version: str = "0.1.0"
    collector: str


class AgentBOM(BaseModel):
    bomFormat: Literal["AgentBOM"] = "AgentBOM"
    specVersion: Literal["0.1"] = "0.1"
    serialNumber: str | None = None
    generated: datetime
    generator: Generator
    agent: Agent
    models: list[Model] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)
    knowledge: list[Knowledge] = Field(default_factory=list)
    storage: list[Storage] = Field(default_factory=list)
    guards: Guards = Field(default_factory=Guards)
    edges: list[Edge] = Field(default_factory=list)
    economics: Economics = Field(default_factory=Economics)
    residency: Residency = Field(default_factory=Residency)
    tags: dict[str, str | None] = Field(default_factory=dict)
    signature: dict[str, str] | None = None
