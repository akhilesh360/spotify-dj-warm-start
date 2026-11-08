"""SYNTHETIC sample generator - NOT real listening data.

Writes data/sample_streaming_history.json in the same schema as Spotify's
"Extended streaming history" export, so the analysis can run end to end.
The skip behaviour is an assumption baked in here (new tracks opening a session
get skipped more), so numbers from this file only demo the method.
"""
import json, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)
ARTISTS = [f"Artist {c}" for c in "ABCDEFGHIJKLMNOPQRST"]
CATALOG = [(f"Track {i:03d}", random.choice(ARTISTS)) for i in range(400)]
FAVES = CATALOG[:40]  # the listener's heavy rotation

def skip_prob(track, plays, pos):
    familiar = plays.get(track, 0) >= 5
    p = 0.18 if familiar else 0.38
    if pos == 0:
        p += 0.05 if familiar else 0.17  # cold opener penalty (assumption)
    return min(p, 0.9)

def main(days=120, out=Path(__file__).with_name("sample_streaming_history.json")):
    plays, rows = {}, []
    t = datetime(2026, 1, 1, 7, tzinfo=timezone.utc)
    for _ in range(days):
        for _ in range(random.randint(1, 3)):  # sessions per day
            t += timedelta(hours=random.uniform(3, 9))
            for pos in range(random.randint(4, 18)):
                track = random.choice(FAVES) if random.random() < 0.45 else random.choice(CATALOG)
                skipped = random.random() < skip_prob(track, plays, pos)
                ms = random.randint(2_000, 29_000) if skipped else random.randint(120_000, 240_000)
                t += timedelta(milliseconds=ms)
                rows.append({
                    "ts": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "ms_played": ms,
                    "master_metadata_track_name": track[0],
                    "master_metadata_album_artist_name": track[1],
                    "reason_start": "clickrow" if pos == 0 else ("fwdbtn" if rows and rows[-1]["skipped"] else "trackdone"),
                    "reason_end": "fwdbtn" if skipped else "trackdone",
                    "skipped": skipped, "shuffle": random.random() < 0.5,
                })
                plays[track] = plays.get(track, 0) + 1
    out.write_text(json.dumps(rows, indent=1))
    print(f"wrote {len(rows)} SYNTHETIC rows -> {out}")

if __name__ == "__main__":
    main()
