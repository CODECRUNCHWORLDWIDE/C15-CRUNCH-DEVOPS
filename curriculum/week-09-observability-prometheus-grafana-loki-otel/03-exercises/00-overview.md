# Exercises — Week 9

Four exercises, in order. Do them on the same `kind` cluster (`w09`). Each builds on the previous.

| Exercise | Topic | Time | Cost |
|---|---|---|---|
| [01](./exercise-01-install-kube-prometheus-stack.md) | Install `kube-prometheus-stack`. Verify Prometheus scrapes the cluster. | ~60 min | $0.00 |
| [02](./exercise-02-write-a-service-monitor-and-an-alert.md) | Write a `ServiceMonitor`, a `PrometheusRule`, and route an alert to a webhook. | ~75 min | $0.00 |
| [03](./exercise-03-instrument-fastapi-with-otel.md) | Instrument a FastAPI service with OpenTelemetry. Auto-instrument + manual spans. Export to Jaeger. | ~75 min | $0.00 |
| [04](./exercise-04-grafana-dashboard-as-code.md) | Commit a Grafana dashboard to a `ConfigMap`. See it provisioned. | ~45 min | $0.00 |

Solutions are in [SOLUTIONS.md](./SOLUTIONS.md). Try each exercise first; the solutions are for after, not before.

The exercises share a common `w09` kind cluster. Tear down only at the end of the week.
