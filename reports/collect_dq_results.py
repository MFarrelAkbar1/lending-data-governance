"""Stage 6a: append the latest `dbt test` results to dq.dq_results_history.

Reads dbt_project/target/run_results.json (what happened) and
dbt_project/target/manifest.json (test metadata: dimension, severity, rule_id,
tested model and column). rows_checked is the row count of the tested relation
at collection time.

Usage:
    python -m reports.collect_dq_results
"""
import json
import re
from pathlib import Path

from sqlalchemy import text

from common.db import get_engine

TARGET = Path("dbt_project/target")

DDL = """
CREATE TABLE IF NOT EXISTS dq.dq_results_history (
    run_id            text,
    run_at            timestamptz,
    data_batch_id     text,
    test_unique_id    text,
    test_name         text,
    test_type         text,
    rule_id           text,
    layer             text,
    source_table      text,
    model_name        text,
    column_name       text,
    dq_dimension      text,
    severity          text,
    status            text,
    failures          bigint,
    rows_checked      bigint,
    execution_seconds numeric(10, 3),
    description       text
)
"""


def node_layer_and_table(manifest: dict, unique_id: str) -> tuple[str, str, str]:
    """Return (layer, source_table, model_name) for a source or model unique_id."""
    if unique_id.startswith("source."):
        src = manifest["sources"][unique_id]
        return "raw", src["name"], src["name"]
    model = manifest["nodes"][unique_id]
    layer = model["fqn"][1] if len(model["fqn"]) > 2 else "other"
    source_table = model["config"].get("meta", {}).get("source_table") or model["name"]
    return layer, source_table, model["name"]


def relation_for(manifest: dict, unique_id: str) -> str:
    node = manifest["sources"].get(unique_id) or manifest["nodes"][unique_id]
    return node["relation_name"]


def main() -> None:
    run_results = json.loads((TARGET / "run_results.json").read_text())
    manifest = json.loads((TARGET / "manifest.json").read_text())
    if run_results["args"].get("which") not in ("test", "build"):
        raise SystemExit("run_results.json is not from `dbt test`; run the tests first")

    run_id = run_results["metadata"]["invocation_id"]
    run_at = run_results["metadata"]["generated_at"]
    models_by_name = {n["name"]: uid for uid, n in manifest["nodes"].items() if n["resource_type"] == "model"}
    sources_by_name = {s["name"]: uid for uid, s in manifest["sources"].items()}

    engine = get_engine()
    rows, row_counts = [], {}
    with engine.begin() as conn:
        conn.execute(text(DDL))
        batch_id = conn.execute(
            text("SELECT batch_id FROM audit.load_log ORDER BY loaded_at DESC LIMIT 1")
        ).scalar()

        for result in run_results["results"]:
            uid = result["unique_id"]
            if not uid.startswith("test."):
                continue
            node = manifest["nodes"][uid]
            meta = node["config"].get("meta", {})
            attached = node.get("attached_node")
            if not attached:
                # Source tests: the tested source is in the `model` kwarg, e.g. source('raw', 'bureau').
                kwarg = (node.get("test_metadata") or {}).get("kwargs", {}).get("model", "")
                match = re.search(r"source\('(\w+)',\s*'(\w+)'\)", kwarg)
                if match:
                    attached = f"source.{manifest['metadata']['project_name']}.{match.group(1)}.{match.group(2)}"
                else:  # singular test: target declared in meta
                    target = meta.get("dq_table")
                    attached = models_by_name.get(target) or sources_by_name.get(target)
            layer, source_table, model_name = node_layer_and_table(manifest, attached)
            layer = meta.get("layer", layer)

            relation = relation_for(manifest, attached)
            if relation not in row_counts:
                row_counts[relation] = conn.execute(text(f"SELECT count(*) FROM {relation}")).scalar()

            test_meta = node.get("test_metadata") or {}
            namespace = test_meta.get("namespace")
            rows.append({
                "run_id": run_id,
                "run_at": run_at,
                "data_batch_id": batch_id,
                "test_unique_id": uid,
                "test_name": node["name"],
                "test_type": f"{namespace}.{test_meta['name']}" if namespace else test_meta.get("name", "singular"),
                "rule_id": meta.get("rule_id"),
                "layer": layer,
                "source_table": source_table,
                "model_name": model_name,
                "column_name": node.get("column_name"),
                "dq_dimension": meta.get("dq_dimension", "unassigned"),
                "severity": node["config"]["severity"].lower(),
                "status": result["status"],
                "failures": result.get("failures"),
                "rows_checked": row_counts[relation],
                "execution_seconds": round(result.get("execution_time") or 0, 3),
                "description": node.get("description"),
            })

        conn.execute(text("DELETE FROM dq.dq_results_history WHERE run_id = :r"), {"r": run_id})
        conn.execute(
            text(
                "INSERT INTO dq.dq_results_history VALUES ("
                ":run_id, :run_at, :data_batch_id, :test_unique_id, :test_name, :test_type, :rule_id, :layer, "
                ":source_table, :model_name, :column_name, :dq_dimension, :severity, :status, :failures, "
                ":rows_checked, :execution_seconds, :description)"
            ),
            rows,
        )
        runs = conn.execute(text("SELECT count(DISTINCT run_id) FROM dq.dq_results_history")).scalar()

    statuses = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    print(f"Run {run_id}: stored {len(rows)} test results {statuses}; history now holds {runs} runs")


if __name__ == "__main__":
    main()
