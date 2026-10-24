import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COL = {"G": "#E45756", "D": "#4C78A8", "J": "#F2B134", "K": "#54A24B"}


def plot_plans(inst, plans, path):
    fig, ax = plt.subplots(figsize=(11, 1.2 + 0.9 * len(plans)))
    for row, (name, plan) in enumerate(plans.items()):
        for k, p in plan.items():
            ax.barh(row, 1, left=k - 1, color=COL[p], edgecolor="white")
            ax.text(k - 0.5, row, p, ha="center", va="center", color="white", fontsize=8)
    ax.set_yticks(range(len(plans))); ax.set_yticklabels(list(plans))
    ax.set_xlabel("lot index k (injection order)"); ax.set_xlim(0, inst.K)
    ax.set_title("First-stage injection sequence (G=gasoline, D=diesel, J=jet, K=kerosene)")
    plt.tight_layout(); plt.savefig(path, dpi=150); plt.close()


def plot_bars(res, path):
    names = ["WS", "RP", "EEV"]
    vals = [res[n] for n in names]
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar(names, vals, color=["#54A24B", "#4C78A8", "#E45756"])
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("expected cost ($)")
    ax.set_title(f"VSS = {res['VSS']:,.0f}   EVPI = {res['EVPI']:,.0f}")
    plt.tight_layout(); plt.savefig(path, dpi=150); plt.close()
