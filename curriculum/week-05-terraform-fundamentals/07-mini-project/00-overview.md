# Mini-Project — A Real App on DigitalOcean, Fully in Terraform

> Provision a small public-facing application on DigitalOcean: one droplet running your Week 4 image, one managed Postgres instance, one domain pointing at the droplet, one TLS certificate. All of it in Terraform. One `terraform apply` brings it up; one `terraform destroy` brings the bill to zero. Three modules, one root, remote state in the Spaces bucket from Exercise 3, every variable typed and validated, every output earning its place.

This is the synthesis project for Week 5. By doing it, you will touch every concept from both lectures: providers, resources, the state file, modules, variables, outputs, locals, `for_each`, `templatefile`, `lifecycle`, remote state, the two-phase bootstrap, and the discipline of `terraform plan -out=plan.tfplan` then `terraform apply plan.tfplan`.

**Estimated time.** 7 hours, spread across Thursday-Saturday.

**Cost.** About $12 over the 14 days of Week 5 and Week 6 if you continue into the GitOps mini-project next week. Prorated, this week's portion is about $6.

---

## What you will build

The work happens in a new repo (`c15-week-05-miniproject-<yourhandle>`). You will create a `.terraform-configs/` (or simply `infra/`) directory containing:

1. **`infra/versions.tf`** — `terraform` block, `required_providers` (DigitalOcean), `backend "s3" {}` (configured via `backend.hcl`).
2. **`infra/providers.tf`** — `provider "digitalocean"` block.
3. **`infra/variables.tf`** — variables for the image reference, domain, region, droplet size, Postgres tier, SSH key path.
4. **`infra/main.tf`** — calls three modules: `database`, `web-droplet`, `dns`.
5. **`infra/outputs.tf`** — the four outputs that matter: the URL, the database connection string (sensitive), the droplet IPv4, the `curl` smoke-test command.
6. **`infra/backend.hcl`** — backend configuration (same Spaces bucket from Exercise 3, different `key`).
7. **`infra/modules/database/`** — managed Postgres + database + user + firewall.
8. **`infra/modules/web-droplet/`** — droplet + firewall + cloud-init template.
9. **`infra/modules/dns/`** — A record + AAAA record for the domain.
10. **`infra/cloud-init.yaml.tftpl`** — the cloud-init template used by `web-droplet`.

Plus:

11. **`README.md`** — a "how to operate" section: how to apply, how to destroy, how to roll forward to a new image tag.
12. **`.gitignore`** — same as Exercise 1.
13. **`.github/workflows/terraform.yml`** — a CI workflow that runs `fmt -check`, `init -backend=false`, `validate`, and `tflint` on every PR.

---

## Acceptance criteria

