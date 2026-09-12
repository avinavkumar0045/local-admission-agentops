import requests

dashboard_payload = {
  "dashboard": {
    "id": None,
    "uid": "agentops_metrics_v1",
    "title": "AgentOps: Core Metrics & Diagnostics",
    "tags": [ "agentops", "metrics" ],
    "timezone": "browser",
    "schemaVersion": 38,
    "version": 2,
    "refresh": "5s",
    "panels": [
      {
        "type": "stat",
        "title": "Total Queries Processed",
        "gridPos": { "h": 6, "w": 4, "x": 0, "y": 0 },
        "datasource": { "uid": "bfv8qs0pp6osga", "type": "mysql" },
        "targets": [
          { "format": "table", "rawSql": "SELECT COUNT(*) FROM traces", "refId": "A" }
        ]
      },
      {
        "type": "gauge",
        "title": "Avg LLM Generation Latency (Seconds)",
        "gridPos": { "h": 6, "w": 4, "x": 4, "y": 0 },
        "datasource": { "uid": "bfv8qs0pp6osga", "type": "mysql" },
        "targets": [
          { "format": "table", "rawSql": "SELECT AVG(duration_ms)/1000 AS seconds FROM spans WHERE span_type = 'llm_generation'", "refId": "A" }
        ],
        "fieldConfig": {
          "defaults": { "min": 0, "max": 60, "color": { "mode": "thresholds" }, "thresholds": { "mode": "absolute", "steps": [ { "color": "green", "value": None }, { "color": "orange", "value": 20 }, { "color": "red", "value": 40 } ] } }
        }
      },
      {
        "type": "piechart",
        "title": "Success vs. Error Rate",
        "gridPos": { "h": 6, "w": 4, "x": 8, "y": 0 },
        "datasource": { "uid": "bfv8qs0pp6osga", "type": "mysql" },
        "targets": [
          { "format": "table", "rawSql": "SELECT status, COUNT(*) AS count FROM spans WHERE span_type = 'full_query_lifecycle' GROUP BY status", "refId": "A" }
        ]
      },
      {
        "type": "timeseries",
        "title": "Latency Over Time (Generation vs Retrieval)",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 6 },
        "datasource": { "uid": "bfv8qs0pp6osga", "type": "mysql" },
        "targets": [
          { "format": "time_series", "rawSql": "SELECT start_time AS time, duration_ms/1000 AS value, span_type AS metric FROM spans WHERE span_type IN ('llm_generation', 'retrieve_context') ORDER BY start_time ASC", "refId": "A" }
        ],
        "fieldConfig": { "defaults": { "unit": "s", "custom": { "drawStyle": "line", "lineWidth": 2, "pointSize": 5, "showPoints": "always" } } }
      },
      {
        "type": "table",
        "title": "Failure Logs (AgentOps Diagnosis)",
        "gridPos": { "h": 6, "w": 12, "x": 0, "y": 14 },
        "datasource": { "uid": "bfv8qs0pp6osga", "type": "mysql" },
        "targets": [
          { "format": "table", "rawSql": "SELECT start_time, span_type, error_message FROM spans WHERE status = 'error' OR status = 'failure' ORDER BY start_time DESC LIMIT 10", "refId": "A" }
        ]
      }
    ]
  },
  "overwrite": True
}

response = requests.post("http://localhost:3000/api/dashboards/db", json=dashboard_payload, auth=("admin", "admin"))
print(response.status_code)
