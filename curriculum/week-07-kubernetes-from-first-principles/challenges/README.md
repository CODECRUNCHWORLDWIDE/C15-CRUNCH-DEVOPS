# Week 7 — Challenges

The challenges are the optional sharpening exercises of the week. They are not required for graduation from C15; they are required for the engineer you want to be at the end of C15.

| Challenge | Title | Time | Difficulty |
|-----------|-------|------|------------|
| [01](./challenge-01-debug-a-broken-deployment.md) | Debug five broken Deployments using only `kubectl describe`, events, and logs | 2-3 hours | Hard |
| [02](./challenge-02-write-a-readiness-and-liveness-probe.md) | Write a readiness and liveness probe for a Python API with a slow startup and an occasional hang | 1-2 hours | Medium |

---

## How challenges differ from exercises

- **Exercises** are scripted. You follow the steps; the steps work; you understand what happened.
- **Challenges** are open-ended. The goal is given; the steps are not. You assemble the pieces from the lecture notes, the exercises, the provider docs, and your own taste.

Cost: $0.00. Both challenges run on the `kind` cluster from Exercises 1-3 (or a fresh one — bring-up is 60 seconds).

Each challenge is graded on three things, in order of weight:

1. **Did you find the actual root cause?** Symptoms are not causes; "the pod is in `CrashLoopBackOff`" is not a root cause.
2. **Can you explain what you did?** A teammate should be able to follow your write-up and reach the same answer.
3. **Did you use the tools the lecture promised would work?** `kubectl describe`, events, logs — not a Google search. The point of the lecture is that the cluster tells you what is wrong; the challenge is showing you can read it.

---

*If a challenge link 404s, please open an issue.*
