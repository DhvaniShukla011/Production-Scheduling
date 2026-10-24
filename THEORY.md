# From scratch: the problem, the maths, and the code

This document explains every modelling decision in `pipesched/`. Read it top to bottom once, then keep it as a reference.

## 1. The engineering problem

A **multiproduct pipeline** carries several refined products (gasoline, diesel, jet fuel, kerosene) from a refinery to a distribution depot through **one** pipe. Products are pumped as consecutive **batches** (lots). The pipe is always full of liquid, so it behaves as a **first-in-first-out (FIFO) queue**: the lot injected first is delivered first, and every time a volume enters at the refinery, the same volume leaves at the depot.

Two operational facts drive the whole model:

1. **Interfaces.** Where two different products touch, they mix. The mixed volume (*transmix*) must be downgraded or reprocessed, which costs money. Cost depends on the pair (jet next to gasoline is far worse than jet next to kerosene). So the **order** of lots matters.
2. **Depot inventory.** The depot has finite tanks and customers draw product continuously. If a product tank runs dry, you lose sales (and for jet fuel, you have a serious problem). If it is full, you cannot accept more.

The planner must choose the injection order **before** knowing what will happen. This is the gap between a deterministic model and a real one.

## 2. Where uncertainty enters

* **Pump / flow-rate disruptions** (the source of the uncertainty in Beheshti Asl & MirHassani 2019 and Baghban et al. 2025): in a disrupted slot nothing moves, so every later delivery slides back in time.
* **Demand** at the depot (the focus of Moradi & MirHassani 2016 and the tree-like network work of Taherkhani et al. 2017).

Our model includes both. A **scenario** `s` is one joint realisation: a vector `u_s[t]` (1 = pumps run, 0 = outage) and a demand matrix `d_s[p,t]`.

## 3. Stochastic programming in 10 minutes

Decisions split by *when they must be made*:

| | Made when? | Depends on scenario? | Here |
|---|---|---|---|
| **Stage 1** (here-and-now) | before uncertainty resolves | no, one value | injection sequence `z[p,k]` |
| **Stage 2** (recourse) | after it resolves | yes, one value per scenario | inventory, sales, shortage, spill |

The **two-stage stochastic program** minimises

    first-stage cost  +  E_s [ second-stage cost(first-stage decision, scenario s) ]

With a finite scenario set and probabilities `π_s`, the expectation is a weighted sum and the whole thing becomes one big deterministic MILP, the **extensive form** (what `build_model` builds). Because stage 1 is shared across scenarios, the plan is automatically a *compromise* that hedges.

Why not just plug in average values? Costs are **nonlinear in the disruptions** (a 4-slot outage is not four times as bad as 1 slot: tanks run dry and stay dry). Solving at the average hides this. That is exactly what the VSS below measures.

## 4. Modelling trick: lots and the FIFO queue

Discretise time into `T` slots and volume into **lots** of `lot` m³. The pipe holds exactly `N` lots. In a slot where pumps run, one lot enters and one leaves.

Let `c_s(t)` = number of slots up to `t` in which pumps ran in scenario `s` (a cumulative sum of `u_s`, pure **data**). Lot number `k` (k = 1, 2, ... in injection order) enters when `c = k` and, after `N` more moves, leaves when `c = k + N`. Therefore:

> At slot `t` (if pumps run), the lot delivered to the depot is lot `k = c_s(t) − N`.

* If `k ≤ 0`, it is a lot that was already in the pipe: its product is **known data** (`init_line`).
* If `k ≥ 1`, its product is the decision variable `z[p,k]`.

So the inflow of product `p` at slot `t` in scenario `s` is `lot * z[p, k(s,t)]`, where the *index* `k(s,t)` is computed in Python, not by the solver. This keeps the model **linear** (no binary × binary products) while still letting an outage delay deliveries. This index trick is the key idea of the repo.

Only lots `1 … T−N` can possibly reach the depot within the horizon, so the planner chooses `K = T − N` lots.

## 5. The model, equation by equation

