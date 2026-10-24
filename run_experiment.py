"""Run the experiment:  python run_experiment.py --case baseline|tight"""
import argparse, csv, os
from pipesched.data import Instance
from pipesched.analysis import run_analysis
from pipesched.plots import plot_plans, plot_bars

CASES = {
    # generous depot buffers, moderate disruptions
    "baseline": (Instance(), dict(p_outage=0.6, max_dur=4, cv=0.2)),
    # thin depot buffers, longer/more frequent pump outages, higher demand volatility
    "tight": (Instance(init_inv={"G": 800, "D": 700, "J": 300, "K": 200}),
              dict(p_outage=0.9, max_dur=5, cv=0.3)),
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="baseline", choices=CASES)
    ap.add_argument("--scenarios", type=int, default=20)
    a = ap.parse_args()
    inst, kw = CASES[a.case]
    os.makedirs("results", exist_ok=True)
    res = run_analysis(inst, n_scen=a.scenarios, **kw)
    keys = ["RP", "WS", "EEV", "EVPI", "VSS", "OOS_RP", "OOS_EEV"]
    for k in keys:
        print(f"{k:8s}: {res[k]:12,.0f}")
    with open(f"results/summary_{a.case}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        for k in keys:
            w.writerow([k, round(res[k], 1)])
    plot_plans(inst, {"Stochastic (RP)": res["plan_rp"], "Mean-value (EEV)": res["plan_mv"]},
               f"results/plans_{a.case}.png")
    plot_bars(res, f"results/value_metrics_{a.case}.png")
    print("sequence RP :", "".join(res["plan_rp"].values()))
    print("sequence EEV:", "".join(res["plan_mv"].values()))
