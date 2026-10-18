# Session-gated Front Standard RTSP — Fedora 43

Implementation prepared on `codex/rtsp-fedora43-session`, based on frozen
`467d1b2`. **Not deployed or enabled.** Accepted camera source, private prefix,
seat policy, PipeWire/WirePlumber drop-ins and packages are unchanged.

## Runtime design

`sp7-front-rtsp.service` is a Peter user service wanted by
`graphical-session.target` and stopped with it through `PartOf=`. It has no
`default.target` activation and does not pull in or restart media services.
`Type=simple` describes the supervisor: an active unit can be waiting rather
than streaming. The journal distinguishes:

- `waiting for eligible local session`;
- `waiting for Front Standard source`;
- `starting Front Standard capture`, then `streaming` after the child's READY;
- `capture child failed/backoff`;
- `session/source lost, stopping capture`.

The supervisor checks every two seconds, with bounded query timeouts. Eligibility
requires an active graphical-session target plus a logind session belonging to
the current UID on seat0: active, non-remote, class user, type Wayland or X11.
An inherited SSH session ID or lingering user manager is not sufficient. The
session is rechecked immediately before starting capture. Session enumeration
and property query errors fail closed. A locked session may still own the active
seat; locking alone is not an additional stop condition.

Only after this gate succeeds does the supervisor check that PipeWire and
WirePlumber are already active and inspect their existing PipeWire registry with
`pw-dump --remote=pipewire-0`. It requires the exact node name
`sp7.front.standard` and media class `Video/Source`. It never uses a raw device,
libcamera directly, a default camera, or a node's transient numeric ID. Missing
services, missing source, malformed registry data and query timeouts all wait
without spawning capture or attempting media-service recovery.

While capturing, loss of either eligibility or source presence stops the child
and releases capture on the next completed check. Ending the graphical-session
target stops the whole service, including its child, even with lingering enabled.
The bounded command/DBus timeouts mean this is not an instantaneous event gate.

The unchanged existing RTSP server is launched as a child. A private Unix notify
socket receives its existing READY notification after two seconds of delivered
frames. Only then does the guard log `streaming`; readiness does not itself
prove nonblack frames. A 45-second guard deadline bounds startup. The server's
existing 35-second startup and five-second frame-stall checks remain intact.

The child alone receives `PIPEWIRE_NODE=sp7.front.standard`,
`PIPEWIRE_REMOTE=pipewire-0`, the current UID's runtime directory, and stream
properties `target.object=sp7.front.standard`, `node.dont-fallback=true`,
`node.dont-move=true`, `node.dont-reconnect=true`. This closes the race where a
named source disappears between inspection and connection: WirePlumber must
not substitute another source. These are client-process settings, not edits to
accepted camera policy or system PipeWire configuration.

Child failures retry after 5, 10, 20 and 40 seconds; after five failures retries
stop until a session/source transition or explicit manual service restart.
A healthy stream for at least 60 seconds from child startup resets the failure
budget. Missing session/source never consumes retries or restarts the unit.
Unexpected supervisor failures have a separate systemd limit: three starts per
300 seconds, with 15 seconds between restarts. A normal manual stop does not
restart the service. KillMode=control-group also cleans up the capture child.

Lingering, the historical nine-device ACLs, udev rule and permission helper are
left unchanged. This implementation does not require broader access or new
permission grants. Permission cleanup is a separate future task.

## Existing server and sharing limitation

The unchanged external server remains at
`/home/peter/surface-pro-7-camera/src/sp7-front-rtsp`; the sustained checker remains
at `/home/peter/surface-pro-7-camera/tools/check-rtsp-sustained.py`. Neither is in
frozen commit 467d1b2, so this four-file branch depends on these existing local
files. Do not move that checkout before arranging a separately reviewed install
of the existing server/checker. Their reviewed SHA256 hashes are:

```text
6bfc7bfa1a855e4d691bbef0f2da616863e59c1fe18c706e785ccec01fd7864b  src/sp7-front-rtsp
03380c5e9d0430f2a723b06dd29a166a9ce43d6048be443f6a8e70f3a2215c3b  tools/check-rtsp-sustained.py
```

The source pipeline remains RGBx 1292x972 at 30 fps, reduced to 15 fps, honoring
orientation metadata through videoflip, then shared H.264 constrained-baseline
at 2.5 Mbit/s over RTSP interleaved TCP. No audio or authentication is configured;
the server binds all IPv4 interfaces on port 8554. No firewall changes are part
of this implementation. The previous LAN URL was:

```text
rtsp://192.168.10.214:8554/front-standard
```

Use the Surface's current LAN address in Synology Surveillance Station. Capture
stays open even without RTSP viewers; reconnecting clients recreates encoding
without reopening the sensor. All five logical sources must remain enumerated,
but the shared IPU path does not support independent simultaneous profile use.
Stop RTSP before using another camera/profile in GNOME Camera, then start it
again when finished. Automatic desktop/RTSP arbitration is outside this change.
Before login and after logout or seat loss, streaming is intentionally unavailable.

