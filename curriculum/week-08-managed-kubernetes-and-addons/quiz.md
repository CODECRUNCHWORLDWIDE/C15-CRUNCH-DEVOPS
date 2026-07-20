# Week 8 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** Which of the following is the **most accurate** one-paragraph description of why managed Kubernetes is the default in 2026?

- A) Managed Kubernetes is cheaper than self-managed because cloud providers operate at scale.
- B) Managed Kubernetes is the default because the operational cost of running etcd correctly is high (subtle WAL management, snapshot ordering, member replacement during partitions) and outsourcing that cost to a cloud provider — for $0-$73/month — costs less than the engineering hours required to operate etcd in-house. Everything else in the control plane is also operated, but etcd is the load-bearing reason.
- C) Managed Kubernetes is mandated by every major compliance framework as of 2024.
- D) Managed Kubernetes is the default because self-managed clusters cannot run on cloud VMs due to networking restrictions.

---

**Q2.** Which of the following describes the **practical difference** between GKE Autopilot and GKE Standard?

- A) Autopilot is a faster Kubernetes; Standard is slower.
- B) Autopilot is older and being deprecated; Standard is the modern default.
- C) On Standard you manage node pools (machine types, sizes, scaling); on Autopilot Google manages node pools too — you submit pods, Google provisions and bills per-pod-vCPU-second, and you do not see node-pool resize events. Same Kubernetes API, same manifests; different operational boundary.
- D) Autopilot is for single-tenant workloads; Standard is for multi-tenant.

---

**Q3.** A pod on GKE Autopilot is failing to start with the error `pod has unbound immediate PersistentVolumeClaims` and the manifest contains a `hostPath` volume. Which of the following is the **correct diagnosis**?

- A) Autopilot's StorageClass is misconfigured.
- B) Autopilot does not support `hostPath` volumes. The node is ephemeral from your perspective (Google may replace it), so a hostPath has no defined meaning. Use a `PersistentVolume` backed by a CSI driver for cross-pod persistence or an `emptyDir` for ephemeral.
- C) The pod needs a higher resource request to schedule on Autopilot.
- D) The PVC controller is broken.

---

**Q4.** Which of the following is the **correct** description of Workload Identity (GCP)?

- A) A mechanism for distributing static JSON keys to pods.
- B) A binding between a Kubernetes ServiceAccount and a GCP IAM service account, configured via a KSA annotation plus an IAM policy binding granting `roles/iam.workloadIdentityUser`. When a pod with the bound KSA calls a Google API, the GKE metadata server exchanges the pod's projected service account token for a short-lived GSA token. No long-lived secret on disk; rotation is automatic.
- C) A replacement for Kubernetes RBAC.
- D) A way to share GCP API tokens across pods in a namespace.

---

**Q5.** You are installing NGINX Ingress Controller on a kind cluster for the first time. Which of the following Helm flags is **specific to the kind use case** and unnecessary on GKE / EKS / AKS?

- A) `--set controller.replicas=2`
- B) `--set controller.hostPort.enabled=true --set controller.kind=DaemonSet --set "controller.nodeSelector.ingress-ready=true"` — these expose NGINX on the kind node's host port (which is then forwarded to the laptop via kind's `extraPortMappings`). On a managed cluster, you would use `--set controller.service.type=LoadBalancer` to let the cloud provision an external IP instead.
- C) `--set controller.image.tag=stable`
- D) `--set controller.minReadySeconds=10`

---

**Q6.** Which of the following correctly describes how **cert-manager** issues a TLS certificate using a Let's Encrypt `ClusterIssuer` and the HTTP-01 solver?

- A) cert-manager generates a self-signed certificate; Let's Encrypt's involvement is to sign cert-manager's request.
- B) cert-manager submits an ACME order to Let's Encrypt; Let's Encrypt responds with a challenge that requires serving a specific token at `http://<host>/.well-known/acme-challenge/<token>`; cert-manager injects a temporary Ingress rule routing that path to its solver pod; Let's Encrypt fetches the token; cert-manager removes the temporary rule; Let's Encrypt issues the certificate; cert-manager stores it in the Secret named in the Certificate resource.
- C) cert-manager copies a pre-installed certificate from a Kubernetes Secret.
- D) cert-manager pulls certificates from a private CA hosted by GKE.

---

**Q7.** Which of the following is the **correct** description of ArgoCD's `selfHeal` and `prune` features?

- A) `selfHeal` is a one-time bootstrap; `prune` is a backup mechanism.
- B) `selfHeal: true` causes ArgoCD to revert any manual change to a resource ArgoCD owns, returning it to the Git-declared state. `prune: true` causes ArgoCD to delete cluster resources when their manifests are removed from Git. Together, they make Git the strict source of truth: nothing in the cluster persists that is not in Git, and nothing in Git is missing from the cluster.
- C) `selfHeal` repairs damaged Pods; `prune` removes unused images.
- D) `selfHeal` and `prune` are deprecated as of ArgoCD 2.5.

---

**Q8.** On GKE Standard, a Deployment's pods are scheduling onto a node pool whose taints they tolerate, but they all land on a single node and the node is at capacity. Other node pools have space. Which of the following is the **most likely** cause?

