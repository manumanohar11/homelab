# 📞 Jitsi Meet

[← Back to README](../README.md)

Deploy Jitsi Meet in this homelab with Pangolin handling only the public web entrypoint while audio and video stay direct-first and home-only.

---

## Table of Contents

- [Why Jitsi, Not Plain WebSockets](#why-jitsi-not-plain-websockets)
- [Traffic Model](#traffic-model)
- [What This Adds](#what-this-adds)
- [Environment Variables](#environment-variables)
- [DNS And Router Setup](#dns-and-router-setup)
- [Deploy The Stack](#deploy-the-stack)
- [Create The Moderator Account](#create-the-moderator-account)
- [Room Flow](#room-flow)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Why Jitsi, Not Plain WebSockets

Jitsi still uses WebSockets for signaling and control, but the actual call media is WebRTC. That matters because your real requirement is not “real-time messages.” It is direct mobile-friendly audio/video with NAT traversal, app joins, guest rooms, and TURN fallback when a direct peer path does not work.

This repo keeps Jitsi for that full calling workflow:

- `meet.${DOMAIN_NAME}` stays the friendly web and app entrypoint.
- Two-person calls still prefer direct peer-to-peer media.
- If direct media fails, the fallback relay stays on your home server, not the VPS.

---

## Traffic Model

- `https://meet.${DOMAIN_NAME}` stays on Pangolin as a normal HTTP resource with Pangolin SSO disabled only for that hostname.
- `rtc.${DOMAIN_NAME}` is a DNS-only Cloudflare record that points straight at your home WAN IP.
- `jitsi-jvb` publishes `10000/udp` from home for JVB fallback media.
- `coturn` publishes `3478/udp`, `3478/tcp`, and `20000-20100/udp` from home for TURN.
- `jitsi-ddns` keeps `rtc.${DOMAIN_NAME}` updated in Cloudflare when your ISP changes your home IP.

Do not create Pangolin raw resources, Gerbil mappings, or Traefik UDP/TCP entrypoints for Jitsi media. In this design the VPS is not part of the media path.

---

## What This Adds

- Compose module: `docker-compose.communication.yml`
- Profile: `jitsi`
- Web entrypoint: `https://meet.${DOMAIN_NAME}`
- Media hostname: `rtc.${DOMAIN_NAME}`
- Runtime data: `${DOCKER_BASE_DIR}/jitsi/...` and `${DOCKER_BASE_DIR}/coturn/...`
- Tracked runtime templates:
  - `config-templates/jitsi/web/custom-config.js`
  - `config-templates/jitsi/jvb/bootstrap.sh`
  - `config-templates/jitsi/ddns/update-cloudflare.py`
  - `config-templates/coturn/bootstrap.sh`
  - `config-templates/coturn/turnserver.conf`

The tracked web config keeps P2P enabled, leaves ICE/UDP enabled, preserves deep links for the Android app, targets `1080p`, and keeps lobby auto-knock enabled for guest joins.

---

## Environment Variables

Set these in `.env` before first start:

```bash
JITSI_IMAGE_VERSION=stable-10655
JITSI_SUBDOMAIN=meet
JITSI_PUBLIC_URL=https://${JITSI_SUBDOMAIN}.${DOMAIN_NAME}
JITSI_MEDIA_SUBDOMAIN=rtc
JITSI_MEDIA_PUBLIC_HOSTNAME=${JITSI_MEDIA_SUBDOMAIN}.${DOMAIN_NAME}
JITSI_XMPP_DOMAIN=meet.jitsi
JITSI_XMPP_AUTH_DOMAIN=auth.${JITSI_XMPP_DOMAIN}
JITSI_XMPP_GUEST_DOMAIN=guest.${JITSI_XMPP_DOMAIN}
JITSI_XMPP_MUC_DOMAIN=muc.${JITSI_XMPP_DOMAIN}
JITSI_XMPP_INTERNAL_MUC_DOMAIN=internal-muc.${JITSI_XMPP_DOMAIN}
JITSI_AUTH_USER=owner
JITSI_AUTH_PASSWORD=<generated>
JITSI_JICOFO_COMPONENT_SECRET=<generated>
JITSI_JICOFO_AUTH_PASSWORD=<generated>
JITSI_JVB_AUTH_PASSWORD=<generated>
JITSI_JVB_UDP_PORT=10000
JITSI_TURN_HOST=${JITSI_MEDIA_PUBLIC_HOSTNAME}
JITSI_TURN_PORT=3478
JITSI_TURN_TRANSPORT=udp,tcp
JITSI_TURN_MIN_PORT=20000
JITSI_TURN_MAX_PORT=20100
JITSI_TURN_CREDENTIALS=<generated>
JITSI_CLOUDFLARE_API_TOKEN=<your token>
```

`make init-env` still generates the Jitsi secrets in `.env` if they are missing. It does not generate `JITSI_CLOUDFLARE_API_TOKEN`, because that token has to come from your Cloudflare account and needs DNS edit access for your zone.

---

## DNS And Router Setup

1. Keep the Pangolin HTTP resource for `meet.${DOMAIN_NAME}`:
   - `pangolin.public-resources.meet.protocol=http`
   - `pangolin.public-resources.meet.full-domain=${JITSI_SUBDOMAIN}.${DOMAIN_NAME}`
   - `pangolin.public-resources.meet.auth.sso-enabled=false`
   - Target: `jitsi-web:80`
2. Create `rtc.${DOMAIN_NAME}` in Cloudflare as a DNS-only `A` record, not proxied.
3. Point that `rtc` record at your current home public IPv4 address once. After that, `jitsi-ddns` keeps it updated.
4. Forward these home router ports to the Docker host:
   - `10000/udp -> jitsi-jvb`
   - `3478/udp -> coturn`
   - `3478/tcp -> coturn`
   - `20000-20100/udp -> coturn`
5. Do not expose Jitsi media on the VPS through Pangolin raw resources, Gerbil, or Traefik TCP/UDP entrypoints.

If `rtc.${DOMAIN_NAME}` is proxied through Cloudflare, media and TURN will fail because the clients need your real home IP for those non-HTTP ports.

---

## Deploy The Stack

```bash
docker compose config
docker compose --profile jitsi up -d
docker compose ps jitsi-web jitsi-prosody jitsi-jicofo jitsi-ddns jitsi-jvb coturn
```

Expected containers:

- `jitsi-web`
- `jitsi-prosody`
- `jitsi-jicofo`
- `jitsi-ddns`
- `jitsi-jvb`
- `coturn`

`jitsi-jvb` resolves `rtc.${DOMAIN_NAME}` when it starts and exports that IPv4 address into `JVB_ADVERTISE_IPS` before handing control back to the stock Jitsi startup flow. `coturn` resolves the same hostname and renders `external-ip` into the live `turnserver.conf` before launching `turnserver`.

---

## Create The Moderator Account

After the containers are healthy, create exactly one internal moderator account:

```bash
docker compose exec jitsi-prosody \
  prosodyctl --config /config/prosody.cfg.lua register \
  "${JITSI_AUTH_USER}" "${JITSI_XMPP_DOMAIN}" "${JITSI_AUTH_PASSWORD}"
```

Use that account to sign in before creating rooms. Guests do not need accounts. With `ENABLE_AUTH=1`, `ENABLE_GUESTS=1`, and `AUTH_TYPE=internal`, a random unauthenticated visitor cannot create the room first.

---

## Room Flow

1. Open `https://meet.${DOMAIN_NAME}` and sign in as the moderator account.
2. Create the room first as the moderator.
3. Open the room security menu and enable the lobby.
4. Set a room passcode.
5. Send the room link to your girlfriend.
6. If the Jitsi Android app is installed, the link should deep-link there. Otherwise the browser join flow still works.
7. On a normal two-person network path, Jitsi should prefer direct P2P media.
8. If the direct path fails, the fallback stays on your home `jitsi-jvb` or home `coturn`, not on Pangolin or the VPS.

Jitsi does not force a room passcode the instant the room is created. In this setup the intended workflow is “moderator creates the room, then immediately enables lobby and passcode, then shares the link.”

---

## Verification

Basic config and health:

```bash
docker compose config
docker inspect --format='{{.State.Health.Status}}' jitsi-web
docker inspect --format='{{.State.Health.Status}}' jitsi-prosody
docker inspect --format='{{.State.Health.Status}}' jitsi-jicofo
docker inspect --format='{{.State.Health.Status}}' jitsi-ddns
docker inspect --format='{{.State.Health.Status}}' jitsi-jvb
docker inspect --format='{{.State.Health.Status}}' coturn
```

Functional checks:

- Visit `https://meet.${DOMAIN_NAME}` and confirm there is no Pangolin SSO prompt.
- Open the same room in the Jitsi Android app and confirm it reaches your self-hosted server.
- Join first as the moderator, then as a guest, and confirm the guest cannot create the room alone.
- Run a two-person Wi-Fi test and inspect Jitsi connection details for direct P2P media.
- Run a restrictive NAT or cellular test and confirm media still works without any VPS relay.
- Temporarily block `10000/udp` at home and confirm JVB fallback breaks in a predictable way.
- Temporarily block `3478` plus `20000-20100/udp` at home and confirm TURN fallback breaks in a predictable way.

In the normal two-person case, connection details should show P2P. When P2P is unavailable, you should still see calls succeed through your home JVB or TURN services while VPS bandwidth stays limited to web and signaling traffic.

---

## Troubleshooting

### Site Opens But There Is No Audio Or Video

- Confirm `rtc.${DOMAIN_NAME}` is DNS-only in Cloudflare and resolves to your current home WAN IPv4.
- Confirm your router forwards `10000/udp`, `3478/udp`, `3478/tcp`, and `20000-20100/udp` to the Docker host.
- Check `docker compose logs jitsi-ddns jitsi-jvb coturn` for DNS, ICE, or TURN allocation failures.
- Inspect the resolved JVB public address:

```bash
docker compose exec jitsi-jvb \
  grep -n "public-address" /config/jvb.conf
```

- Inspect the rendered coturn runtime config:

```bash
docker compose exec coturn \
  grep -nE "external-ip|realm|listening-port|min-port|max-port" /var/lib/coturn/turnserver.conf
```

The most common failure mode is a stale or proxied `rtc.${DOMAIN_NAME}` record, followed by missing home router port forwards.

### My ISP Changed My IP

- Confirm `rtc.${DOMAIN_NAME}` has moved to the new home public IP.
- Check `docker compose logs jitsi-ddns` for the last Cloudflare update result.
- Restart the media services after the DNS record is correct:

```bash
docker compose restart jitsi-jvb coturn
```

`jitsi-jvb` and `coturn` resolve the current `rtc.${DOMAIN_NAME}` address only when they start, so a restart is the expected recovery step after a WAN IP change.

### Android App Or Browser Hits Pangolin Login

- Check the `jitsi-web` labels and confirm `pangolin.public-resources.meet.auth.sso-enabled=false`.
- Make sure only the `meet` HTTP resource is unauthenticated in Pangolin.
- Confirm the public `meet` hostname still points to the Pangolin edge that owns the Jitsi HTTP resource.

### Guest Can Create Rooms Alone

- Confirm the moderator account exists in Prosody.
- Make sure the moderator joins and creates the room before sharing the link.
- Check `docker compose logs jitsi-prosody` and `docker compose logs jitsi-jicofo` for auth or moderator-check failures.

### DDNS Does Not Update `rtc.${DOMAIN_NAME}`

- Confirm `JITSI_CLOUDFLARE_API_TOKEN` is set and has Zone DNS edit permission for `${DOMAIN_NAME}`.
- Make sure the zone is actually hosted in Cloudflare.
- Check `docker compose logs jitsi-ddns` for API permission errors or public-IP detection failures.
- If you manually correct the DNS record, restart `jitsi-jvb` and `coturn` afterward so they advertise the new IP immediately.

---

## Related Docs

- [Services Catalog](services.md)
- [Configuration Guide](configuration.md)
- [Networking Guide](networking.md)
