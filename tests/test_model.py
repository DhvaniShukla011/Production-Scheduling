"""Sanity tests on a tiny instance:  python -m pytest -q"""
import pytest
from pipesched.data import Instance, make_scenarios, mean_scenario
from pipesched.model import build_model, solve, get_plan
from pipesched.analysis import evaluate_plan


@pytest.fixture(scope="module")
def setup():
    inst = Instance(T=10, N=3)
    probs, scen = make_scenarios(inst, 4, seed=1)
    return inst, probs, scen


def test_one_product_per_lot(setup):
    inst, probs, scen = setup
    m = build_model(inst, probs, scen)
    solve(m, time_limit=30)
    assert len(get_plan(m, inst)) == inst.K


def test_value_metric_ordering(setup):
    """WS <= RP <= EEV must hold for a minimisation problem (up to solver gap)."""
    inst, probs, scen = setup
    rp_m = build_model(inst, probs, scen)
    rp = solve(rp_m, time_limit=30, gap=1e-4)
    ws = sum(p * solve(build_model(inst, [1.0], [s]), gap=1e-4) for p, s in zip(probs, scen))
    mv = build_model(inst, [1.0], [mean_scenario(scen)])
    solve(mv, gap=1e-4)
    eev = evaluate_plan(inst, get_plan(mv, inst), probs, scen)
    tol = 1e-3 * rp
    assert ws <= rp + tol
    assert rp <= eev + tol


def test_no_outage_delivers_one_lot_per_slot(setup):
    inst, _, scen = setup
    assert mean_scenario(scen).cum[-1] == inst.T
