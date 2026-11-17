# Deployment candidate — not yet publicly deployed

Project scope: **English → Hindi dubbing only**. English input; Hindi translation, speech and subtitles.
This is a single-operator prototype behind authentication, not a multi-tenant production service.
No provider, spending budget or domain has been selected. Do not expose Gradio directly.

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
