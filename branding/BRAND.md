# C15 · Crunch DevOps — Brand Guide

> **Voice:** post-mortem-grade. Specific timestamps, specific impact, no blame.
> **Feel:** the inside of a clean Grafana dashboard at 4 AM — restrained, accurate, useful.

Extends the family brand. C15-specific overrides only.

---

## Identity

- **Full name:** Crunch DevOps
- **Program code:** C15
- **Full title in copy:** *C15 · Crunch DevOps*
- **Tagline (short):** Ship it. Then keep it shipped.
- **Tagline (long):** A free, open-source twelve-week DevOps / SRE track — Docker, Kubernetes, Terraform, CI/CD, observability, secrets, and an incident-response runbook you'd actually use at 3 AM.
- **Canonical URL:** `codecrunchglobal.vercel.app/course-c15-devops`
- **License:** GPL-3.0

---

## Where C15 diverges from the family palette

Inherits Ink/Parchment/Gold. Adds **SRE Blue** for "green build / healthy service" semantics and **Alert Red** (shared with C6) for "page-worthy" signals — together they form the C15 traffic-light system:

| Role | Name | Hex | Use |
|------|------|-----|-----|
| Accent | SRE Blue | `#2563EB` | The C15 mark, healthy-build indicators, "synced" GitOps state |
| Accent deep | SRE Blue deep | `#1E40AF` | Hover, eyebrows |
| Accent soft | SRE Blue soft | `#BFDBFE` | Subtle background of "healthy" rows in status tables |
| Status — Healthy | Green | `#15803D` | Inherited from C10's palette family |
| Status — Warning | Amber | `#D97706` | "Degraded" status |
| Status — Critical | Alert Red | `#EF4444` | "Page now" status |

```css
:root {
  --sre-blue:      #2563EB;
  --sre-blue-deep: #1E40AF;
  --sre-blue-soft: #BFDBFE;
  --status-good:    #15803D;
  --status-warn:    #D97706;
  --status-crit:    #EF4444;
}
```

> **Why a traffic-light system:** because operations is graded in colors. The whole point of observability is that "what color is this dashboard" answers "should I be awake?" The brand should reinforce that pattern, not fight it.

### Typography

EB Garamond display, Lora body, JetBrains Mono for any command, container image tag, port, version pin, alert rule, runbook step. Mono is the "this is operational truth" face.

---

## Recurring page elements

### The "status panel"

Every operational lecture includes one or more status panels:

```
┌─────────────────────────────────────────────────────┐
│  SERVICE STATUS — crunchwriter-api                  │
│                                                     │
│  Health:   ● healthy        p99 latency: 124 ms     │
│  Replicas: 3 / 3 ready      error rate:  0.02 %     │
│  Build:    a7c3f1d           uptime:     14 d 7 h    │
│  Last alert: none in 24 h                           │
└─────────────────────────────────────────────────────┘
```

Color discipline: the dot is `--status-good` (green), `--status-warn` (amber), or `--status-crit` (red). Never decorative; always semantic.

### The "post-mortem template"

The track's signature deliverable. Recurring shape on every incident lecture and the capstone:

```markdown
## Incident: <one-line summary>

### Impact
- Duration: HH:MM UTC → HH:MM UTC (X minutes)
- Users affected: <metric>
- Revenue / SLO impact: <metric>

### Timeline (UTC)
- HH:MM  Detection — alert fired on <metric>
- HH:MM  Acknowledged by on-call
- HH:MM  Mitigation deployed
- HH:MM  Verified resolved
- HH:MM  All-clear

### Root cause

### Resolution

### What went well

### What didn't

### Action items
- [ ] <owner> — <action> — <due>
```

**Blameless** is a rule, not a vibe. C15 voice models that in every example. We use "the deploy at 14:02 introduced X" — never "Alice's deploy."

---

## Voice rules

- **Cite the timestamp.** Always UTC. Always exact to the minute. Operations runs on receipts.
- **Cite the metric.** "p99 latency rose from 120 ms to 1.4 s" — not "the service got slow."
- **Distinguish symptom from cause.** "We saw 502s (symptom). The cause was an upstream timeout in the Redis client (cause)."
- **Don't shame past engineers.** "The 2024-built migration ran into a constraint that wasn't visible when it was written" — not "this migration is bad."
- **No "rockstar" or "ninja" — anywhere.** Not even in jokes about on-call. Especially not in jokes about on-call.

---

## Course page conventions

The course page (`course-c15-devops.html`, future) uses an inverted variant (Ink background, Parchment text) with a stylized status-board grid of small panels as the hero. SRE Blue for the program code; green/amber/red dots scattered to evoke a dashboard. The 12-week ladder is rendered as a deployment pipeline (stages connecting left to right).

---

*GPL-3.0. Fork freely.*
