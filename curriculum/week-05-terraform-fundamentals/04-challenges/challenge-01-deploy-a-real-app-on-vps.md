# Challenge 01 — Deploy a Real App on a Real VPS, in Terraform

**Goal.** Take the OCI image your Week 4 CI pipeline pushes to GHCR. Provision a DigitalOcean droplet with Terraform. Wire the droplet to pull the image at boot and run it. Expose it on port 80. SSH in to verify. Tear it down.

This is not the mini-project. The mini-project adds a managed database, a domain, and TLS. The challenge keeps it simple: one droplet, one image, one open port. Get the keystrokes right; the mini-project later this week builds on top of this shape.

**Estimated time.** 3-4 hours.

**Cost.** About $0.50 (one s-1vcpu-1gb droplet for two to three hours of active work).

---

## What you will build

A single Terraform configuration in your own GitHub repo that:

1. Reads variables for the image reference (`ghcr.io/<you>/<repo>:<tag>`), the droplet region, the droplet size, and your SSH public key.
2. Provisions one droplet with cloud-init `user_data` that installs Docker, pulls the image from GHCR, and runs it as a systemd service.
3. Configures a firewall: SSH (22), HTTP (80) inbound; all outbound.
4. Outputs the droplet's IPv4 and a `curl` command that confirms the image is serving.
5. Stores its state in the Spaces bucket you bootstrapped in Exercise 3.

If your Week 4 image is private (most are by default), the challenge has a bonus: configure cloud-init to log in to GHCR with a fine-grained PAT before pulling. See "Bonus: private images" below.

---

## Hint sheet (use sparingly)

You should be able to do this with what you already know. Use these hints only if you are stuck for more than fifteen minutes on a step.

### Hint 1 — the file layout

```
challenge-01/
├── versions.tf        # terraform { required_providers, backend "s3" {} }
├── providers.tf       # provider "digitalocean" { token = var.do_token }
├── variables.tf       # 6-8 variables
├── main.tf            # ssh_key + droplet + firewall
├── outputs.tf         # droplet_ipv4, curl_command, ssh_command
├── cloud-init.yaml.tftpl  # template for user_data
├── backend.hcl        # same as Ex 3, different key
└── README.md          # the design rationale
```

### Hint 2 — the `user_data` shape

```yaml
#cloud-config
package_update: true
packages:
  - docker.io

write_files:
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
      ExecStart=/usr/bin/docker run --rm --name app -p 80:8000 ${image_ref}

      [Install]
      WantedBy=multi-user.target

runcmd:
  - systemctl daemon-reload
  - systemctl enable app.service
  - systemctl start app.service
```

Replace `8000` with whatever port your Week 4 image listens on (most likely 8000 for Flask, 3000 for Node, 8080 for Spring).

### Hint 3 — pulling the template

```hcl
locals {
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    image_ref = var.image_ref
  })
}

resource "digitalocean_droplet" "app" {
  # ...
  user_data = local.user_data
  # ...
}
```

### Hint 4 — the firewall

```hcl
resource "digitalocean_firewall" "app" {
  name        = "challenge-01-fw"
  droplet_ids = [digitalocean_droplet.app.id]

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

---

## Bonus: private GHCR images

If your image is private, cloud-init must log in to GHCR before `docker pull`. The shape:

```yaml
runcmd:
  - echo "${ghcr_pat}" | docker login ghcr.io -u ${ghcr_user} --password-stdin
  - systemctl daemon-reload
  - systemctl enable app.service
  - systemctl start app.service
```

The PAT must have `read:packages` scope. Treat it as a secret: pass it via a `sensitive = true` variable. Be aware that **the PAT will end up in the droplet's user-data metadata**, which is readable from inside the droplet. For real production, you would use a secret-management agent; for this challenge, the user-data approach is acceptable as long as you destroy promptly.

---

## Acceptance

- [ ] `curl http://<droplet-ipv4>` returns a response from your Week 4 image (any status code that is not connection-refused; 200 is the goal but a 404 from a route you did not define still means the image is serving).
- [ ] `ssh root@<droplet-ipv4> 'systemctl status app'` shows `active (running)`.
- [ ] `ssh root@<droplet-ipv4> 'docker ps'` shows your image with a recent uptime.
- [ ] State is in the Spaces bucket from Exercise 3 (`doctl spaces object list ... | grep challenge-01`).
- [ ] `terraform plan` returns "no changes" on a re-run with no edits.
- [ ] `terraform destroy` brings the bill back to zero; `doctl compute droplet list` is empty.
- [ ] The repo's last commit is on `main` and pushed.

---

## Write-up (the heart of the challenge)

A `README.md` at the root, ~300 words, covering:

1. **The design choices.** Which size droplet, which region, which image, which open ports. Why each.
2. **The cloud-init choice.** Why `user_data` rather than (e.g.) Ansible-after-boot or a pre-baked AMI. What you would do differently if this were a fleet of 100 droplets, not one.
3. **The TLS gap.** Port 80 is plaintext. List the three options for adding TLS (the mini-project will pick one): Caddy with automatic Let's Encrypt; nginx with certbot; a DigitalOcean Load Balancer with managed TLS. One sentence on the tradeoffs of each.
4. **The cost reckoning.** How much this droplet would cost per month if you forgot to destroy it. How much the same shape would cost on AWS (`t4g.nano` ~ $3/month), GCP (`e2-micro` ~ $7/month free tier through 2026), and DigitalOcean (`s-1vcpu-1gb` $6/month). One sentence on what you would actually pick for a personal project.
5. **The post-mortem of one thing that went wrong.** Use the C15 post-mortem template (impact, timeline, root cause, resolution, action items). Most likely it will be the cloud-init template not rendering correctly, or the image not pulling because the PAT was wrong, or the firewall blocking the port the image listens on. Pick one; write it up properly.

> **Status panel — challenge target**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  CHALLENGE 01 — runtime check                       │
> │                                                     │
> │  Droplet:        s-1vcpu-1gb / nyc3                 │
> │  IPv4:           <set after apply>                  │
> │  Image:          ghcr.io/<you>/<repo>:<tag>         │
> │  HTTP:           80    expected: 200 or 404         │
> │  SSH:            22    expected: prompt             │
> │  systemctl:      app.service active (running)       │
> │  docker ps:      one container, recent uptime       │
> │  Plan re-run:    no changes                          │
> └─────────────────────────────────────────────────────┘
> ```

---

## Tear down

```bash
terraform destroy -auto-approve
doctl compute droplet list
# (empty)
```

The Spaces bucket stays; the mini-project will use it.

```bash
git add . README.md
git commit -m "feat: challenge 01 — week-4 image on a real VPS, in terraform"
git push -u origin main
```
