# Automatically trust new SSH host keys

Commit: uncommitted (new module; no prior module commits)
Author: emadco88
Date: 2026-09-16 (UTC)
Original commit subject: not applicable; no commit created

## Current changes before commit:

- Match the deployment script's `StrictHostKeyChecking=accept-new` behavior in the shared SSH function used for launch and monitoring, keeping unattended authentication enabled.
- Allow the systemd service to write the existing `/home/abdeploy/.ssh/known_hosts` file while keeping the rest of the home read-only.
- Document automatic first-connection trust, rejection of changed host keys, file prerequisites and manual service rollout.
- No translatable UI strings added or changed; both existing Arabic catalogs remain unchanged by this fix.

## Validation

- Isolated loopback SSH tests passed under a transient systemd unit with the runner's filesystem restrictions: new keys persisted, repeat connections succeeded and changed keys were rejected without altering the stored key.
- Sandbox checks confirmed the known-hosts file was writable while the private key and SSH configuration remained read-only.
- Verified the shared SSH arguments retain batch authentication and use accept-new. Systemd unit validation and diff whitespace checks passed.
- Test keys and SSH daemon were temporary and cleaned up. No branch servers contacted, installed runner service modified/restarted, or Odoo databases upgraded.

Files changed:

- `ab_deploy/runner/service.py`
- `ab_deploy/runner/ab-deploy-runner.service`
- `ab_deploy/runner/README.md`
- `ab_deploy/changelog.d/2026-09-16-ssh-host-keys.md`
