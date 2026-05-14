# Kubernetes Deployment Guide

This guide explains how to run SupportOps Toolkit on a local Kubernetes cluster using **minikube** — free and runs entirely on your machine.

---

## Prerequisites

- [minikube](https://minikube.sigs.k8s.io/docs/start/) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/) installed
- Docker installed (minikube uses it as the driver)

---

## 1. Start minikube

```bash
minikube start --driver=docker --memory=4096 --cpus=2
```

SQL Server needs at least 2GB RAM — the `--memory=4096` flag allocates 4GB to the cluster.

---

## 2. Point Docker to minikube's registry

This lets you build the image directly into minikube without pushing to a registry:

```bash
# Linux / macOS
eval $(minikube docker-env)

# Windows PowerShell
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
```

---

## 3. Build the API image inside minikube

```bash
docker build -t supportops-api:latest .
```

---

## 4. Configure your secrets

Edit `k8s/secret.yml` and replace the base64-encoded password with your own:

```bash
# Generate base64 for your password
echo -n "YourStrong!Password123" | base64
```

Paste the output into `secret.yml` under `db-password`.

---

## 5. Apply all manifests

```bash
# Create namespace first
kubectl apply -f k8s/namespace.yml

# Apply everything else
kubectl apply -f k8s/secret.yml
kubectl apply -f k8s/sqlserver.yml
kubectl apply -f k8s/api.yml
kubectl apply -f k8s/scheduler.yml

# Enable ingress addon and apply ingress
minikube addons enable ingress
kubectl apply -f k8s/ingress.yml
```

---

## 6. Wait for pods to be ready

```bash
kubectl get pods -n supportops -w
```

Wait until all pods show `Running` and `READY 1/1` (SQL Server takes ~60 seconds).

---

## 7. Run migrations

```bash
kubectl exec -n supportops \
  $(kubectl get pod -n supportops -l app=api -o jsonpath='{.items[0].metadata.name}') \
  -- python db/migrate.py
```

Seed sample data:

```bash
kubectl exec -n supportops \
  $(kubectl get pod -n supportops -l app=api -o jsonpath='{.items[0].metadata.name}') \
  -- python db/seed.py
```

---

## 8. Access the API

```bash
# Option A — port forward directly (simplest)
kubectl port-forward -n supportops svc/api 8000:8000
# Then open http://localhost:8000/docs

# Option B — via ingress
minikube tunnel  # run in a separate terminal
# Add to hosts file: 127.0.0.1  supportops.local
# Then open http://supportops.local/docs
```

---

## Useful commands

```bash
# View all resources in the namespace
kubectl get all -n supportops

# View logs from the API
kubectl logs -n supportops -l app=api -f

# View logs from the scheduler
kubectl logs -n supportops -l app=scheduler -f

# Describe a pod (useful for debugging)
kubectl describe pod -n supportops -l app=api

# Delete everything and start fresh
kubectl delete namespace supportops
```

---

## How this compares to Docker Compose

| Feature | Docker Compose | Kubernetes |
|---|---|---|
| Purpose | Local development | Production-grade orchestration |
| Scaling | Manual (`--scale`) | Declarative (`replicas: N`) |
| Health checks | Basic | Liveness + readiness probes |
| Secrets | `.env` file | `Secret` objects |
| Networking | Automatic | Services + Ingress |
| Self-healing | No | Yes — restarts failed pods |

The Kubernetes setup mirrors what a real enterprise deployment looks like, which is why it's valuable to have in a support engineering portfolio.
