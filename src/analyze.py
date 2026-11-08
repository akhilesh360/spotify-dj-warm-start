"""Early-skip analysis + warm-start simulation for a Spotify Extended streaming history export.

Usage: python src/analyze.py data/my_Streaming_History_Audio_*.json [--synthetic]
"""
import argparse, json, sys
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SESSION_GAP = pd.Timedelta(minutes=30)
EARLY_MS = 30_000
FAMILIAR_PLAYS = 5

def load(paths):
    rows = []
    for p in paths:
        rows += json.loads(Path(p).read_text())
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["master_metadata_track_name"])  # drop podcasts/unknown
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    # ts is when playback ended; approximate start time
    df["start"] = df["ts"] - pd.to_timedelta(df["ms_played"], unit="ms")
    return df.sort_values("start").reset_index(drop=True)

def enrich(df):
    gap = df["start"] - df["ts"].shift()
    df["session"] = (gap.isna() | (gap > SESSION_GAP)).cumsum()
    df["pos"] = df.groupby("session").cumcount() + 1
    key = df["master_metadata_album_artist_name"].fillna("") + " | " + df["master_metadata_track_name"]
    df["prior_plays"] = df.groupby(key).cumcount()
    df["familiar"] = df["prior_plays"] >= FAMILIAR_PLAYS
    df["early_skip"] = df["ms_played"] < EARLY_MS
    return df

def summarize(df):
    by_pos = df.assign(pos_b=df["pos"].clip(upper=10)).groupby("pos_b")["early_skip"].mean()
    openers = df[df["pos"] == 1]
    by_fam = df.groupby([df["pos"] == 1, "familiar"])["early_skip"].agg(["mean", "size"])
    rate_fam = openers.loc[openers["familiar"], "early_skip"].mean()
    rate_new = openers.loc[~openers["familiar"], "early_skip"].mean()
    share_new = (~openers["familiar"]).mean()
    baseline = openers["early_skip"].mean()
    # Warm start: every session that opened on a new track opens on a familiar one instead.
    simulated = rate_fam  # all openers become familiar
    return dict(sessions=int(df["session"].nunique()), plays=len(df), by_pos=by_pos, by_fam=by_fam,
                opener_skip_baseline=baseline, opener_skip_familiar=rate_fam, opener_skip_new=rate_new,
                share_sessions_new_opener=share_new, opener_skip_warm_start=simulated)

def charts(s, outdir, label):
    outdir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    s["by_pos"].mul(100).plot(ax=ax, marker="o", color="#1DB954")
    ax.set(xlabel="Position in session (10 = 10+)", ylabel="Early-skip rate (%)",
           title="Early skips by position in session")
    fig.text(0.99, 0.01, label, ha="right", fontsize=8, color="#b00")
    fig.tight_layout(); fig.savefig(outdir / "skip_by_position.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    vals = [s["opener_skip_new"], s["opener_skip_familiar"], s["opener_skip_baseline"], s["opener_skip_warm_start"]]
    names = ["Opener: new", "Opener: familiar", "Today (mix)", "Warm start (sim)"]
    bars = ax.bar(names, [v * 100 for v in vals], color=["#888", "#1DB954", "#555", "#1ed760"])
    ax.bar_label(bars, fmt="%.0f%%")
    ax.set(ylabel="Early-skip rate on first track (%)", title="First-track skips: today vs warm start")
    fig.text(0.99, 0.01, label, ha="right", fontsize=8, color="#b00")
    fig.tight_layout(); fig.savefig(outdir / "warm_start_simulation.png", dpi=150); plt.close(fig)

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--synthetic", action="store_true", help="label outputs as synthetic sample")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args(argv)
    label = "SYNTHETIC SAMPLE - run on your own export for real numbers" if a.synthetic else "Your Spotify export"
    s = summarize(enrich(load(a.files)))
    charts(s, Path(a.out), label)
    print(f"[{label}]")
    print(f"sessions={s['sessions']} plays={s['plays']}")
    print("early-skip rate by position:\n" + s["by_pos"].round(3).to_string())
    print(f"first-track skip: new={s['opener_skip_new']:.1%} familiar={s['opener_skip_familiar']:.1%}")
    print(f"sessions opening on a new track: {s['share_sessions_new_opener']:.1%}")
    print(f"first-track skip today={s['opener_skip_baseline']:.1%} -> warm start (sim)={s['opener_skip_warm_start']:.1%}")
    print("Caveat: observational; listeners may pick familiar openers on purpose, so this is an upper bound, not a causal effect.")
    return s

if __name__ == "__main__":
    main()