- [ ] `infra/` contains the five canonical root files plus `backend.hcl` and `cloud-init.yaml.tftpl`.
- [ ] `infra/modules/database/`, `infra/modules/web-droplet/`, `infra/modules/dns/` each have the four canonical files (`versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`).
- [ ] Every variable has a `description` and a `type`.
- [ ] At least four variables across the three modules have a `validation` block.
- [ ] Every output has a `description`. Sensitive outputs are marked `sensitive = true`.
- [ ] Every module has `required_version >= 1.9.0` and `required_providers` pinned with `~>` constraints.
- [ ] Top-level `permissions: contents: read` on the `.github/workflows/terraform.yml` workflow.
- [ ] `terraform fmt -recursive -check` returns 0.
- [ ] `terraform validate` returns 0.
- [ ] `tflint --recursive` returns 0.
- [ ] `terraform plan` returns "no changes" on a re-run after `apply`.
- [ ] `curl https://<your-domain>` returns a 200 (or whatever your Week 4 app returns at `/`) with a valid Let's Encrypt certificate.
- [ ] `dig <your-domain> +short` returns the droplet's IPv4.
- [ ] State is in the Spaces bucket from Exercise 3 (`doctl spaces object list <bucket> | grep mini-project`).
- [ ] `terraform destroy` brings the bill back to zero; `doctl databases list`, `doctl compute droplet list`, `doctl compute domain records list` are all empty.
- [ ] The repo has at least three commits on `main` (initial; feat: each module; chore: destroy clean-up).

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   USER                                                                 │
│     │                                                                  │
│     │  HTTPS (443)                                                     │
│     ▼                                                                  │
│   ┌───────────────────────────────────────────────────────┐            │
│   │  DNS                                                  │            │
│   │  <yourdomain>.com    A    -> 157.245.110.42           │            │
│   │  <yourdomain>.com    AAAA -> 2604:a880:...            │            │
│   └────────┬──────────────────────────────────────────────┘            │
│            │                                                            │
│            ▼                                                            │
│   ┌───────────────────────────────────────────────────────┐            │
│   │  DROPLET  (s-1vcpu-1gb)                               │            │
│   │  ┌─────────────────────────────────────────────┐      │            │
│   │  │  Caddy  (TLS termination, port 443)         │      │            │
│   │  │   └─> reverse proxy to app:8000             │      │            │
│   │  └─────────────────────────────────────────────┘      │            │
│   │  ┌─────────────────────────────────────────────┐      │            │
│   │  │  app  (your Week 4 image, port 8000)        │      │            │
│   │  │   env: DATABASE_URL=postgres://...          │      │            │
│   │  └────┬────────────────────────────────────────┘      │            │
│   └───────┼───────────────────────────────────────────────┘            │
│           │                                                            │
│           │  postgres (5432), private network only                     │
│           ▼                                                            │
│   ┌───────────────────────────────────────────────────────┐            │
│   │  MANAGED POSTGRES  (db-s-1vcpu-1gb)                   │            │
│   │  - encrypted at rest                                  │            │
│   │  - daily backups                                      │            │
│   │  - firewall: droplet IP only                          │            │
│   └───────────────────────────────────────────────────────┘            │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

> **Status panel — target steady state**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  SERVICE STATUS — c15-w05-mini-project              │
> │                                                     │
> │  Health:    healthy        TLS:        valid LE     │
> │  Droplet:   1 / 1 running  CPU usage:  3 %          │
> │  Postgres:  online         connections: 1           │
> │  DNS:       resolving      TTL:        300 s        │
> │  Build:     <image-tag>    uptime:     <ttl>        │
> │  Last alert: none in 24 h                           │
> └─────────────────────────────────────────────────────┘
> ```

---

## Sketch of the three modules

### `infra/modules/database/`

`variables.tf`: `name_prefix`, `region`, `node_size` (default `"db-s-1vcpu-1gb"`), `engine_version` (default `"16"`), `app_db_name`, `app_db_user`, `allowed_droplet_ids` (list).

`main.tf`:

```hcl
resource "digitalocean_database_cluster" "this" {
  name       = "${var.name_prefix}-pg"
  engine     = "pg"
  version    = var.engine_version
  size       = var.node_size
  region     = var.region
  node_count = 1

  lifecycle {
    prevent_destroy = false  # toggle to true after the mini-project is in production
  }
}

resource "digitalocean_database_db" "app" {
  cluster_id = digitalocean_database_cluster.this.id
  name       = var.app_db_name
}

resource "digitalocean_database_user" "app" {
  cluster_id = digitalocean_database_cluster.this.id
  name       = var.app_db_user
}

resource "digitalocean_database_firewall" "this" {
  cluster_id = digitalocean_database_cluster.this.id

  dynamic "rule" {
    for_each = toset(var.allowed_droplet_ids)
    content {
      type  = "droplet"
      value = rule.value
    }
  }
}
```

`outputs.tf`:

```hcl
output "host" {
  value = digitalocean_database_cluster.this.host
}

output "port" {
  value = digitalocean_database_cluster.this.port
}

