# Week 11 — Challenges

Two challenges. Pick one. Both are open-ended; the grading is rubric-based, not test-based. Budget 3 to 5 hours.

| # | Title                                              | Difficulty | File                                                      |
| - | -------------------------------------------------- | ---------- | --------------------------------------------------------- |
| 1 | Scheduled scale-down for staging environments      | Medium     | `challenge-01-scheduled-scaledown.md`                     |
| 2 | A second-generation cost anomaly detector          | Hard       | `challenge-02-anomaly-detector-v2.md`                     |

Both challenges build directly on Exercises 1 to 3. You will need the cluster from Exercise 1 still running.

## Submission

For either challenge, produce:

1. The code or manifests you wrote.
2. A short write-up (~500 words) explaining the design choices, the trade-offs you considered, and the limitations of your implementation.
3. Evidence the implementation works — pod logs, OpenCost screenshots, before-and-after cost reports.

The write-up is more important than the code volume. The grader reads it first.

## Grading rubric

Both challenges are graded on:

- **Correctness** (40 percent). Does the implementation do what is asked.
- **Design quality** (30 percent). Are the trade-offs reasonable. Is the code or manifest readable.
- **Operational thinking** (20 percent). Did you consider failure modes, rollback, observability of the system you built.
- **Write-up** (10 percent). Is it clear what you did and why.

A passing submission scores 60 percent overall. A strong submission scores 80 percent or higher.
