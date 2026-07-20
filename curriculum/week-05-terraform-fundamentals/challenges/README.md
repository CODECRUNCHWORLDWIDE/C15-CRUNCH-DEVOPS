# Week 5 — Challenges

The challenge is the optional sharpening exercise of the week. It is not required for graduation from C15; it is required for the engineer you want to be at the end of C15.

| Challenge | Title | Time | Difficulty |
|-----------|-------|------|------------|
| [01](./challenge-01-deploy-a-real-app-on-vps.md) | Deploy your Week 4 image on a real VPS, in Terraform | 3-4 hours | Hard |

---

## How challenges differ from exercises

- **Exercises** are scripted. You follow the steps; the steps work; you understand what happened.
- **Challenges** are open-ended. The goal is given; the steps are not. You assemble the pieces from the lecture notes, the exercises, the provider docs, and the internet. You also make taste calls — which size droplet, which region, which DNS record types, how to handle TLS — and defend them in your write-up.

Cost: about $0.50 of droplet time if you tear down within an hour or two. Same DigitalOcean credentials, same Spaces bucket from Exercise 3.

The challenge is graded on three things, in order of weight: **does it work** (you can `curl https://<your-domain>` and get a 200 from your Week 4 image), **does the code show taste** (variables named for what they are, outputs that earn their place, lifecycle hooks where they belong, no `null_resource`), and **does the write-up explain the choices** (the design rationale, the alternatives considered, the cost tradeoffs).

---

*If a challenge link 404s, please open an issue.*
