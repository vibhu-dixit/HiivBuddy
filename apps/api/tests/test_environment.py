import json

import pytest
from pydantic import TypeAdapter

from app.debate.environment import (
    AgentAction,
    DebateOption,
    EnvLimits,
    LinkAction,
    PassAction,
    ProposeClaimAction,
    SupportOptionAction,
    UtterAction,
)
from app.debate.environment_ops import apply_action, init_environment, merge_options, snapshot_for_api


def test_t1_pass_increments_step():
    env = init_environment("hello world context", rng_seed=1)
    assert env.step_index == 0
    r = apply_action(env, PassAction(agent_id="optimist"))
    assert r.ok
    assert r.env.step_index == 1
    assert r.env.hooks.passes == 1
    assert r.env.hooks.steps_applied == 1


def test_t2_utter_then_propose_claim_source_step():
    env = init_environment("x" * 20, rng_seed=0)
    env = merge_options(
        env,
        [DebateOption(id="0", title="A"), DebateOption(id="1", title="B")],
    )
    r1 = apply_action(env, UtterAction(agent_id="optimist", text="I lean A."))
    assert r1.ok
    r2 = apply_action(
        r1.env,
        ProposeClaimAction(agent_id="optimist", text="A is cheaper.", option_ids=("0",)),
    )
    assert r2.ok
    assert r2.env.step_index == 2
    claims = list(r2.env.claims.values())
    assert len(claims) == 1
    assert claims[0].source_step == 2


def test_t3_support_unknown_option():
    env = init_environment("context " * 5, rng_seed=3)
    r = apply_action(
        env,
        SupportOptionAction(agent_id="optimist", option_id="99", delta=0.1),
    )
    assert not r.ok
    assert "unknown_option" in r.errors
    assert r.env.step_index == env.step_index


def test_t4_support_clamps_deterministic():
    env = init_environment("ctx", rng_seed=0)
    env = merge_options(env, [DebateOption(id="0", title="Opt")])
    e = env
    for _ in range(20):
        r = apply_action(e, SupportOptionAction(agent_id="optimist", option_id="0", delta=0.2))
        assert r.ok
        e = r.env
    assert abs(e.option_support_scores["0"] - 1.0) < 1e-9


def test_t5_link_missing_claim():
    env = init_environment("ctx", rng_seed=0)
    env = merge_options(env, [DebateOption(id="0", title="Opt")])
    e = apply_action(
        env,
        ProposeClaimAction(agent_id="optimist", text="claim one", option_ids=()),
    ).env
    e = apply_action(
        e,
        ProposeClaimAction(agent_id="data_analyst", text="claim two", option_ids=()),
    ).env
    ids = sorted(e.claims.keys())
    r_bad = apply_action(
        e,
        LinkAction(
            agent_id="optimist",
            src_claim_id="nope",
            dst_claim_id=ids[0],
            rel="supports",
        ),
    )
    assert not r_bad.ok
    assert "unknown_claim" in r_bad.errors


def test_t6_max_claims():
    lim = EnvLimits(max_claims=2, max_steps_per_session=100)
    env = init_environment("ctx", rng_seed=0, limits=lim)
    env = merge_options(env, [DebateOption(id="0", title="O")])
    e = env
    for i in range(2):
        r = apply_action(e, ProposeClaimAction(agent_id="optimist", text=f"c{i}", option_ids=()))
        assert r.ok
        e = r.env
    r = apply_action(e, ProposeClaimAction(agent_id="optimist", text="overflow", option_ids=()))
    assert not r.ok
    assert "max_claims" in r.errors


def test_t7_max_edges():
    lim = EnvLimits(max_edges=1, max_claims=10, max_steps_per_session=100)
    env = init_environment("ctx", rng_seed=0, limits=lim)
    e = apply_action(
        env,
        ProposeClaimAction(agent_id="optimist", text="a", option_ids=()),
    ).env
    e = apply_action(
        e,
        ProposeClaimAction(agent_id="optimist", text="b", option_ids=()),
    ).env
    ids = sorted(e.claims.keys())
    e = apply_action(
        e,
        LinkAction(agent_id="optimist", src_claim_id=ids[0], dst_claim_id=ids[1], rel="relates"),
    ).env
    r = apply_action(
        e,
        LinkAction(agent_id="optimist", src_claim_id=ids[1], dst_claim_id=ids[0], rel="relates"),
    )
    assert not r.ok
    assert "max_edges" in r.errors


def test_t8_max_steps_per_session():
    lim = EnvLimits(max_steps_per_session=1)
    env = init_environment("ctx", rng_seed=0, limits=lim)
    r1 = apply_action(env, PassAction(agent_id="optimist"))
    assert r1.ok
    r2 = apply_action(r1.env, PassAction(agent_id="optimist"))
    assert not r2.ok
    assert "max_steps_per_session" in r2.errors


def test_t9_same_seed_context_ref():
    e1 = init_environment("same", rng_seed=42)
    e2 = init_environment("same", rng_seed=999)
    assert e1.context_ref.sha256 == e2.context_ref.sha256
    assert e1.context_ref.char_len == e2.context_ref.char_len


def test_t10_snapshot_roundtrip():
    env = init_environment("ctx", rng_seed=1)
    snap = snapshot_for_api(env)
    json.dumps(snap)
    assert snap["schema_version"] == 1
    assert "session_id" in snap
    assert "context_ref" in snap
    assert "hooks" in snap
    assert "action_log" in snap


def test_agent_action_discriminated_union_parse():
    parsed = TypeAdapter(AgentAction).validate_python(
        {"action": "pass", "agent_id": "optimist"},
    )
    assert isinstance(parsed, PassAction)
