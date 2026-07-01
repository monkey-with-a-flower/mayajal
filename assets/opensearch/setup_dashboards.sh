#!/bin/sh
set -eu

OPENSEARCH_URL="${OPENSEARCH_URL:-http://opensearch:9200}"
DASHBOARDS_URL="${DASHBOARDS_URL:-http://opensearch-dashboards:5601}"
INDEX_PATTERN_ID="mayajal-logs"
INDEX_PATTERN_TITLE="mayajal-logs-*"

until curl -fsS "$OPENSEARCH_URL/_cluster/health" >/dev/null; do
  echo "Waiting for OpenSearch..."
  sleep 3
done

curl -fsS -X PUT "$OPENSEARCH_URL/_index_template/mayajal-logs" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["mayajal-logs-*"],
    "template": {
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
      },
      "mappings": {
        "dynamic": true,
        "properties": {
          "@timestamp": { "type": "date" },
          "session_id": { "type": "keyword" },
          "lab_id": { "type": "keyword" },
          "user_id": { "type": "keyword" },
          "project_id": { "type": "keyword" },
          "telemetry_source": { "type": "keyword" },
          "event_type": { "type": "keyword" },
          "src_ip": { "type": "ip" },
          "dest_ip": { "type": "ip" }
        }
      }
    }
  }'

curl -fsS -X POST "$OPENSEARCH_URL/mayajal-logs-setup/_doc/telemetry-bootstrap" \
  -H "Content-Type: application/json" \
  -d '{
    "@timestamp": "2026-07-01T00:00:00Z",
    "platform": "mayajal",
    "telemetry_source": "setup",
    "event_type": "telemetry_setup",
    "session_id": "telemetry-bootstrap",
    "message": "Mayajal telemetry data view bootstrap event"
  }' >/dev/null

until curl -fsS "$DASHBOARDS_URL/api/status" >/dev/null; do
  echo "Waiting for OpenSearch Dashboards..."
  sleep 3
done

curl -fsS -X POST "$DASHBOARDS_URL/api/saved_objects/index-pattern/$INDEX_PATTERN_ID?overwrite=true" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  -d "{
    \"attributes\": {
      \"title\": \"$INDEX_PATTERN_TITLE\",
      \"timeFieldName\": \"@timestamp\"
    }
  }" >/dev/null

curl -fsS -X POST "$DASHBOARDS_URL/api/opensearch-dashboards/settings/defaultIndex" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  -d "{
    \"value\": \"$INDEX_PATTERN_ID\"
  }" >/dev/null || true

echo "Mayajal telemetry data view is ready: $INDEX_PATTERN_TITLE"
