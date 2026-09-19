"""Day 6: prove the schema by building the REAL capability from the real
successful run in evidence/discovery-20260914T115514-3d104b/log.jsonl -- not
synthetic data. This is a hand-built preview of what the recorder will
automate later: translating a discovery transcript into a reusable artifact.

Two deliberate translations happen going from log -> artifact (this IS the
"decoupled from the raw model transcript" requirement in practice):
  - literal values the model typed ("100002", "Savings", "50") become
    ValueRef(kind="param", ...) -- the whole point of a REUSABLE capability
    is that these are supplied per-call, not frozen into the recording.
  - username/password become ValueRef(kind="secret", ...) -- never the
    plaintext, even though the harness log already redacts the password.
"""

from __future__ import annotations

import json

from cua.artifact import (
    Capability,
    Checkpoint,
    ClickStep,
    ErrorRule,
    Locator,
    NavigateStep,
    OutputSpec,
    ParamSpec,
    Policy,
    Provenance,
    ReadStep,
    RoleNameStrategy,
    SelectStep,
    Target,
    TypeStep,
    ValueRef,
)


def _role_name(role: str, name: str, confidence: str = "high") -> Locator:
    return Locator(strategies=[RoleNameStrategy(role=role, name=name, confidence=confidence)])


def build_open_subaccount_capability() -> Capability:
    # Named separately (rather than inline in the steps list) so `success`
    # below can point at this exact Checkpoint object instead of retyping
    # the same string -- one source of truth for "what does success look like".
    review_step = ClickStep(
        index=12,
        intent="review the new sub-account",
        target=_role_name("button", "Review"),
        checkpoint=Checkpoint(kind="text_present", value="Review New Sub-Account"),
    )

    steps = [
        NavigateStep(
            index=1,
            intent="open the target application",
            value=ValueRef(kind="literal", ref="http://localhost:8080/login"),
        ),
        TypeStep(
            index=2,
            intent="log in (harness)",
            target=_role_name("textbox", "Username"),
            value=ValueRef(kind="secret", ref="MOCKAPP_USERNAME"),
        ),
        TypeStep(
            index=3,
            intent="log in (harness)",
            target=_role_name("textbox", "Password"),
            value=ValueRef(kind="secret", ref="MOCKAPP_PASSWORD"),
        ),
        ClickStep(
            index=4,
            intent="log in (harness)",
            target=_role_name("button", "Sign In"),
            checkpoint=Checkpoint(kind="url_matches", value="/dashboard"),
        ),
        ClickStep(
            index=5,
            intent="go to member search",
            target=_role_name("link", "Go to Member Search"),
            checkpoint=Checkpoint(kind="url_matches", value="/search"),
        ),
        TypeStep(
            index=6,
            intent="enter member id",
            target=_role_name("textbox", "Member ID"),
            value=ValueRef(kind="param", ref="member_id"),
        ),
        ClickStep(
            index=7,
            intent="run search",
            target=_role_name("button", "Search"),
            checkpoint=Checkpoint(kind="text_present", value="Search Results"),
            on_error=[
                ErrorRule(
                    match=Checkpoint(kind="text_present", value="No matching records"),
                    classify="business_outcome",
                    outcome_code="member_not_found",
                )
            ],
        ),
        ClickStep(
            index=8,
            intent="open member detail",
            target=_role_name("link", "View"),
        ),
        ClickStep(
            index=9,
            intent="start new sub-account",
            target=_role_name("link", "Add Sub-Account"),
        ),
        SelectStep(
            index=10,
            intent="choose account type",
            target=_role_name("combobox", "Account Type"),
            value=ValueRef(kind="param", ref="account_type"),
        ),
        TypeStep(
            index=11,
            intent="enter initial deposit",
            target=_role_name("textbox", "Initial Deposit"),
            value=ValueRef(kind="param", ref="initial_deposit"),
        ),
        review_step,
        # Not in the raw discovery log -- the goal only asked to REACH this
        # screen. Added here because a reusable capability should hand the
        # caller the thing it just created, not just confirm it exists.
        ReadStep(
            index=13,
            intent="read the generated sub-account number",
            target=Locator(strategies=[RoleNameStrategy(role="cell", name="SA-4471", confidence="low", note="placeholder role/name; real recorder would capture the cell's actual locator bundle")]),
            output="sub_account_number",
        ),
    ]

    return Capability(
        id="open-subaccount",
        title="Open a new sub-account",
        description="Search for a member, open a new sub-account for them, and reach the confirmation screen.",
        target=Target(app_id="acme-cu-console", entry_url="http://localhost:8080/login"),
        inputs=[
            ParamSpec(name="member_id", type="string", sensitive=True, example="100002"),
            ParamSpec(name="account_type", type="enum", enum_values=["Savings", "Checking"]),
            ParamSpec(name="initial_deposit", type="money", example="50"),
        ],
        outputs=[
            OutputSpec(name="sub_account_number", type="string"),
        ],
        steps=steps,
        success=review_step.checkpoint,
        policy=Policy(risky_controls=["Confirm & Create", "Close Account"]),
        provenance=Provenance(
            discovered_at="2026-09-14T11:55:14Z",
            model="gemini-3.5-flash-lite",
            run_id="20260914T115514-3d104b",
            goal=(
                "Open a new sub-account for member 100002, type Savings, "
                "initial deposit 50, and reach the confirmation screen"
            ),
        ),
    )


def test_real_capability_builds_and_has_the_expected_shape():
    cap = build_open_subaccount_capability()
    assert len(cap.steps) == 13
    assert cap.steps[0].action == "navigate"
    assert cap.steps[6].action == "click"  # the search step
    assert cap.steps[6].on_error[0].outcome_code == "member_not_found"


def test_discriminated_union_resolves_correct_subclass_after_json_roundtrip():
    cap = build_open_subaccount_capability()
    restored = Capability.model_validate_json(cap.model_dump_json())

    # This is the actual point of a discriminated union: after coming back
    # from plain JSON, step 6 is a real TypeStep instance (has .value),
    # not a generic dict or a base Step with everything optional.
    type_step = restored.steps[5]
    assert type_step.action == "type"
    assert type_step.value.kind == "param"
    assert type_step.value.ref == "member_id"

    click_step = restored.steps[0 + 3]  # index 4 in the list -> "Sign In"
    assert click_step.action == "click"
    assert not hasattr(click_step, "value")  # ClickStep never had a value field at all


def test_secrets_never_appear_as_plaintext_literals():
    cap = build_open_subaccount_capability()
    dumped = cap.model_dump_json()
    assert "changeme" not in dumped  # the real .env password, if it ever leaked in
    for step in cap.steps:
        if step.action in ("type", "select") and "MOCKAPP" in getattr(step.value, "ref", ""):
            assert step.value.kind == "secret"


def test_json_schema_export_works_for_the_whole_capability():
    # This is the free win Pydantic gives an agent-facing contract: a calling
    # agent (or a reviewer) can introspect exactly what a capability needs
    # and returns without reading any Python.
    schema = Capability.model_json_schema()
    assert schema["title"] == "Capability"
    assert "properties" in schema


if __name__ == "__main__":
    cap = build_open_subaccount_capability()
    print(json.dumps(json.loads(cap.model_dump_json()), indent=2))
