# Snartrevolutions beheer — v0.1.0 (prototype)

An extensible Home Assistant custom integration, starting with temporary support administrator access.

**Security / limitations:** This is an untested prototype, not a security-audited release. Only listed user IDs may call the services. Service calls from automations with no user context are deliberately denied. Do not share dashboard access with untrusted users. The support user must be an existing non-owner administrator. The integration uses Home Assistant's internal auth API; compatibility may change. Deactivation does not promise immediate termination of already-established sessions. If a support user has an active long-lived token or refresh token, evaluate token revocation separately. Home Assistant must be running to enforce the timer; on restart the saved deadline is checked. An unexpected process failure may delay deactivation until restart. A backup administrator should remain available.

## Install

1. HACS > three dots > Custom repositories > URL `https://github.com/Smart-Revolutions/smartrevolutions-ha-app` > Integration. Alternatively copy `custom_components/snartrevolutions_beheer` into the Home Assistant config directory.
2. Find Home Assistant user IDs as an administrator (Settings > People > Users or via administrator WebSocket `config/auth/list`). Do not confuse IDs with usernames.
3. Add to `configuration.yaml`:

```yaml
snartrevolutions_beheer:
  support_user_id: "SUPPORT_USER_UUID"
  allowed_user_ids:
    - "ORDINARY_USER_UUID"
  max_minutes: 1440
```

4. Restart Home Assistant. Under Developer tools > Actions check `snartrevolutions_beheer.activate` and `snartrevolutions_beheer.revoke`.
5. Add `dashboard-example.yaml` as a manual card, and create the `input_number.sr_support_minutes` helper (range 1–1440, step 1).
6. For the custom duration button, create the following script in `scripts.yaml` (or via the UI), then reload scripts:

```yaml
sr_activate_custom:
  alias: SR Activate Custom
  sequence:
    - action: snartrevolutions_beheer.activate
      data:
        minutes: "{{ states('input_number.sr_support_minutes') | int(30) }}"
```

**Note:** Script actions may run with a different service context depending on Home Assistant version and execution path; because the integration deliberately denies calls without an allowlisted user context, the custom script may be rejected. For production, use a dedicated authenticated WebSocket command that accepts the chosen duration and verifies the invoking user; do not weaken the allowlist to make scripts work.

## Planned improvements
- Native dashboard card with presets, custom duration, countdown and confirmation.
- Config flow and options flow (no YAML needed).
- Permissioned, authenticated WebSocket command for custom duration.
- Clear state entities and notifications.
- Better resilience for timer expiry during downtime and session/token revocation policy.
- Modular architecture for future Smart Revolutions management features.
