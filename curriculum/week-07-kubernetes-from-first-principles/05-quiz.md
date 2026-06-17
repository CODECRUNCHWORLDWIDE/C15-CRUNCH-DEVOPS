# Week 7 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** Which of the following is the **most accurate** one-paragraph description of the problem Kubernetes solves?

- A) Kubernetes is a container runtime that runs OCI images on a single host.
- B) Kubernetes is a declarative API plus a set of controllers that converge a cluster's actual state toward a declared desired state. It solves placement (which host runs which container), restart (what happens when something crashes), rolling updates (how to ship v2 without taking v1 down), service discovery (how clients find pods whose IPs change), and configuration injection (how to get config and secrets into pods).
- C) Kubernetes is a load balancer with a YAML interface.
- D) Kubernetes is a replacement for Linux's systemd that schedules processes across machines.

---

**Q2.** A teammate proposes "let's have our CI job write directly to etcd to register a deploy" because "going through the API server is slow." Which of the following is the **best** rebuttal?

- A) etcd does not accept HTTP requests; only the API server can talk to it.
- B) The API server is the only contract layer in Kubernetes: it authenticates, authorizes, validates, mutates, and notifies watchers on every write. Bypassing it skips all five and leaves the cluster in a state controllers do not know how to reason about. The API server is faster than your teammate thinks; the "slowness" they perceived is something else.
- C) etcd is read-only from outside the API server's TLS scope.
- D) Writing to etcd directly is allowed but discouraged.

---

**Q3.** A Pod is stuck in the `Pending` state. Which `kubectl` command is the **first** one you run?

- A) `kubectl logs <pod>`
- B) `kubectl exec <pod> -- ps aux`
- C) `kubectl describe pod <pod>` (and read the `Events:` section, which will name the scheduling constraint that failed)
- D) `kubectl delete pod <pod>` and hope it comes back healthier

---

**Q4.** Which of the following correctly describes the relationship between a **Deployment**, a **ReplicaSet**, and the **Pods** they produce?

- A) A Deployment is a synonym for a ReplicaSet; they refer to the same controller with two names.
- B) A Deployment manages one or more ReplicaSets (one per `spec.template` hash; usually only one is non-zero at a time). Each ReplicaSet manages N Pods. Deletion cascades via `ownerReferences`: deleting the Deployment deletes its ReplicaSets, which deletes its Pods.
- C) A Pod is a template that is materialized into a ReplicaSet, which is materialized into a Deployment.
- D) Deployments only exist in the `apps/v1beta1` API; modern clusters use ReplicaSets directly.

---

**Q5.** A Service has `selector: {app: hello}` but `kubectl get endpointslice` shows zero endpoints. The Pods labeled `app: hello` are healthy. Which of the following is the **most likely** root cause?

- A) The Service is missing a `port` field; without it the cluster does not create endpoints.
- B) There is a label-selector mismatch — the Pods either have a typo on the `app` label, are in a different namespace from the Service, or are not actually labeled `app=hello`. `kubectl get pods --show-labels` and comparing against the Service's selector reveals the diff.
- C) The cluster's `kube-proxy` is misconfigured.
- D) The Service's `type` is wrong; only `LoadBalancer` Services have endpoints.

---

**Q6.** Which of the following is the **correct** description of the difference between a readiness probe and a liveness probe?

- A) Readiness and liveness probes are aliases for the same mechanism.
- B) Readiness probe failure removes the pod from the Service's endpoint list (no traffic; pod still running); liveness probe failure causes the container to be restarted. The two probes solve different problems and are tuned independently.
- C) Liveness probes run only on the first start; readiness probes run continuously.
- D) Readiness probes are deprecated as of Kubernetes 1.27 in favor of startup probes.

---

**Q7.** A ConfigMap is updated to change `LOG_LEVEL=info` to `LOG_LEVEL=debug`. The Pods that consume the ConfigMap via `envFrom.configMapRef` continue to report `LOG_LEVEL=info` in their environment for hours. Which of the following is the **correct** explanation?

