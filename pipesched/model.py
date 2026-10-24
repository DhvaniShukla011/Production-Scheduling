"""Two-stage stochastic MILP (extensive form) in Pyomo.

Stage 1 (here-and-now): product of each lot to be injected, z[p,k].
Stage 2 (recourse, per scenario s): depot inventory, sales, unmet demand, spills.
"""
import pyomo.environ as pyo


def build_model(inst, probs, scen, fixed_z=None):
    P, N, K, T = inst.products, inst.N, inst.K, inst.T
    m = pyo.ConcreteModel()
    m.P = pyo.Set(initialize=P)
    m.K = pyo.RangeSet(1, K)
    m.S = pyo.RangeSet(0, len(scen) - 1)
    m.T = pyo.RangeSet(1, T)

    # ---------------- Stage 1: injection sequence ----------------
    m.z = pyo.Var(m.P, m.K, domain=pyo.Binary)           # lot k is product p
    m.one = pyo.Constraint(m.K, rule=lambda m, k: sum(m.z[p, k] for p in m.P) == 1)

    # Transition flow w[p,q,k] = 1 iff lot k-1 is p AND lot k is q (exactly z[p,k-1]*z[q,k]).
    # Written as two "assignment" equalities -> much tighter LP relaxation than
    # the textbook w >= z[p,k-1] + z[q,k] - 1.
    m.w = pyo.Var(m.P, m.P, pyo.RangeSet(2, K), domain=pyo.NonNegativeReals)
    m.out = pyo.Constraint(m.P, pyo.RangeSet(2, K),
                           rule=lambda m, p, k: sum(m.w[p, q, k] for q in m.P) == m.z[p, k - 1])
    m.inn = pyo.Constraint(m.P, pyo.RangeSet(2, K),
                           rule=lambda m, q, k: sum(m.w[p, q, k] for p in m.P) == m.z[q, k])
    pairs = [(p, q) for p in P for q in P if p != q]

    last = inst.init_line[-1]  # product of lot 0 (newest lot already in the line)
    interface_cost = (
        sum(inst.interface[p, q] * m.w[p, q, k] for (p, q) in pairs for k in range(2, K + 1))
        + sum(inst.interface[last, q] * m.z[q, 1] for q in P if q != last)
    )

    # ---------------- Stage 2: depot inventory per scenario ----------------
    m.I = pyo.Var(m.P, m.S, m.T, domain=pyo.NonNegativeReals)
    m.sale = pyo.Var(m.P, m.S, m.T, domain=pyo.NonNegativeReals)
    m.short = pyo.Var(m.P, m.S, m.T, domain=pyo.NonNegativeReals)
    m.spill = pyo.Var(m.P, m.S, m.T, domain=pyo.NonNegativeReals)
    m.tshort = pyo.Var(m.P, m.S, domain=pyo.NonNegativeReals)  # terminal stock shortfall

    def inflow(p, s, t):
        """Volume of product p arriving at the depot in slot t (1-based) under scenario s.
        Lot index delivered = (lots moved so far) - N. Pure data -> stays linear in z."""
        sc = scen[s]
        if sc.u[t - 1] == 0:
            return 0
        k = int(sc.cum[t - 1]) - N
        if k <= 0:                                      # product that was already in the line
            return inst.lot * (1 if inst.init_line[k + N - 1] == p else 0)
        return inst.lot * m.z[p, k]                     # product chosen by the planner

    def balance(m, p, s, t):
        prev = m.I[p, s, t - 1] if t > 1 else inst.init_inv[p]
        return m.I[p, s, t] == prev + inflow(p, s, t) - m.sale[p, s, t] - m.spill[p, s, t]
    m.bal = pyo.Constraint(m.P, m.S, m.T, rule=balance)

    m.cap = pyo.Constraint(m.P, m.S, m.T, rule=lambda m, p, s, t: m.I[p, s, t] <= inst.cap[p])
    m.dem = pyo.Constraint(
        m.P, m.S, m.T,
        rule=lambda m, p, s, t: m.sale[p, s, t] + m.short[p, s, t] == float(scen[s].demand[P.index(p), t - 1]))
    m.term = pyo.Constraint(m.P, m.S, rule=lambda m, p, s: m.I[p, s, T] + m.tshort[p, s] >= inst.init_inv[p])

    if fixed_z is not None:
        for key, v in fixed_z.items():
            m.z[key].fix(round(v))

    recourse = sum(
        probs[s] * (
            sum(inst.hold[p] * m.I[p, s, t] + inst.short[p] * m.short[p, s, t] + inst.spill * m.spill[p, s, t]
                for p in m.P for t in m.T)
            + sum(inst.short[p] * m.tshort[p, s] for p in m.P))
        for s in m.S)

    m.first_stage = pyo.Expression(expr=interface_cost)
    m.second_stage = pyo.Expression(expr=recourse)
    m.obj = pyo.Objective(expr=interface_cost + recourse, sense=pyo.minimize)
    return m


def solve(m, time_limit=60, gap=0.02):
    opt = pyo.SolverFactory("appsi_highs")
    opt.options["time_limit"] = time_limit
    opt.options["mip_rel_gap"] = gap
    opt.solve(m)
    return pyo.value(m.obj)


def get_plan(m, inst):
    """Return {k: product} for the first-stage decision."""
    return {k: next(p for p in inst.products if pyo.value(m.z[p, k]) > 0.5) for k in m.K}
