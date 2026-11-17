# Deployment candidate — not yet publicly deployed

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.
This is a single-operator prototype behind authentication, not a multi-tenant production service.
No permanent provider, spending budget or domain has been selected. Do not expose an unauthenticated Gradio server.

1. Provision a Linux NVIDIA GPU host only after choosing a provider and budget. Transfer code,
   separately licensed weights, MuseTalk, and the isolated Python environments. Recreate environments
   from their lockfiles; copying virtualenv directories across hosts is not reliable.
2. Rewrite absolute paths in configs for that host. Test the recorded pipeline on the target GPU.
3. Install the project with its `server` extra in `/opt/multilingua/.venv-service`.
4. Create an unprivileged `multilingua` account and a root-readable `/etc/multilingua.env`:
   `MULTILINGUA_USER`, `MULTILINGUA_PASSWORD` (unique random value, at least 16 characters),
   `MULTILINGUA_CONFIG`, `MULTILINGUA_RUNS`. Give the service account only necessary model and
   output-directory access. Never commit passwords or Hugging Face tokens.
5. Adapt/install the systemd unit and Caddyfile. Set `MULTILINGUA_DOMAIN` in Caddy's environment,
   point DNS at the host, permit HTTPS ports 80/443, and leave port 7861 private.
6. Before release, verify certificate renewal, authentication, 64 MiB upload enforcement, a real
   GPU job, full-queue errors, restart recovery, disk quotas, retention, and restore procedures.

The API accepts complete MP4/WebM clips up to 30 seconds, one worker and one waiting job.
Webcam capture uploads independently finalized six-second recordings; it is NOT continuous
WebRTC transport or validated low-latency dubbing. Queue overload is surfaced, not hidden.
Stopping the camera stops capture; already submitted jobs continue. Failed translations may require
review in the recorded-video UI. No tenant isolation, retention scheduler, external monitoring,
TURN configuration, or GPU scaling has been validated. Keep public release pending these checks.

Local launch (after setting credentials):
`python -m uvicorn multilingua.server:create_app --factory --host 127.0.0.1 --port 7861 --workers 1`

Apply `patches/musetalk-frame-rounding.patch` from the MuseTalk repository root after checkout.
It corrects float rounding at exact frame boundaries; the adapter rejects any frame-count mismatch.
Store this local patch alongside the pinned upstream revision when reproducing a deployment.
The test server may use leading/following pauses to fit translated speech, so its speech start time
can shift within an available pause; original and effective timestamps are both saved.

## Temporary local-GPU demo

For an explicitly requested temporary English → Hindi demo, run from the repository:

```bash
python scripts/serve_demo.py
```

Use an environment with the UI dependencies installed and a working `configs/local.json`.
The launcher binds to localhost port 7860, requires login, and requests a Gradio share
link. Stop any existing studio using that port first. Credentials are generated once in
`.runtime/demo-login.json` (owner-only permissions); read them locally and share them
only with intended demo users. Earlier studio recordings are excluded by using
`runs/public-demo` as the demo output directory. This remains a single-operator demo;
anyone given its login can access that demo's results.

A public URL is usable only after the tunnel connects and authentication is verified
through that URL. A local startup message alone does not prove public hosting.
Keep the computer awake and connected; stop the launcher with Ctrl+C to stop the demo.
The link is temporary and depends on the tunnel provider and network connectivity.
Cloudflare Quick Tunnels do not support Gradio's SSE queue; use the authenticated,
polling-based capture service for that transport instead, with a dedicated run folder.
Do not run GPU jobs in both interfaces at the same time.

If Gradio sharing times out, an explicitly approved localhost.run tunnel can forward the
same authenticated studio. Start `python scripts/serve_demo.py --no-share`, then run:

```bash
ssh -o ServerAliveInterval=30 -R 80:127.0.0.1:7860 nokey@localhost.run
```

Use the HTTPS URL printed by SSH and keep both processes running. localhost.run terminates
HTTPS, so it can access transmitted demo credentials and media. Use only a dedicated demo
password and share permitted media. Verify anonymous `/config` access returns 401, then
verify login through the public URL. Stop SSH with Ctrl+C to remove public access.