Sets: products `p`, lots `k = 1..K`, slots `t = 1..T`, scenarios `s`.

**Stage 1 variables:** `z[p,k] ∈ {0,1}` = 1 if lot `k` is product `p`.

1. **One product per lot**: `Σ_p z[p,k] = 1`.
2. **Interface transitions**: `w[p,q,k] = z[p,k−1]·z[q,k]` (1 iff lot `k−1` is `p` and lot `k` is `q`). Products of binaries are not linear, so we use the **assignment (flow) form**:
   `Σ_q w[p,q,k] = z[p,k−1]` and `Σ_p w[p,q,k] = z[q,k]`.
   This is *exact* for binary `z` and has a much tighter LP relaxation than the textbook `w ≥ z[p,k−1] + z[q,k] − 1` (we tried both: the weak one was far slower).
   The cost of lot 1 against the known last lot in the pipe is added separately.
3. **First-stage cost** = `Σ interface_cost[p,q] · w[p,q,k]`.

**Stage 2 variables (per scenario):** `I` inventory, `sale`, `short` (unmet demand), `spill` (emergency off-loading when a tank is full), `tshort` (end-of-horizon stock below the starting level).

4. **Inventory balance**: `I[p,s,t] = I[p,s,t−1] + inflow[p,s,t] − sale[p,s,t] − spill[p,s,t]`, with `I[p,s,0]` the initial stock.
5. **Tank capacity**: `I[p,s,t] ≤ cap[p]`.
6. **Demand split**: `sale + short = demand[p,s,t]` (what you cannot sell is lost and penalised).
7. **Terminal stock**: `I[p,s,T] + tshort ≥ init_inv[p]`, otherwise the optimiser would simply drain every tank at the end (an *end-of-horizon effect*).

**Objective:** `min  first-stage cost + Σ_s π_s [ holding + shortage + spill + terminal penalties ]`.

*Relatively complete recourse*: for any `z` and any scenario, a feasible stage-2 solution exists (shortage and spill are always allowed). This avoids infeasibility cuts and is a standard modelling habit.

## 6. Value metrics (the part reviewers like)

All costs, minimisation.

* **RP**, recourse problem: optimum of the stochastic model.
* **WS**, wait-and-see: solve each scenario separately (as if you knew the future) and average the optima.
* **EEV**, expected result of the mean-value solution: solve with *one* average scenario (no outage, mean demand), fix that plan, then evaluate it on all scenarios.

Always **WS ≤ RP ≤ EEV** (the test suite checks this).

* **EVPI = RP − WS** = the most you would pay for a perfect forecast.
* **VSS = EEV − RP** = what you gain by modelling uncertainty instead of using averages.

**Out-of-sample test.** Planning on 20 scenarios and evaluating on the same 20 flatters the stochastic plan (over-fitting). So we draw 100 *new* scenarios and evaluate both fixed plans on them (`OOS_RP`, `OOS_EEV`). This is the Sample Average Approximation (SAA) validation idea.

## 7. Computational lessons (put these in interviews)

* The lot-sequencing core is combinatorial; a 24-slot horizon did not close a 0.01% gap in 5 minutes with HiGHS, so the default is `T=16` and a 2% gap.
* A tighter transition formulation (section 5.2) was the single biggest speed-up.
* **Always compare VSS with the MIP gap.** With a 2% gap on a ~190k objective, differences below ~4k are noise. In the `baseline` case VSS is 60, which is *not* evidence of anything.

## 8. How to extend (pick one)

1. **CVaR objective** (risk aversion): add `η`, `ξ_s ≥ cost_s − η`, minimise `E + λ(η + Σ π_s ξ_s /(1−α))`.
2. **Benders / L-shaped or Progressive Hedging** (`mpi-sppy`) for many scenarios.
3. **Pump energy cost / flow-rate variables**, as in Beheshti Asl & MirHassani (2019).
4. **Multiple depots / tree-like network** (Mostafaei et al. 2015; Taherkhani et al. 2017).
5. **Scenario reduction** and a convergence study over `n_scen`.
