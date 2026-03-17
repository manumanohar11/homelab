# Advanced Jitsi

[Back to README](../../README.md)

Jitsi lives in the `access` bundle and stays behind the `jitsi` profile.

## Start It

```bash
make init BUNDLES="access"
make up BUNDLES="access" PROFILES="jitsi"
```

Required bundle settings live in `env/bundles/access.env.example`.

Important pieces:

- `newt` is part of the access bundle.
- `jitsi-web`, `jitsi-prosody`, `jitsi-jicofo`, `jitsi-jvb`, `coturn`, and `jitsi-ddns` stay on the `jitsi` profile.
- `JITSI_CLOUDFLARE_API_TOKEN` is never generated automatically.
- `rtc.${DOMAIN_NAME}` should stay DNS-only in Cloudflare when you use the DDNS helper.