- A) The cluster autoscaler is disabled on the busy node pool.
- B) The pods have a `nodeSelector` that pins them to the busy node pool's label, even though their tolerations are broader. `nodeSelector` is a hard constraint; tolerations only permit scheduling on tainted nodes — they do not pull pods toward them. The fix is to remove the `nodeSelector` (or change it to allow multiple pools) or to enable the cluster autoscaler on the busy pool.
- C) The kubelet on the other node pools is misbehaving.
- D) The Deployment's strategy is `Recreate` instead of `RollingUpdate`.

---

**Q9.** A team wants to expose ArgoCD's UI on a public hostname with a valid Let's Encrypt certificate. The cluster has NGINX Ingress and cert-manager installed. Which of the following is the **correct** Ingress shape?

- A) An Ingress with `tls` block pointing at a hand-uploaded `Secret` containing a copy of the Let's Encrypt certificate.
- B) An Ingress annotated with `cert-manager.io/cluster-issuer: letsencrypt-prod` (so cert-manager auto-creates the Certificate resource) plus `nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"` (because the ArgoCD server speaks HTTPS to its upstream). For ssl-passthrough mode, add `nginx.ingress.kubernetes.io/ssl-passthrough: "true"` and ensure the NGINX controller was installed with `--enable-ssl-passthrough`.
- C) A `Service` of type `LoadBalancer` directly pointed at the argocd-server pod; no Ingress needed.
- D) An Ingress in the `cert-manager` namespace (because that is where the certificates live).

---

**Q10.** Which of the following is the **best** description of why the four canonical add-ons (NGINX Ingress, cert-manager, external-dns, ArgoCD) are installed open-source rather than using the cloud-provider's bundled equivalents (GKE Gateway, Google-managed certificates, Cloud DNS, Cloud Deploy)?

- A) The open-source versions are always cheaper.
- B) The open-source versions keep the manifest surface portable across kind / GKE / EKS / AKS / bare metal — the YAML you write is the same on every cluster. The cloud-bundled equivalents work well but tie the manifests to provider-specific annotations and behaviors. Open-source-first keeps the migration story bounded (a handful of well-known differences) rather than unbounded (a rewrite of every manifest).
- C) The cloud-bundled options are unreliable.
- D) The open-source options are mandated by CNCF certification.

---

## Answers

1. **B.** Managed Kubernetes wins because etcd's operational burden is high and outsourcing it is cheap. Everything else in the control plane is operated too, but etcd is the load-bearing reason. The cost differential ($0-$73/month managed vs $7,000+/month in engineering time for self-managed) is the practical evidence.
2. **C.** Autopilot is GKE where Google manages the data plane too. Same API, same manifests, different boundary of "Google's responsibility." Per-pod billing replaces per-node billing.
3. **B.** Autopilot does not support `hostPath` volumes. The node is ephemeral; hostPath is meaningless. Use PV+CSI for cross-pod persistence or emptyDir for ephemeral. This is one of the canonical Autopilot constraints (Lecture 2 Section 3).
4. **B.** Workload Identity binds a KSA to a GSA via annotation + IAM policy binding. Short-lived tokens, no long-lived secret. Equivalents on AWS (IRSA) and Azure (AAD Workload Identity) follow the same pattern with different plumbing.
5. **B.** `hostPort` + `DaemonSet` + `nodeSelector: ingress-ready=true` is the kind-specific recipe (NGINX binds to the kind node's port, forwarded to the laptop via `extraPortMappings`). On a managed cluster, `controller.service.type=LoadBalancer` is the equivalent (the cloud provisions an external IP for the Service).
6. **B.** The ACME HTTP-01 flow: order, challenge, prove ownership by serving a token at a well-known URL, issuance. cert-manager handles the choreography; the cluster's Ingress + the solver pod serve the challenge token; Let's Encrypt fetches it and issues.
7. **B.** `selfHeal: true` reverts drift; `prune: true` deletes resources removed from Git. Together they make Git the strict source of truth. Both are configured under `syncPolicy.automated`.
8. **B.** `nodeSelector` is a hard constraint that *pins* pods to nodes with the matching label; tolerations only *permit* scheduling on tainted nodes — they do not pull pods toward them. The fix is to remove the nodeSelector or to use a softer `nodeAffinity` with multiple match expressions.
9. **B.** The cert-manager Ingress annotation auto-creates the Certificate. For an HTTPS upstream (ArgoCD server), the `backend-protocol: HTTPS` annotation tells NGINX the upstream protocol. For ssl-passthrough (preserving the TLS handshake end-to-end), `ssl-passthrough: true` is added — and NGINX must be installed with the passthrough flag.
10. **B.** Portability. The open-source stack works on every cluster with the same YAML; cloud-bundled equivalents introduce provider-specific annotations and behaviors. The trade-off is that you operate the open-source add-on yourself; the trade-off is small (Helm upgrade twice a year per add-on) and the portability gain is large.

---

*If you missed more than two, re-read the relevant lecture before the mini-project. Q3 (Autopilot constraints), Q4 (Workload Identity), Q7 (selfHeal/prune), and Q8 (nodeSelector vs tolerations) are the four most common interview questions on these topics in 2026; expect them in technical screens for any platform/SRE role.*
