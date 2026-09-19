"""
The capability artifact schema -- the reusable, versioned contract that
discovery produces and replay consumes. See REPORT.md section 2 for the full
design rationale.

Design rule applied throughout, decided deliberately per type rather than
applied blindly everywhere:

    Use a discriminated union (separate classes + a `kind`/`action` tag) when
    the different kinds genuinely need different required fields.
    Use one flat model with a `kind` enum when every kind shares the same
    shape and only the INTERPRETATION differs.

  - Step:            union   -- TypeStep requires `value`, ClickStep doesn't,
                                 NavigateStep has no `target` at all.
  - LocatorStrategy:  union   -- role_name needs 2 fields, ordinal needs an
                                 int; kept as 5 named kinds (not collapsed
                                 further) for human reviewability.
  - Checkpoint:       flat    -- every kind is just `kind` + a string; only
                                 which field of the screen gets searched
                                 differs.
  - ValueRef:         flat    -- literal/param/secret are all just one string,
                                 differently interpreted.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Locator -- HOW a step's target element is identified. A ranked BUNDLE of
# strategies, not one selector -- replay tries them best-first and stops at
# the first unique match (see REPORT.md section 3).
# ---------------------------------------------------------------------------

Confidence = Literal["high", "medium", "low"]


class LocatorStrategyBase(BaseModel):
    confidence: Confidence
    note: str = ""  # reviewer-facing: why this strategy is/isn't robust


class RoleNameStrategy(LocatorStrategyBase):
    """Semantic: role + accessible name, e.g. button "Search". Best signal --
    survives layout changes and is the only kind that also makes sense on a
    desktop surface (see REPORT.md section 4)."""

    kind: Literal["role_name"] = "role_name"
    role: str
    name: str


class LabelStrategy(LocatorStrategyBase):
    """Found via an associated <label>, e.g. the field labeled "Member ID"."""

    kind: Literal["label"] = "label"
    label: str


class TextStrategy(LocatorStrategyBase):
    """Found via visible text content."""

    kind: Literal["text"] = "text"
    text: str


class CssStrategy(LocatorStrategyBase):
    """Last resort: a raw selector. Brittle -- breaks if markup shifts."""

    kind: Literal["css_path"] = "css_path"
    css: str


class OrdinalStrategy(LocatorStrategyBase):
    """Last resort: "the Nth match". Brittle -- breaks if a row is added."""

    kind: Literal["ordinal"] = "ordinal"
    position: int


LocatorStrategy = Annotated[
    Union[RoleNameStrategy, LabelStrategy, TextStrategy, CssStrategy, OrdinalStrategy],
    Field(discriminator="kind"),
]


class Locator(BaseModel):
    """A ranked bundle of ways to find ONE element, best strategy first."""

    strategies: list[LocatorStrategy]
    screenshot_crop: str | None = None  # evidence + last resort: a saved crop path


# ---------------------------------------------------------------------------
# ValueRef -- HOW a step's value gets filled in. Never an inline secret.
# ---------------------------------------------------------------------------


class ValueRef(BaseModel):
    kind: Literal["literal", "param", "secret"]
    ref: str
    # kind="literal" -> `ref` IS the value, e.g. "Savings"
    # kind="param"   -> `ref` is a parameter NAME, resolved from the caller's
    #                   inputs at replay time
    # kind="secret"  -> `ref` is a secret NAME, resolved from a secret store
    #                   at replay time -- the plaintext never appears here,
    #                   in a log, or anywhere else in the artifact


# ---------------------------------------------------------------------------
# Checkpoint -- a condition to verify against the CURRENT screen. Reused for:
# a capability's success condition, a step's precondition, a step's own
# checkpoint, and ErrorRule.match.
# ---------------------------------------------------------------------------


class Checkpoint(BaseModel):
    kind: Literal["url_matches", "text_present", "text_absent"]
    value: str


# ---------------------------------------------------------------------------
# ErrorRule -- how to classify a known deviation at a specific step.
# ---------------------------------------------------------------------------


class ErrorRule(BaseModel):
    match: Checkpoint
    classify: Literal["business_outcome", "recoverable", "hard_failure"]
    outcome_code: str | None = None  # e.g. "member_not_found", for business_outcome
    recover: Literal["dismiss", "retry", "reload", "relogin"] | None = None
    max_attempts: int = 2


# ---------------------------------------------------------------------------
# Step -- ONE action in the replayable flow.
# ---------------------------------------------------------------------------


class StepBase(BaseModel):
    index: int
    intent: str  # human-readable "why", carried over from discovery's reasoning
    precondition: Checkpoint | None = None  # must hold BEFORE acting
    checkpoint: Checkpoint | None = None  # must hold AFTER acting
    on_error: list[ErrorRule] = Field(default_factory=list)


class NavigateStep(StepBase):
    action: Literal["navigate"] = "navigate"
    value: ValueRef


class ClickStep(StepBase):
    action: Literal["click"] = "click"
    target: Locator


class TypeStep(StepBase):
    action: Literal["type"] = "type"
    target: Locator
    value: ValueRef


class SelectStep(StepBase):
    action: Literal["select"] = "select"
    target: Locator
    value: ValueRef


class ReadStep(StepBase):
    action: Literal["read"] = "read"
    target: Locator
    output: str  # names which OutputSpec below this read fills


Step = Annotated[
    Union[NavigateStep, ClickStep, TypeStep, SelectStep, ReadStep],
    Field(discriminator="action"),
]


# ---------------------------------------------------------------------------
# ParamSpec / OutputSpec -- the capability's typed contract with its caller.
# ---------------------------------------------------------------------------

ParamType = Literal["string", "number", "money", "boolean", "enum"]


class ParamSpec(BaseModel):
    name: str
    type: ParamType
    required: bool = True
    sensitive: bool = False  # if True: never logged, never stored raw anywhere
    enum_values: list[str] | None = None
    example: str | None = None  # a synthetic, safe example value
    description: str = ""


class OutputSpec(BaseModel):
    name: str
    type: ParamType
    sensitive: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Capability -- the whole artifact.
# ---------------------------------------------------------------------------

SurfaceType = Literal["web", "legacy_web", "desktop"]


class Target(BaseModel):
    app_id: str  # identifies the VENDOR PRODUCT, not the tenant -- the hook
    # for cross-tenant reuse (REPORT.md section 4)
    entry_url: str
    surface_type: SurfaceType = "web"


class Policy(BaseModel):
    allowed_action_types: list[str] = Field(
        default_factory=lambda: ["navigate", "click", "type", "select", "read"]
    )
    risky_controls: list[str] = Field(default_factory=list)  # exact control names, never auto-clicked


class Provenance(BaseModel):
    discovered_at: str  # ISO timestamp
    model: str  # which LLM produced this, e.g. "gemini-3.5-flash-lite"
    run_id: str  # ties back to the evidence/discovery-<run_id> directory
    goal: str  # the natural-language goal that was discovered


class Capability(BaseModel):
    schema_version: str = "1.0"
    id: str
    version: int = 1
    title: str
    description: str = ""

    target: Target
    inputs: list[ParamSpec] = Field(default_factory=list)
    outputs: list[OutputSpec] = Field(default_factory=list)
    steps: list[Step]
    success: Checkpoint

    policy: Policy = Field(default_factory=Policy)
    provenance: Provenance

    @model_validator(mode="after")
    def _validate_step_references(self) -> "Capability":
        """Catches a typo'd `ref`/`output` at artifact-build time instead of
        at replay time, where it would surface as a confusing KeyError deep
        inside step execution instead of a clear validation error here."""
        param_names = {p.name for p in self.inputs}
        output_names = {o.name for o in self.outputs}

        for step in self.steps:
            value = getattr(step, "value", None)
            if value is not None and value.kind == "param" and value.ref not in param_names:
                raise ValueError(f"step {step.index}: value references undeclared param {value.ref!r}")
            if isinstance(step, ReadStep) and step.output not in output_names:
                raise ValueError(f"step {step.index}: output {step.output!r} is not a declared output")
        return self
