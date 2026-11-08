# Container Checklist

## Dockerfile

```dockerfile
# build stage
FROM python:3.11-slim@sha256:<digest> AS build
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# runtime stage
FROM python:3.11-slim@sha256:<digest>
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=app:app . .
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Adapt the language and server; keep the structure: pinned base, separate build and runtime, non-root, no secrets.

## Kubernetes workload essentials

| Field | Guidance |
|---|---|
| `resources.requests` | Measured typical usage; decides scheduling |
| `resources.limits.memory` | Above peak usage; OOMKilled means too low or a leak |
| CPU limits | Optional; throttling can hurt latency — follow the cluster's policy |
| `readinessProbe` | "Can serve traffic now" |
| `livenessProbe` | "Is stuck and must restart"; generous thresholds |
| `startupProbe` | Slow-starting apps, protects against early liveness kills |
| `terminationGracePeriodSeconds` + SIGTERM handling | Finish in-flight requests |

## Debugging

| Symptom | First checks |
|---|---|
| `CrashLoopBackOff` | `kubectl logs --previous`, config/secret missing, wrong command |
| `OOMKilled` | Memory limit vs usage, leaks, JVM/runtime heap settings |
| `ImagePullBackOff` | Tag exists, registry credentials, architecture (amd64/arm64) |
| `Pending` | Requests too large, node selectors/taints, PVC binding |
| Not receiving traffic | Readiness failing, Service selector labels, Ingress rules |