output "database" {
  value = digitalocean_database_db.app.name
}

output "user" {
  value = digitalocean_database_user.app.name
}

output "password" {
  value     = digitalocean_database_user.app.password
  sensitive = true
}

output "connection_string" {
  value     = "postgres://${digitalocean_database_user.app.name}:${digitalocean_database_user.app.password}@${digitalocean_database_cluster.this.private_host}:${digitalocean_database_cluster.this.port}/${digitalocean_database_db.app.name}?sslmode=require"
  sensitive = true
}
```

### `infra/modules/web-droplet/`

`variables.tf`: `name_prefix`, `region`, `size`, `image`, `ssh_key_ids`, `image_ref`, `db_url`, `domain`, `tags`.

`main.tf`:

```hcl
locals {
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    image_ref = var.image_ref
    db_url    = var.db_url
    domain    = var.domain
  })
}

resource "digitalocean_droplet" "this" {
  name      = "${var.name_prefix}-web"
  image     = var.image
  region    = var.region
  size      = var.size
  ssh_keys  = var.ssh_key_ids
  user_data = local.user_data
  tags      = var.tags

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [image]
  }
}

resource "digitalocean_firewall" "this" {
  name        = "${var.name_prefix}-web-fw"
  droplet_ids = [digitalocean_droplet.this.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
```

`outputs.tf`: `id`, `ipv4_address`, `ipv6_address`, `firewall_id`.

### `infra/modules/dns/`

`variables.tf`: `domain`, `droplet_ipv4`, `droplet_ipv6`, `ttl` (default `300`).

`main.tf`:

```hcl
resource "digitalocean_record" "a" {
  domain = var.domain
  type   = "A"
  name   = "@"
  value  = var.droplet_ipv4
  ttl    = var.ttl
}

resource "digitalocean_record" "aaaa" {
  domain = var.domain
  type   = "AAAA"
  name   = "@"
  value  = var.droplet_ipv6
  ttl    = var.ttl
}
```

`outputs.tf`: `fqdn`.

> **Note on the domain.** This module assumes the domain is already on DigitalOcean's DNS (registered there, or nameservers pointed there). If you do not own a domain, register a free `.tk` or `.ga` through Freenom, or use a `.duckdns.org` subdomain. The mini-project assumes you have one.

---

## The `cloud-init.yaml.tftpl`

```yaml
#cloud-config
package_update: true
package_upgrade: false  # do not block boot on apt upgrades
packages:
  - docker.io
  - postgresql-client-16
  - debian-keyring
  - debian-archive-keyring
  - apt-transport-https
  - curl

write_files:
  - path: /etc/caddy/Caddyfile
    content: |
      ${domain} {
        reverse_proxy localhost:8000
      }
  - path: /etc/systemd/system/app.service
    content: |
      [Unit]
      Description=app
      After=docker.service
      Requires=docker.service

      [Service]
      Restart=always
      ExecStartPre=-/usr/bin/docker stop app
      ExecStartPre=-/usr/bin/docker rm app
      ExecStartPre=/usr/bin/docker pull ${image_ref}
      ExecStart=/usr/bin/docker run --rm --name app \
        -p 127.0.0.1:8000:8000 \
        -e DATABASE_URL='${db_url}' \
        ${image_ref}

      [Install]
      WantedBy=multi-user.target

runcmd:
  - curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  - curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  - apt-get update
  - apt-get install -y caddy
  - systemctl enable caddy
  - systemctl start caddy
  - systemctl daemon-reload
  - systemctl enable app.service
  - systemctl start app.service
```

Three takeaways:

- **Caddy handles TLS automatically.** Point it at a domain, port 443 just works with Let's Encrypt. No certbot, no cron job to renew. This is the right shape for a one-droplet app.
- **The app listens on `127.0.0.1:8000` only.** Caddy proxies to it. The firewall blocks 8000 from the world; Caddy is the only ingress.
- **The DB URL goes into the environment.** Not baked into the image. The Week 4 image reads `DATABASE_URL` and that is the entire integration point.

---

## The root `main.tf`

```hcl
data "digitalocean_ssh_key" "default" {
  name = var.ssh_key_name
}

module "database" {
  source = "./modules/database"

  name_prefix         = var.name_prefix
  region              = var.region
  app_db_name         = var.app_db_name
  app_db_user         = var.app_db_user
  allowed_droplet_ids = [module.web_droplet.id]
}

module "web_droplet" {
  source = "./modules/web-droplet"

  name_prefix = var.name_prefix
  region      = var.region
  size        = var.droplet_size
  ssh_key_ids = [data.digitalocean_ssh_key.default.id]
  image_ref   = var.image_ref
  db_url      = module.database.connection_string
  domain      = var.domain
  tags        = ["c15-week-05", "mini-project"]
}

module "dns" {
  source = "./modules/dns"

  domain        = var.domain
  droplet_ipv4  = module.web_droplet.ipv4_address
  droplet_ipv6  = module.web_droplet.ipv6_address
}
```

> **The cycle.** `database` depends on `web_droplet` (the database firewall needs the droplet ID); `web_droplet` depends on `database` (the cloud-init needs the connection string). This looks like a cycle but is not: the droplet ID exists after the droplet is created; the connection string exists after the database is created. Terraform's dependency graph resolves this by creating the database first (with no firewall rules), then the droplet (with the DB URL in cloud-init), then updating the database's firewall to allow the droplet. The plan output will show the order. The `allowed_droplet_ids` argument is the key: it is set on the firewall, which is a separate resource from the cluster, and the firewall can be updated independently of the cluster's creation.

---

## The root `outputs.tf`

```hcl
output "url" {
  description = "Public URL of the app"
  value       = "https://${var.domain}"
}

output "droplet_ipv4" {
  description = "Public IPv4 of the droplet"
  value       = module.web_droplet.ipv4_address
}

output "ssh_command" {
  description = "SSH command for operator access"
  value       = "ssh root@${module.web_droplet.ipv4_address}"
}

output "smoke_test" {
  description = "Smoke-test command to confirm the app is up"
  value       = "curl -s -o /dev/null -w '%{http_code}\\n' https://${var.domain}"
}

output "database_host" {
  description = "Postgres host (private)"
  value       = module.database.host
}

output "database_connection_string" {
  description = "Postgres connection string with embedded credentials"
  value       = module.database.connection_string
  sensitive   = true
}
```

---

## Run it

```bash
cd infra/
export TF_VAR_do_token=$TF_VAR_do_token
export AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

terraform init -backend-config=backend.hcl
terraform fmt -recursive
terraform validate
tflint --recursive
terraform plan -out=plan.tfplan

# READ THE PLAN. Read it twice.

terraform apply plan.tfplan
```

Expected timing on a cold apply:

- Database cluster creation: 4-6 minutes (the slow step)
- Droplet creation: 60-90 seconds
- DNS records: 5 seconds
- Cloud-init runtime (after droplet boot): another 60-90 seconds

Total: about 8 minutes wall-clock. The first DNS resolution after `apply` returns may take an additional 1-5 minutes for global TTLs to propagate.

After apply:

```bash
terraform output smoke_test
# "curl -s -o /dev/null -w '%{http_code}\\n' https://<your-domain>"

# wait 60-90 seconds for cloud-init to finish, then:
curl -s -o /dev/null -w '%{http_code}\n' https://<your-domain>
# 200
```

If the first `curl` is `503`, Caddy is still requesting the certificate; wait 30 seconds and try again. If it is `connection refused`, the app service has not started yet; SSH in and `systemctl status app.service`.

---

## Roll forward to a new image tag

The point of all this infrastructure is that a new image tag from Week 4's CI pipeline is the smallest possible change. Edit `terraform.tfvars`:

```hcl
image_ref = "ghcr.io/<you>/<repo>:v1.1.0"  # was v1.0.0
```

```bash
terraform plan -out=plan.tfplan
# Plan: 0 to add, 1 to change, 0 to destroy.
# (the droplet's user_data changes; cloud-init re-runs on the next boot)

# but we have lifecycle { ignore_changes = [image] } AND user_data is the input
# so the plan actually shows a destroy-then-create of the droplet via
# create_before_destroy, which spins up a new droplet with the new image,
# updates the DNS A record to point at it, and destroys the old droplet.

terraform apply plan.tfplan
```

Wall-clock: about 3 minutes for the new droplet to boot and Caddy to acquire its cert. Brief DNS-propagation gap of up to TTL seconds (5 minutes at TTL=300) during which the world sees the old IP. For zero-downtime, use a load balancer; that is a Week 8 topic.

---

## Destroy

**Before you destroy: confirm you do not want to continue to Week 6 immediately.** Week 6's mini-project uses this same infrastructure as the starting point for a GitOps refactor.

If you are destroying:

```bash
terraform destroy
# Plan: 0 to add, 0 to change, 6 to destroy.
# yes
```

This takes about 4-6 minutes (the database cluster is the slow step on destroy too).

Confirm:

```bash
doctl databases list
# (empty)

doctl compute droplet list
# (empty)

doctl compute domain records list <your-domain> --format Type,Name,Data
# (only the default NS records that DigitalOcean ships, no A/AAAA records you created)

doctl spaces object list <bucket> | grep mini-project
# mini-project/terraform.tfstate (still there, mostly empty)
```

---

## Write-up

A `RUNBOOK.md` at the repo root. Five sections:

1. **How to apply from a fresh clone.** Six lines max. The exact commands a teammate would type.
2. **How to roll forward to a new image tag.** Three lines: edit `terraform.tfvars`, plan, apply.
3. **How to read the state of the world.** Three commands: `terraform output`, `curl <smoke_test>`, `ssh <ssh_command> 'systemctl status app.service'`.
4. **How to destroy.** Two lines.
5. **A post-mortem of one thing that went wrong during the build.** Use the C15 template. The likely candidates: the DB firewall ordering (chicken-and-egg between droplet and DB), the Caddy first-request 503 (cert acquisition), the DNS-not-propagated `curl` failure, the `digitalocean_record` `value` interpretation as a domain when it should be an IP. Pick one; write it up properly.

```bash
git add . RUNBOOK.md
git commit -m "feat: mini-project — droplet + postgres + dns + tls on digitalocean"
git push -u origin main
```

---

## Cost reconciliation

After destroy, check the DigitalOcean billing page:

```
https://cloud.digitalocean.com/account/billing
```

The pending bill should be no more than the prorated cost of the resources for the hours they were live. Take a screenshot. Add it to `RUNBOOK.md`. This is the receipt that closes the project: "I provisioned, I operated, I destroyed, I paid for exactly what I used."

> **Status panel — week 5 cost ledger**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  COST LEDGER — c15-week-05                          │
> │                                                     │
> │  Exercise 1:       $0.05  (droplet, 15 min)         │
> │  Exercise 2:       $0.10  (2 droplets, 15 min)      │
> │  Exercise 3:       $1.00  (Spaces, full week)       │
> │  Challenge 01:     $0.50  (droplet, 2 hours)        │
> │  Mini-project:     $6.00  (DB + droplet, 7 days)    │
> │  ───────────────────────────────────────            │
> │  Total:            $7.65  (approx)                  │
> │  Allocation:       $10 budget                       │
> └─────────────────────────────────────────────────────┘
> ```

---

*If you find errors in this material, please open an issue or send a PR. Future learners (and future you, in 2027, trying to remember how to set up Caddy with a managed Postgres) will thank you.*
