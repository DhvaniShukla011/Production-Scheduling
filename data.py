"""Problem data and scenario generation.

ALL NUMBERS ARE ILLUSTRATIVE (not taken from a real pipeline). They are chosen
so the problem is realistic in structure and magnitude; replace them with
published case-study data if you want to reproduce a specific paper.
"""
from dataclasses import dataclass, field
import numpy as np

PRODUCTS = ["G", "D", "J", "K"]  # Gasoline, Diesel, Jet fuel, Kerosene

# $ lost per interface (transmix reprocessing/downgrade) between adjacent lots.
INTERFACE_COST = {
    ("G", "D"): 4000, ("D", "G"): 4000,
    ("G", "J"): 9000, ("J", "G"): 9000,
    ("G", "K"): 7000, ("K", "G"): 7000,
    ("D", "J"): 2500, ("J", "D"): 2500,
    ("D", "K"): 2000, ("K", "D"): 2000,
    ("J", "K"): 1500, ("K", "J"): 1500,
}


@dataclass
class Instance:
    products: list = field(default_factory=lambda: list(PRODUCTS))
    T: int = 16                 # time slots in horizon (e.g. 16 x 6 h = 4 days)
    N: int = 3                  # number of lots the pipeline holds at any time
    lot: float = 1000.0         # volume of one lot (m3)
    # product currently in the line; index 0 is delivered first, last is newest
    init_line: list = field(default_factory=lambda: ["D", "G", "D"])
    init_inv: dict = field(default_factory=lambda: {"G": 1500, "D": 1400, "J": 600, "K": 400})
    cap: dict = field(default_factory=lambda: {"G": 3500, "D": 3200, "J": 1500, "K": 1000})
    base_demand: dict = field(default_factory=lambda: {"G": 420, "D": 380, "J": 130, "K": 70})  # m3/slot
    hold: dict = field(default_factory=lambda: {"G": 0.8, "D": 0.7, "J": 1.0, "K": 0.8})        # $/m3/slot
    short: dict = field(default_factory=lambda: {"G": 45, "D": 40, "J": 80, "K": 50})           # $/m3 unmet
    spill: float = 60.0         # $/m3 emergency off-loading when tank is full
    interface: dict = field(default_factory=lambda: dict(INTERFACE_COST))

    @property
    def K(self):
        """Number of lots the planner chooses (lots that can reach the depot in the horizon)."""
        return self.T - self.N


@dataclass
class Scenario:
    u: np.ndarray        # u[t]=1 if pumps run in slot t (t=0..T-1), 0 if outage
    demand: np.ndarray   # demand[p_index, t]  (m3)

    @property
    def cum(self):
        """Cumulative number of lots moved up to and including slot t."""
        return np.cumsum(self.u).astype(int)


def make_scenarios(inst, n=20, seed=0, p_outage=0.6, max_dur=4, cv=0.2):
    """Scenario = (pump-outage event) x (lognormal demand level per product)."""
    rng = np.random.default_rng(seed)
    P, T = len(inst.products), inst.T
    sigma = np.sqrt(np.log(1 + cv ** 2))
    profile = 1 + 0.15 * np.sin(2 * np.pi * np.arange(T) / 8)  # intra-day swing
    scen = []
    for _ in range(n):
        u = np.ones(T, dtype=int)
        if rng.random() < p_outage:
            start = rng.integers(0, T - max_dur)
            u[start:start + rng.integers(1, max_dur + 1)] = 0
        level = rng.lognormal(-sigma ** 2 / 2, sigma, size=P)  # mean 1
        d = np.array([inst.base_demand[p] for p in inst.products])[:, None] * level[:, None] * profile[None, :]
        scen.append(Scenario(u=u, demand=d))
    return [1.0 / n] * n, scen


def mean_scenario(scen):
    """Deterministic 'expected value' scenario: no outage, mean demand."""
    T = len(scen[0].u)
    return Scenario(u=np.ones(T, dtype=int), demand=np.mean([s.demand for s in scen], axis=0))
