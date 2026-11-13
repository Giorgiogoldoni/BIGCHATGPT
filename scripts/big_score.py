"""Classifica sperimentale BIG: integra score tecnico e qualita' storica dei sistemi BIG.
Non modifica score.json: produce data/score_big.json come classifica parallela.
"""
import json
import math
from pathlib import Path

HORIZONS = (20, 40, 60)
FAMILIES = {
    "Trend": ("core", "azb", "sbb", "psar", "adx", "ema"),
    "Momentum": ("mom",),
    "Indicatori": ("cd",),
    "Inversione": ("inv", "mr", "smr"),
    "Breakout": ("k5",),
}
TILT = 0.20  # +/- 10 punti massimi rispetto allo score originale


def _clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(x)))


def system_quality(stats):
    """Qualita' storica 0-100. Richiede almeno 10 segnali e due meta' misurabili.
    Non usa la statistica t di rank.py, che non e' un test inferenziale corretto.
    """
    if not stats or len(stats) < 9:
        return None
    n, hit, median, excess, first, second = stats[:6]
    if n < 10 or excess is None or first is None or second is None:
        return None
    excess_score = 50.0 + 50.0 * math.tanh(float(excess) / 5.0)
    hit_score = _clip(50.0 + 2.0 * (float(hit) - 50.0))
    stability = _clip(50.0 + 25.0 * math.tanh(float(first) / 4.0)
                      + 25.0 * math.tanh(float(second) / 4.0))
    sample = min(100.0, 100.0 * float(n) / 30.0)
    return round(0.40 * excess_score + 0.25 * hit_score
                 + 0.25 * stability + 0.10 * sample, 1)


def _freshness(age):
    if age <= 3:
        return 1.0
    if age <= 5:
        return 0.75
    if age <= 10:
        return 0.40
    return 0.0


def _signal_quality(row, stats_for_horizon):
    ages = row.get("system_ages") or {}
    family_scores = []
    details = []
    for family, system_ids in FAMILIES.items():
        weighted, weights = 0.0, 0.0
        for sid in system_ids:
            age = ages.get(sid)
            if age is None or age > 10:
                continue
            stat = stats_for_horizon.get(sid)
            quality = system_quality(stat)
            if quality is None:
                continue
            w = _freshness(int(age))
            weighted += quality * w
            weights += w
            details.append({
                "id": sid, "age": int(age), "quality": quality,
                "n": int(stat[0]), "excess": stat[3], "hit": stat[1],
            })
        if weights:
            family_scores.append(weighted / weights)
    if not family_scores:
        return 50.0, details
    # Ogni famiglia pesa uguale: sei sistemi Trend non sovrastano gli altri.
    return round(sum(family_scores) / len(family_scores), 1), details


def build(score_payload, rank_payload):
    rank_by_ticker = {r["t"]: r for r in rank_payload.get("righe", [])}
    rows = []
    for base in score_payload.get("rows", []):
        row = dict(base)
        historical = rank_by_ticker.get(base.get("t"), {})
        scores = {}
        details_by_horizon = {}
        for horizon in HORIZONS:
            stats = (historical.get("st") or {}).get(str(horizon), {})
            quality, details = _signal_quality(base, stats)
            original = float(base.get("score%d" % horizon, base.get("score", 0)))
            scores[horizon] = round(_clip(original + TILT * (quality - 50.0)), 1)
            details_by_horizon[str(horizon)] = {
                "signal_quality": quality, "active": details,
                "tilt": round(TILT * (quality - 50.0), 1),
            }
        row.update({
            "score_big20": scores[20], "score_big40": scores[40],
            "score_big60": scores[60],
            "score_big": round(sum(scores.values()) / 3.0, 1),
            "big_signal_detail": details_by_horizon,
        })
        rows.append(row)
    rows.sort(key=lambda x: x.get("score_big", -1), reverse=True)
    return {
        "generated": score_payload.get("generated"),
        "period": score_payload.get("period"),
        "method": "score_base_plus_20pct_BIG_signal_quality",
        "tilt": TILT,
        "horizons": list(HORIZONS),
        "rows": rows,
    }


def write(data_dir):
    data_dir = Path(data_dir)
    score_path = data_dir / "score.json"
    rank_path = data_dir / "classifica.json"
    if not score_path.exists() or not rank_path.exists():
        print("score BIG: score.json o classifica.json non disponibile; salto")
        return
    with score_path.open(encoding="utf-8") as f:
        score_payload = json.load(f)
    with rank_path.open(encoding="utf-8") as f:
        rank_payload = json.load(f)
    payload = build(score_payload, rank_payload)
    (data_dir / "score_big.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    eligible = sum(1 for r in payload["rows"] if r.get("eligible"))
    print("score BIG:", len(payload["rows"]), "strumenti |", eligible,
          "ammessi alla Top20 BIG")


if __name__ == "__main__":
    write(Path(__file__).resolve().parent.parent / "data")
