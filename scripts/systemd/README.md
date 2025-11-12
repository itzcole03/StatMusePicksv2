# systemd service + timer for StatMusePicksV2 daily ingestion

These are example `systemd` unit and timer files that run the repository's
daily ingestion script `scripts/run_daily_sync.sh` once per day at 06:00.

Important: edit `run_daily_sync.service` before enabling it and use an EnvironmentFile for secrets and paths:

- Copy `scripts/systemd/env.example` to `/etc/statmuse/env` and update values (especially `REPO_ROOT`, `SERVICE_USER`, and `INGEST_ALERT_HMAC_SECRET`).
- Secure the file:

```bash
sudo mkdir -p /etc/statmuse
sudo cp scripts/systemd/env.example /etc/statmuse/env
sudo chown root:root /etc/statmuse/env
sudo chmod 600 /etc/statmuse/env
```

- Edit `run_daily_sync.service` and set `User`/`Group` to the non-root service account (e.g. `statmuse`). The unit reads `/etc/statmuse/env` so avoid committing secrets to Git.

Environment file best-practices:

- Keep secrets out of the repository: use `/etc/statmuse/env` or a secure secrets manager.
- Use file permissions `600` and a non-root service user.
- Rotate `INGEST_ALERT_HMAC_SECRET` periodically and update receivers accordingly.
- On systems using `systemd`, you can also use `systemd-escape` and `systemd-run` for temporary runs in CI.

Example installation (on a machine with `systemd`):

```bash
# copy units to systemd directory (requires sudo)
sudo cp scripts/systemd/run_daily_sync.service /etc/systemd/system/run_daily_sync.service
sudo cp scripts/systemd/run_daily_sync.timer /etc/systemd/system/run_daily_sync.timer

# reload systemd unit files
sudo systemctl daemon-reload

# enable and start the timer (timer will trigger the service at 06:00 daily)
sudo systemctl enable --now run_daily_sync.timer

# check status
sudo systemctl status run_daily_sync.timer
sudo journalctl -u run_daily_sync.service -f
```

Notes:
- `Persistent=true` in the timer causes systemd to run the missed job once if the machine was powered off at the scheduled time.
- The `run_daily_sync.sh` runner tries to activate `.venv` if present; ensure your venv is created and dependencies installed.
- The unit uses `Restart=on-failure` and will retry after 30s on failure.

GitHub Actions note (CI): to run integration tests that depend on webhook behavior, use repository secrets for `INGEST_ALERT_HMAC_SECRET` and inject them at runtime in the workflow. For local dev, use the `env.example` as a template.
