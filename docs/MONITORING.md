# Monitoring & logging (Phase 20)

## What ships now

- Access logs via `RequestLoggingMiddleware` (`method`, `path`, `status`, `duration_ms`, `request_id`)
- Response header `X-Request-ID` for client correlation
- `GET /metrics-snapshot` for process-local counters (expand later)

## Production recommendations

| Signal | Tooling |
|--------|---------|
| Logs | Ship JSON stdout → CloudWatch / OpenSearch |
| Metrics | ALB + ECS Container Insights; later Prometheus |
| Traces | Optional OpenTelemetry once ECS is stable |
| Alerts | 5xx rate, p95 latency, SQS age, RDS CPU/storage |

Configure log aggregation outside the app (Fluent Bit / CloudWatch agent) so the API stays thin.