- A) The cluster has a 1-hour cache for ConfigMap propagation.
- B) Environment variables sourced from a ConfigMap are evaluated at pod start; they are a snapshot. Updating the ConfigMap does not update running pods. To pick up the change, restart the pods (`kubectl rollout restart deployment/<name>`) or use a tool that hashes the ConfigMap into the Deployment's template (kustomize's `configMapGenerator`, or Helm with a hashed annotation).
- C) The pod's ServiceAccount lacks `get` permission on ConfigMaps.
- D) The ConfigMap controller is malfunctioning.

---

**Q8.** Which Kubernetes component **schedules** a pod onto a node?

- A) `kubelet` on each node.
- B) `kube-scheduler` watches for pods with empty `nodeName`, picks a node via a filter-then-score algorithm, and writes the binding. Once the binding is written, the kubelet on the chosen node sees it and starts the containers.
- C) `kube-controller-manager` does scheduling along with everything else.
- D) `etcd` schedules pods using its consensus algorithm.

---

**Q9.** You run `kubectl apply -f deployment.yaml` and then run it again 5 seconds later. The second run reports `deployment.apps/hello unchanged`. Which of the following is the **correct** description of what `kubectl apply` did?

- A) The second run was a no-op because `kubectl` cached the result locally.
- B) `kubectl apply` is idempotent. Internally it stores the last-applied configuration in an annotation on the object and computes a three-way merge between (a) the last-applied state, (b) the live state, and (c) the new YAML. When the live state already matches the new YAML, the patch is empty and the response is `unchanged`.
- C) The second apply was rejected by the API server because the object already exists.
- D) `kubectl apply` is randomly idempotent; the behavior depends on cluster load.

---

**Q10.** Which of the following is the **best** description of the *reconciliation loop* that every Kubernetes controller follows?

- A) Each controller has a complex state machine that handles each possible event explicitly.
- B) A controller watches a resource type, periodically (and on watch events) compares the desired state (the `spec`) to the actual state (`status` + side-channel observations), and acts to reduce the difference. The loop is *level-triggered*: the controller looks at the current state, not the change that produced it, so missed events do not cause bugs. The same pattern is used by every built-in controller and is what you implement when writing an operator.
- C) Controllers run once at cluster startup and never again.
- D) Controllers are deprecated in favor of admission webhooks.

---

## Answers

1. **B.** Kubernetes is a declarative API plus controllers that converge actual to desired state. The five operational properties — placement, restart, rolling updates, service discovery, configuration injection — are the *concrete* problems it solves. The word "orchestration" is jargon; the five problems are the answer.
2. **B.** The API server is the contract layer; bypassing it skips authentication, authorization, validation, mutation, and watch notifications. Controllers reason about state-via-the-API-server; direct etcd writes break the model.
3. **C.** `kubectl describe pod` and the `Events:` section. The scheduler emits events explaining why a pod is unschedulable. The answer is in the cluster; the skill is reading it.
4. **B.** Deployment owns ReplicaSets (one per template hash); ReplicaSet owns Pods; deletion cascades via `ownerReferences`. The chain is reified in `metadata.ownerReferences` on each child.
5. **B.** Label-selector mismatch is the canonical "no endpoints" cause. Compare `Service.spec.selector` with `kubectl get pods --show-labels`. Most often it is a typo on the `app` label or a namespace mismatch.
6. **B.** Readiness controls Service endpoint inclusion (gentle action); liveness controls container restart (aggressive action). Same probe schema, different consequences.
7. **B.** Env vars from a ConfigMap are snapshot-at-start. The cluster does not restart pods when a ConfigMap changes. Mitigations: `kubectl rollout restart`, or hash the ConfigMap into the Deployment template (Helm and kustomize do this).
8. **B.** `kube-scheduler`. It is the only component that decides pod placement; the kubelet *executes* on the bound node but does not pick it.
9. **B.** `kubectl apply` is idempotent via a three-way merge with the last-applied annotation. Running it twice with the same YAML produces no diff and the API returns `unchanged`.
10. **B.** Level-triggered reconciliation: watch + diff + act, robust to missed events because the controller looks at current state. The same pattern is fractal across the project.

---

*If you missed more than two, re-read the relevant lecture section before moving on. Q2 (the API-server-only-talks-to-etcd rule), Q5 (label-selector binding), Q6 (readiness vs liveness), and Q10 (the reconciliation loop) are the conceptual foundations of every week from here forward; the others are mechanics you will pick up by repetition.*
