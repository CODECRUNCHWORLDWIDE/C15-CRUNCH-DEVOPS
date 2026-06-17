# Week 6 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** Which of the following is the **correct** definition of *immutable infrastructure* in one sentence?

- A) A server you can SSH into but never modify the `/etc/` directory.
- B) A server whose configuration is derived from a baked image plus boot-time data, never modified in place — to "patch" it, you rebuild the image, boot a new instance, drain the old, and destroy the old.
- C) A server that is read-only from the kernel's perspective.
- D) A server that runs only stateless services.

---

**Q2.** A teammate proposes turning `selfHeal: false` on an Argo CD `Application` in the production cluster because "we want a human in the loop." Which of the following is the **best** rebuttal?

- A) `selfHeal: false` is deprecated as of Argo CD 2.10.
- B) With `selfHeal: false`, Argo only reports drift; it does not correct it. Drift accumulates between human-triggered syncs, and the human is rarely as careful as you wanted. In prod, this means production slowly diverges from `main`, and the "what is in prod right now?" question gets harder to answer. Self-heal on is what makes the repo the source of truth in practice, not just in principle.
- C) `selfHeal: true` runs faster than `selfHeal: false`.
- D) The Argo project lead has stated on Twitter that `selfHeal: false` is a code smell.

---

**Q3.** The four OpenGitOps principles are: declarative, versioned-and-immutable, pulled-automatically, and continuously-reconciled. Which principle does a CI pipeline that runs `kubectl apply -f manifests/` on every merge to `main` violate?

- A) Declarative (kubectl is imperative).
- B) Versioned and immutable (CI does not version anything).
- C) Pulled automatically (CI is pushing, not pulling).
- D) Continuously reconciled (CI runs at merge time and not again).

---

**Q4.** Which of the following is the **correct** description of the build-droplet lifecycle in a `packer build`?

- A) Packer leaves the build droplet running and you destroy it manually.
- B) Packer boots a transient droplet from the base image, runs provisioners against it, snapshots the result, and destroys the build droplet at the end of every build — successful or failed (unless `-on-error=abort` is set).
- C) The build droplet is the same droplet your application runs on; Packer pauses the app while it provisions.
- D) Packer does not use a droplet; it builds the image locally in a chroot.

---

**Q5.** A `flux bootstrap github ...` command was successful. Which of the following is the **correct** description of what is now in the config repo and the cluster?

- A) Flux is installed in the cluster; nothing was written to the repo.
- B) Flux is installed in the cluster *and* Flux's own install manifests have been committed to the config repo at the `--path` you specified, and a `GitRepository`+`Kustomization` pair now reconciles the cluster against that path. Flux is managing itself.
- C) Flux has cloned the repo to the cluster's filesystem; future commits update the local clone.
- D) Flux has installed a webhook on the GitHub repo; pushes to `main` trigger the install.

---

**Q6.** Which of the following is the **strongest** argument for the pull model over the push model of deployments?

- A) The pull model is faster (lower deploy latency).
- B) The pull model gives the CI pipeline a smaller blast radius if compromised: CI only needs git-push permission, not credentials to the target environment. The cluster's credentials never leave the cluster.
- C) The pull model is required by Kubernetes; the push model is deprecated.
- D) The pull model produces better commit messages.

---

**Q7.** A new CVE drops against `openssl`. Your fleet's Packer-baked image has the vulnerable version. Which of the following is the **correct** response under the rebuild-vs-patch rule?

- A) SSH into each droplet, `apt-get install -y openssl`, restart affected services. Five minutes total.
- B) Trigger a Packer build with the latest `apt-get update` baked in, promote the new snapshot to the config repo, roll the fleet via the reconciler. The fix is durable: the next instance booted from the image is also patched, with no separate human action.
- C) Wait for the next scheduled image rebuild. CVEs are routine; rolling out of cycle is risky.
- D) Set `selfHeal: false` and ignore the CVE.

---

**Q8.** In the Flux architecture, **source-controller** is responsible for which of the following?

- A) Reading `Kustomization` resources and applying the resulting manifests to the cluster.
- B) Reading `GitRepository`, `OCIRepository`, `HelmRepository`, and `Bucket` resources, pulling the source content, and producing an in-cluster artifact that other controllers consume.
- C) Sending notifications to Slack, GitHub, and PagerDuty when reconciliations succeed or fail.
- D) Rendering Helm charts.

---

**Q9.** The Argo CD *app of apps* pattern lets you bootstrap many `Application` resources from a single one. Which of the following is the **correct** description of the pattern?

- A) One `Application` is templated into many `Application` resources by a generator.
- B) The first `Application` you create by hand points at a directory in the config repo containing many other `Application` YAML files. Argo syncs those YAMLs into the cluster, which causes Argo to create the per-app `Application` resources, which causes Argo to sync the per-app sources. The whole tree boots from one `kubectl apply`.
- C) The pattern is an Argo CD UI feature, not a configuration pattern.
- D) The pattern is deprecated as of Argo CD 2.0 in favor of `ApplicationSet`.

---

**Q10.** A teammate adds a `breakpoint` provisioner to a Packer build and runs `packer build -on-error=ask`. The build pauses. What did the teammate want, and what should they do next?

- A) The teammate paused the build by accident; they should re-run with `-on-error=abort`.
- B) The teammate paused the build to SSH into the still-running build droplet and inspect its state. The droplet's IP is in the Packer output; the teammate can `ssh root@<ip>` (Packer printed the SSH command), debug interactively, then press a key in the Packer console to resume or abort.
- C) The `breakpoint` provisioner is deprecated; the teammate should remove it.
- D) The teammate wanted to skip a provisioner; `-on-error=ask` lets them choose.

---

## Answers

1. **B.** Immutable infrastructure is configuration-derived-from-image-plus-boot-data, never modified in place. To patch, you rebuild and replace.
2. **B.** `selfHeal: false` lets drift accumulate; the in-the-loop human is the weak link, not the safety. Turn it on in prod.
3. **D.** Continuously reconciled — the CI runs at merge time and not again, so drift is undetected and uncorrected.
4. **B.** Packer's build droplet is transient: boot, provision, snapshot, destroy. Same lifecycle in every build, on every cloud.
5. **B.** `flux bootstrap` installs Flux *and* commits its own install manifests to the repo, then has Flux reconcile itself. Self-bootstrapping is the default shape.
6. **B.** Smaller blast radius for compromised CI. The pull model is defense in depth; the cluster's credentials stay in the cluster.
7. **B.** Rebuild, promote, roll. Patching one droplet is a snowflake; the next instance booted from the unpatched image regresses the fix.
8. **B.** source-controller pulls sources; it produces artifacts that other controllers consume. It does not apply anything.
9. **B.** *app of apps* is the bootstrap-many-Applications-from-one pattern. The root `Application` is the only thing you `kubectl apply` by hand.
10. **B.** The `breakpoint` provisioner with `-on-error=ask` is for interactive debugging of a build. The teammate SSHs into the build droplet, inspects, then resumes or aborts in Packer.

---

*If you missed more than two, re-read the relevant lecture section before moving on. The decision-rule (Q7) and the pull-model arguments (Q3, Q6) are the conceptual foundations of every week from here forward; the others are mechanics you will pick up by repetition.*
