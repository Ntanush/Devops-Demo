# DevOps Demo – GitHub → Harness → Kubernetes (one-day lab)

```
devops-demo/
├── app/                  Flask app (/, /health, /load, /metrics) + tests
├── Dockerfile
├── k8s/                  Namespace, Deployment, Service, HPA, RBAC (plain kubectl)
├── istio/                v2 deployment + Gateway, canary VirtualService, mTLS
└── harness/              Harness manifests (templated) + reference pipeline.yaml
```

Use a **personal laptop** (min 16 GB RAM recommended for Istio). Commands are for bash
(Mac/Linux/Git Bash on Windows).

## Phase 0 – Install (1:30–2:00)
Docker Desktop, git, kubectl, minikube, helm, istioctl. Accounts: GitHub, Docker Hub, Harness (free).
```bash
minikube start --cpus 4 --memory 8192
minikube addons enable metrics-server
kubectl get nodes
```

## Phase 1 – Run locally + push to GitHub (2:00–2:45)
```bash
cd app && pip install -r requirements.txt && python -m pytest -q && python app.py
# open http://localhost:8080  and  http://localhost:8080/metrics
cd ..
docker build -t devops-demo:local . && docker run -p 8080:8080 devops-demo:local

git init && git add . && git commit -m "initial devops demo"
git branch -M main
git remote add origin https://github.com/<you>/devops-demo.git
git push -u origin main
```

## Phase 2 – Manual deploy to Kubernetes (2:45–3:30)
```bash
# build images directly into minikube's image store
minikube image build -t devops-demo:v1 .
minikube image build -t devops-demo:v2 .

kubectl apply -f k8s/01-namespace.yaml -f k8s/02-deployment.yaml -f k8s/03-service.yaml
kubectl -n demo get pods,svc
```
**Open from mobile / another laptop (same Wi-Fi):**
```bash
kubectl -n demo port-forward svc/devops-demo 8080:80 --address 0.0.0.0
# find laptop IP:  Mac: ipconfig getifaddr en0   Windows: ipconfig   Linux: hostname -I
# phone browser -> http://<laptop-ip>:8080   (allow port 8080 in the firewall if blocked)
```
Refresh a few times – the pod name changes (load balancing across replicas).
Different network? `cloudflared tunnel --url http://localhost:8080` gives a public https URL.

> Note: Istio injection is on for the `demo` namespace label. Before Phase 7, either
> install Istio first or remove the label: `kubectl label ns demo istio-injection-`

## Phase 3 – Harness setup (3:45–5:15)
1. Create project `devops_lab`.
2. **Delegate**: Project Settings → Delegates → New → Kubernetes → Helm. Run the given
   `helm upgrade -i ...` command against minikube. Wait until it shows Connected.
3. **Connectors**: GitHub (`github_conn`, PAT stored as Harness secret),
   Docker Hub (`dockerhub_conn`), Kubernetes cluster (`minikube_k8s`, "use delegate credentials").
4. **Service** `devops_demo_svc`: type Kubernetes, manifests = `harness/manifests/deployment.yaml`
   + `values.yaml` from GitHub; artifact = Docker Hub `<you>/devops-demo`, identifier `dockerhub_image`.
5. **Environment** `dev` (Pre-Production) → **Infrastructure** `minikube_demo`, connector
   `minikube_k8s`, namespace `demo`.
6. **Pipeline**: CI stage (Harness Cloud) → CD stage (Rolling). Compare with `harness/pipeline.yaml`.
7. Run it. Watch: clone → test → build/push → rolling deploy → smoke test.

## Phase 4 – Full GitOps-style loop (5:15–5:45)
- Add a **Trigger**: Pipeline → Triggers → GitHub → on Push to `main`.
- Change `APP_COLOR` default or the heading in `app.py`, commit, push.
- Watch the pipeline auto-run, then `kubectl -n demo get pods -w` for the rolling update,
  then refresh your phone. **This is the whole DevOps loop.**
- Break a test on purpose → pipeline fails at CI, nothing deploys. Break `/health` → readiness fails → rollback.

## Phase 5 – HPA autoscaling (5:45–6:30)
```bash
kubectl apply -f k8s/04-hpa.yaml
kubectl -n demo get hpa -w            # terminal 1
kubectl -n demo run load --rm -it --image=busybox --restart=Never -- \
  sh -c "while true; do wget -q -O- http://devops-demo/load >/dev/null; done"   # terminal 2
kubectl -n demo get pods -w           # terminal 3: replicas 2 -> up to 6, then scale down ~5 min after stopping
```

## Phase 6 – RBAC (7:15–8:00)
```bash
kubectl apply -f k8s/05-rbac.yaml
SA=system:serviceaccount:demo:dev-viewer
kubectl auth can-i list pods   -n demo    --as=$SA   # yes
kubectl auth can-i delete pods -n demo    --as=$SA   # no
kubectl auth can-i list pods   -n default --as=$SA   # no (namespace scoped)
kubectl auth can-i patch deployments -n demo --as=system:serviceaccount:demo:deployer  # yes
kubectl auth can-i create roles      -n demo --as=system:serviceaccount:demo:deployer  # no
```
Also try Harness RBAC: Account Settings → Access Control → create a user group with
"Pipeline Executor" only (can run, not edit).

## Phase 7 – Istio service mesh (8:00–9:15)
```bash
istioctl install --set profile=demo -y
kubectl label ns demo istio-injection=enabled --overwrite
kubectl -n demo rollout restart deploy      # pods now show 2/2 (app + envoy sidecar)
kubectl apply -f istio/01-deployment-v2.yaml -f istio/02-traffic.yaml
kubectl -n istio-system port-forward svc/istio-ingressgateway 8081:80 --address 0.0.0.0
# phone -> http://<laptop-ip>:8081 : ~80% blue (v1), ~20% green (v2)
```
Change weights to 50/50 then 0/100 in `02-traffic.yaml` and re-apply = canary promotion.
Observability (your area):
```bash
kubectl apply -f <istio-dir>/samples/addons/prometheus.yaml
kubectl apply -f <istio-dir>/samples/addons/kiali.yaml
kubectl apply -f <istio-dir>/samples/addons/grafana.yaml
istioctl dashboard kiali      # live traffic graph, mTLS padlocks, success rates
```
Low on RAM? Use Linkerd instead of Istio (lighter), skip the canary YAML.

## Cleanup
```bash
minikube stop      # or: minikube delete
```
