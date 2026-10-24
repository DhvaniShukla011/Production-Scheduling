"""Stochastic-programming value metrics: RP, WS, EEV, EVPI, VSS, out-of-sample test."""
from .data import make_scenarios, mean_scenario
from .model import build_model, solve, get_plan


def plan_to_z(plan, inst):
    return {(p, k): int(plan[k] == p) for k in plan for p in inst.products}


def evaluate_plan(inst, plan, probs, scen):
    """Expected cost of a FIXED first-stage plan on a set of scenarios (an LP)."""
    m = build_model(inst, probs, scen, fixed_z=plan_to_z(plan, inst))
    return solve(m)


def run_analysis(inst, n_scen=20, seed=0, n_test=100, test_seed=999, **scen_kw):
    probs, scen = make_scenarios(inst, n_scen, seed, **scen_kw)

    rp_m = build_model(inst, probs, scen)
    RP = solve(rp_m)
    plan_rp = get_plan(rp_m, inst)

    WS = 0.0   # perfect information: optimise separately for each scenario
    for s in range(n_scen):
        WS += probs[s] * solve(build_model(inst, [1.0], [scen[s]]))

    mv_m = build_model(inst, [1.0], [mean_scenario(scen)])   # deterministic "mean" problem
    solve(mv_m)
    plan_mv = get_plan(mv_m, inst)
    EEV = evaluate_plan(inst, plan_mv, probs, scen)

    # out-of-sample check on fresh scenarios (guards against over-fitting to the sample)
    tp, ts = make_scenarios(inst, n_test, test_seed, **scen_kw)
    oos_rp = evaluate_plan(inst, plan_rp, tp, ts)
    oos_mv = evaluate_plan(inst, plan_mv, tp, ts)

    return dict(RP=RP, WS=WS, EEV=EEV, EVPI=RP - WS, VSS=EEV - RP,
                OOS_RP=oos_rp, OOS_EEV=oos_mv, plan_rp=plan_rp, plan_mv=plan_mv)