## Non-hardware checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/test-rtsp-session-guard.py
```

Tests use fake sessions, media-unit states and registry data. One synthetic child
only sends READY over a temporary Unix socket; it does not load GStreamer or
connect to PipeWire/cameras. They cover eligibility, absent-source waiting,
readiness, session/source loss, bounded retries, child cleanup and no-fallback
properties. A separate systemd verification uses a staged executable path because
the real guard is intentionally not yet installed. No capture validation is
claimed by these tests. Preparation results: **23/23 tests passed**, staged
systemd unit verification passed, and a read-only check confirmed recognition of
the current local graphical session. RTSP stayed disabled/inactive with zero
restarts; no server or real capture child was launched.

## Proposed deployment — do not execute until approved

Run as Peter in the local graphical session. These commands affect only the
RTSP layer. They do not restart PipeWire/WirePlumber or change permissions.
The existing camera rollback bundle at
`/home/peter/sp7-forward-port/f43-20261018` must remain untouched.

First preserve this RTSP branch outside volatile /tmp (the destination must not
already exist), then use that persistent checkout:

```bash
set -euo pipefail
test ! -e /home/peter/sp7-rtsp-fedora43-session
if test -d /tmp/sp7-rtsp-fedora43-session; then
  git -C /home/peter/surface-pro-7-camera worktree move \
    /tmp/sp7-rtsp-fedora43-session /home/peter/sp7-rtsp-fedora43-session
else
  git -C /home/peter/surface-pro-7-camera worktree add --force \
    /home/peter/sp7-rtsp-fedora43-session codex/rtsp-fedora43-session
fi
cd /home/peter/sp7-rtsp-fedora43-session
PYTHONDONTWRITEBYTECODE=1 python3 tools/test-rtsp-session-guard.py
systemctl --user show sp7-front-rtsp.service -p ActiveState -p UnitFileState
# Require inactive + disabled before proceeding.
python3 - <<'PY'
import subprocess
s = subprocess.check_output(['systemctl', '--user', 'show', 'sp7-front-rtsp.service',
                             '-p', 'ActiveState', '-p', 'UnitFileState'], text=True)
assert 'ActiveState=inactive\n' in s and 'UnitFileState=disabled\n' in s, s
PY
(cd /home/peter/surface-pro-7-camera && sha256sum --check <<'HASHES'
6bfc7bfa1a855e4d691bbef0f2da616863e59c1fe18c706e785ccec01fd7864b  src/sp7-front-rtsp
03380c5e9d0430f2a723b06dd29a166a9ce43d6048be443f6a8e70f3a2215c3b  tools/check-rtsp-sustained.py
HASHES
)
```

Back up the RTSP unit and guard (including recording an absent old guard), then
install only them; this still does not enable/start capture:

```bash
set -euo pipefail
cd /home/peter/sp7-rtsp-fedora43-session
RTSP_BACKUP="$HOME/sp7-rtsp-backups/session-gated-first-deployment"
test ! -e "$RTSP_BACKUP"
mkdir -p "$RTSP_BACKUP" "$HOME/.local/libexec" "$HOME/.config/systemd/user"
cp -a "$HOME/.config/systemd/user/sp7-front-rtsp.service" "$RTSP_BACKUP/unit"
if test -e "$HOME/.local/libexec/sp7-rtsp-session" || test -L "$HOME/.local/libexec/sp7-rtsp-session"; then
  cp -a "$HOME/.local/libexec/sp7-rtsp-session" "$RTSP_BACKUP/guard"
else
  touch "$RTSP_BACKUP/guard-was-absent"
fi
install -m 0755 src/sp7-rtsp-session "$HOME/.local/libexec/sp7-rtsp-session"
install -m 0644 systemd/user/sp7-front-rtsp.service \
  "$HOME/.config/systemd/user/sp7-front-rtsp.service"
systemd-analyze --user verify "$HOME/.config/systemd/user/sp7-front-rtsp.service"
systemctl --user daemon-reload
systemctl --user cat sp7-front-rtsp.service
# Remains disabled/inactive until the separately approved activation below.
```

After review, enable/start only this service:

```bash
systemctl --user enable --now sp7-front-rtsp.service
journalctl --user -u sp7-front-rtsp.service -f
```

Require the state progression through waiting/starting to streaming, then run the
unchanged nonblack soak checker for at least ten minutes:

```bash
DISABLE_RTKIT=1 python3 /home/peter/surface-pro-7-camera/tools/check-rtsp-sustained.py \
  rtsp://127.0.0.1:8554/front-standard --duration 610 \
  --output "$HOME/sp7-rtsp-validation/session-gated-first-soak"
```

Next verify Synology TCP reconnects, seat switching/logout release, local login
recovery, and a clean boot without capture before login. Stop RTSP and verify all
five camera profiles and existing private/Fedora library separation. Do not
restart media services as a recovery step; retain evidence and disable RTSP if
these gates fail. Automatic lifecycle behavior remains hardware-unvalidated until
these tests run. No reboot is authorized by this document alone.

## Disable and RTSP-only rollback

Immediate independent stop/disable:

```bash
systemctl --user disable --now sp7-front-rtsp.service
```

Restore only the saved RTSP files, leaving the old service disabled/inactive:

```bash
set -euo pipefail
RTSP_BACKUP="$HOME/sp7-rtsp-backups/session-gated-first-deployment"
systemctl --user disable --now sp7-front-rtsp.service
cp -a --remove-destination "$RTSP_BACKUP/unit" \
  "$HOME/.config/systemd/user/sp7-front-rtsp.service"
if test -f "$RTSP_BACKUP/guard-was-absent"; then
  rm -- "$HOME/.local/libexec/sp7-rtsp-session"
else
  cp -a --remove-destination "$RTSP_BACKUP/guard" "$HOME/.local/libexec/sp7-rtsp-session"
fi
systemctl --user daemon-reload
systemctl --user show sp7-front-rtsp.service -p ActiveState -p UnitFileState
```

Do not re-enable the historical default.target service. Do not run the historical
ACL helper or alter lingering/udev as part of this rollback. The accepted camera
baseline, PR #1 and its full camera rollback material remain unchanged.
