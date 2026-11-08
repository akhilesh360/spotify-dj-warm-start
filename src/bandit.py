"""Contextual Thompson-sampling bandit for the DJ session opener. SIMULATION ON SYNTHETIC DATA.

Arms: "familiar" (a favorite played 5+ times) vs "new" (a discovery).
Context: time-of-day bucket. Reward: the opener is NOT skipped in the first 30 s.
Each (bucket, arm) keeps a Beta(1, 1) prior that is updated after every session.

The opener skip probabilities start from data/sample_generator.py (familiar 0.23, new 0.55
on the first track). The time-of-day shifts below are ASSUMPTIONS made up for this demo:
listeners are assumed to be more open to new music in the evening and late at night.

Usage: python src/bandit.py [--sessions 2000] [--seed 7]
"""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BUCKETS = ["morning", "afternoon", "evening", "late night"]
BUCKET_WEIGHTS = [0.30, 0.30, 0.25, 0.15]
# P(early skip of the opener) per bucket: [familiar, new]. Synthetic assumptions.
SKIP = np.array([
    [0.23, 0.55],  # morning commute: wants the comfortable pick (generator default)
    [0.23, 0.45],
    [0.30, 0.22],  # evening: repeats feel stale, open to discovery
    [0.27, 0.25],  # late night: close call
])
FAMILIAR, NEW = 0, 1
LABEL = "SYNTHETIC SIMULATION - assumed skip probabilities, not Spotify data"

def simulate(policy, n, rng):
    ctx = rng.choice(len(BUCKETS), size=n, p=BUCKET_WEIGHTS)
    u = rng.random(n)
    a = np.ones((len(BUCKETS), 2)); b = np.ones((len(BUCKETS), 2))
    arms = np.empty(n, int); skips = np.empty(n, bool)
    for i, c in enumerate(ctx):
        if policy == "always new": arm = NEW
        elif policy == "always familiar": arm = FAMILIAR
        else: arm = int(np.argmax(rng.beta(a[c], b[c])))
        skipped = u[i] < SKIP[c, arm]
        a[c, arm] += not skipped; b[c, arm] += skipped
        arms[i], skips[i] = arm, skipped
    return arms, skips

def metrics(arms, skips):
    # discovery share: share of sessions whose opener is a new track played 30 s or more
    return skips.mean(), ((arms == NEW) & ~skips).mean()

def bootstrap_ci(arms, skips, rng, reps=2000):
    idx = rng.integers(0, len(arms), size=(reps, len(arms)))
    s = skips[idx].mean(1); d = ((arms[idx] == NEW) & ~skips[idx]).mean(1)
    return np.percentile(s, [2.5, 97.5]), np.percentile(d, [2.5, 97.5])

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="docs")
    a = ap.parse_args(argv)
    rng = np.random.default_rng(a.seed)
    print(f"[{LABEL}]  sessions per policy={a.sessions}, seed={a.seed}, 95% bootstrap CIs over sessions")
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {"always new": "#888", "always familiar": "#555", "Thompson sampling": "#1DB954"}
    results = {}
    for name in colors:
        arms, skips = simulate(name, a.sessions, rng)
        (s, d), (sci, dci) = metrics(arms, skips), bootstrap_ci(arms, skips, rng)
        results[name] = (s, d)
        print(f"{name:18s} early-skip {s:5.1%} [{sci[0]:.1%}, {sci[1]:.1%}]   "
              f"discovery share {d:5.1%} [{dci[0]:.1%}, {dci[1]:.1%}]")
        cum = np.cumsum(skips) / np.arange(1, len(skips) + 1)
        ax.plot(cum * 100, label=name, color=colors[name], lw=2 if "Thompson" in name else 1.4)
    best = SKIP.min(1) @ BUCKET_WEIGHTS
    ax.axhline(best * 100, ls=":", color="#1DB954", lw=1)
    ax.text(a.sessions, best * 100, "best fixed per-bucket rule (known in advance) ", va="bottom", ha="right", fontsize=8, color="#1DB954")
    ax.set(xlabel="Sessions", ylabel="Cumulative early-skip rate on opener (%)",
           title="Opener policy learning: cumulative skip rate", ylim=(10, 50))
    ax.legend(frameon=False)
    fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, color="#b00")
    fig.tight_layout(); Path(a.out).mkdir(parents=True, exist_ok=True)
    fig.savefig(Path(a.out) / "bandit_learning.png", dpi=150); plt.close(fig)
    print(f"best fixed per-bucket rule (known in advance): early-skip {best:.1%}")
    return results

if __name__ == "__main__":
    main()
