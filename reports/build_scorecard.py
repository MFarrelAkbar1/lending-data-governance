"""Stage 6b: build reports/dq_scorecard.html from the dq models.

Reads dq.dq_scorecard, dq.dq_results, dq.dq_before_after and audit.load_log,
embeds the numbers as JSON and renders the charts with Plotly.js. Every number
on the page comes from those tables.

Usage:
    python -m reports.build_scorecard
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from common.db import get_engine

OUT = Path(__file__).with_name("dq_scorecard.html")
TEMPLATE = Path(__file__).with_name("scorecard_template.html")
DIMENSIONS = ["completeness", "uniqueness", "validity", "consistency", "referential_integrity", "timeliness"]
LAYER_ORDER = {"raw": 0, "staging": 1, "marts": 2}


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        score = pd.read_sql("SELECT * FROM dq.dq_scorecard", conn)
        results = pd.read_sql("SELECT * FROM dq.dq_results WHERE is_latest_run", conn)
        before_after = pd.read_sql("SELECT * FROM dq.dq_before_after ORDER BY source_table, rule_id", conn)
        load = pd.read_sql(
            "SELECT table_name, row_count, column_count, loaded_at, status, batch_id FROM audit.load_log "
            "WHERE batch_id = (SELECT batch_id FROM audit.load_log ORDER BY loaded_at DESC LIMIT 1)",
            conn,
        )
        runs = pd.read_sql(
            "SELECT run_number, run_at, layer, sum(tests_run) AS tests_run, sum(tests_passed) AS tests_passed "
            "FROM dq.dq_scorecard WHERE dq_dimension = 'overall' GROUP BY 1, 2, 3 ORDER BY 1",
            conn,
        )

    runs["dq_score_pct"] = (100 * runs["tests_passed"] / runs["tests_run"]).round(1)
    latest = score[score["is_latest_run"]].copy()
    latest["layer_order"] = latest["layer"].map(LAYER_ORDER)
    overall = latest[latest["dq_dimension"] == "overall"].sort_values(["layer_order", "model_name"])
    heat = latest[latest["dq_dimension"] != "overall"]

    layer_totals = (
        overall.groupby("layer")[["tests_run", "tests_passed"]].sum()
        .assign(score=lambda d: (100 * d["tests_passed"] / d["tests_run"]).round(1))
    )
    failing = results[results["status"] != "pass"].sort_values("failures", ascending=False)

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "run_count": int(runs["run_number"].nunique()),
        "latest_run_at": str(results["run_at"].max()),
        "kpi": {
            "tests": int(len(results)),
            "passed": int((results["status"] == "pass").sum()),
            "warned": int((results["status"] == "warn").sum()),
            "failed": int(results["status"].isin(["fail", "error"]).sum()),
            "raw_score": float(layer_totals.loc["raw", "score"]),
            "staging_score": float(layer_totals.loc["staging", "score"]),
            "rows_loaded": int(load["row_count"].sum()),
            "batch_id": load["batch_id"].iloc[0],
            "rules_resolved": int((before_after["outcome"] == "resolved by cleansing").sum()),
            "rules_open": int((before_after["outcome"] == "still open (accepted)").sum()),
            "rules_paired": int(len(before_after)),
        },
        "overall": records(overall[["layer", "model_name", "source_table", "tests_run", "tests_passed",
                                    "tests_warned", "tests_failed", "dq_score_pct"]]),
        "heat": records(heat[["layer", "model_name", "dq_dimension", "tests_run", "tests_passed", "dq_score_pct"]]),
        "dimensions": DIMENSIONS,
        "before_after": records(before_after),
        "top_failing": records(failing.head(15)[["test_name", "layer", "model_name", "dq_dimension",
                                                  "severity", "status", "failures", "rows_checked"]]),
        "trend": records(runs),
        "load": records(load),
    }

    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} (run {data['run_count']}, {data['kpi']['tests']} tests)")


if __name__ == "__main__":
    main()
