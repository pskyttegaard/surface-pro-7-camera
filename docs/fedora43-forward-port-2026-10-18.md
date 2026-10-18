# Fedora 43 capture-host forward port — 2026-10-18

Status: **deployed and accepted on Surface Pro 7 hardware**, including reboot
persistence, as reported by Peter on 2026-10-18. The preserved automated
artifact has one timeout; see the evidence qualification below.
Branch: `codex/camera-fedora43-forward-port`, based on PR #1 head
`2eb4916295a9090694fca7cdb84d66c4db2b9e06`. The published PR and its
branch remain unchanged. The working installation now uses this forward port.
Kernel 6.19.8-3.surface.fc43.x86_64, IPU4,
firmware, GStreamer packages and RTSP/unattended setup are outside this change.

## Source and configuration changes

WirePlumber 0.5.14's packaged `monitors/libcamera/create-node.lua` creates a
`LocalNode("spa-node-factory", ...)`: WirePlumber now hosts capture. Its existing
`UnsetEnvironment=LD_LIBRARY_PATH` would discard the custom library selection.
The accepted installation supplies **both** PipeWire and WirePlumber with one
environment file through matching late service drop-ins. `UnsetEnvironment=` resets the
legacy final environment removal before `EnvironmentFile=` is applied. For future
deployments, inspect expanded units for any additional unset variables that must
be retained; the reviewed baseline removes only LD_LIBRARY_PATH.

The common environment selects one camera-only private prefix for libcamera,
libcamera-base, IPA module, IPA configuration, IPA proxy, and custom SPA.
It retains CPU SoftISP, VFLIP=1 and OV8865 mode 15. SPA fallback is Fedora's
`/usr/lib64/spa-0.2`, excluding the old mixed `/usr/local` build. The prefix must
contain no libpipewire/libwireplumber libraries: core/audio libraries remain
Fedora RPM libraries. The existing seat-aware policy and Lua are staged unchanged.
No sensor, orientation, exposure, timestamp, queueing or suspension-guard patch
is altered. No source patch is necessary for this first target.

Implementation files:

- `config/camera-userspace-sources.json`: exact pinned source revisions.
- `scripts/build-camera-userspace`: apply existing patches and build/install only
  within an isolated /tmp workspace. Uses fresh source archives; use a new workspace
  when source pins or patches change (existing build directories support resume).
- `scripts/stage-camera-userspace`: generate reviewable environment, two service
  drop-ins, unchanged seat policy and Lua, plus a hash manifest. No activation.
- `config/camera-userspace/`: environment/drop-in templates and exact package plan.
- `tools/inspect-camera-userspace.py`: linkage, symbol-resolution and version checks
  without opening cameras or starting media daemons.

Pinned sources: libcamera 0.7.2 at
`191e202178f02430b5942397c70d215cdd2056fa`, PipeWire 1.4.11 at
`255541eac34370e312f0c5c8c18e46dc1911352f`, WirePlumber 0.5.14 at
`07e730b279ac7a520699ae9f6b0797848a731b30`.

## Historical build and inspection results

Reproduce from this worktree with the usual build dependencies already present:

```sh
scripts/build-camera-userspace --workspace /tmp/sp7-f43-candidate \
  --source-cache /tmp/sp7-compat-2026-10-18 --jobs 2
tools/inspect-camera-userspace.py --workspace /tmp/sp7-f43-candidate
scripts/stage-camera-userspace \
  --camera-prefix /tmp/sp7-f43-candidate/prefix/camera \
  --runtime-prefix /home/peter/.local/lib/sp7-camera-userspace/f43-20261018 \
  --output /tmp/sp7-f43-deployment-stage-final
```

Omit `--source-cache` to fetch the pinned sources. Staging output must not already
exist. Builds also download the hash-pinned upstream Lua wrap into /tmp.

- All existing libcamera/PipeWire patches applied with fuzz disabled; all three
  source builds and prefix-restricted installs completed.
- Custom SPA, IPA and proxy dependencies resolve to the same camera prefix;
  SPA and IPA load with immediate symbol resolution.
- Inspection binaries report PipeWire 1.4.11 and WirePlumber 0.5.14.
- Generated systemd units pass `systemd-analyze --user verify` with synthetic base
  units. Environment and staged file hashes pass inspection.
- All 13 target RPMs and 13 exact rollback RPMs were downloaded and their Fedora
  signatures verified. Both repository and offline local-RPM dry-runs resolve
  exactly 13 upgrades, without a transaction.
- Extracted **actual Fedora RPM** binaries report the correct compiled/linked
  versions. Their dependencies resolve, and Fedora's WP Lua module, the custom
  SPA and IPA load successfully. Packaged WP has the expected LocalNode change
  and all seat-policy feature dependencies.

The source-built PipeWire is a minimal inspection build (D-Bus disabled because
its development dependency is absent); source-built WP uses bundled Lua 5.5.
They are **not deployment payloads**. Deployment uses Fedora's full RPM binaries
and system Lua 5.4; the separate exact-RPM checks cover their linkage. These
pre-deployment checks did not prove runtime capture, Lua policy execution, or
audio behavior. No camera/audio device was opened during those isolated checks;
subsequent hardware acceptance is recorded below. The build-results JSON remains
an unchanged-in-substance historical record, with its scope explicitly labeled.

## Persistent deployment and rollback material

The complete reviewed deployment is preserved at
`/home/peter/sp7-forward-port/f43-20261018`, outside volatile `/tmp`:

- `camera-payload.tar`, `stage/`, `SHA256SUMS` and manifests;
- `rpms/target/` (13 signed target RPMs) and `rpms/rollback/` (13 exact old RPMs);
- `source/`, `forward-port.git.bundle` (original candidate commit `6b2a204`),
  `branch-metadata.json`, and `evidence/` with original build/solver records;
- `operator-state/` with pre-deployment file backups and service state;
- `DEPLOY.md`, `ROLLBACK.md`, `verify-bundle.py` and `operator-state.py`;
- `validation-profile-check/` with local capture results and images.

Do not commit RPM binaries, camera images, raw debug logs, extracted build trees,
user backups or the deployment archive to Git. The branch retains source/config,
concise acceptance evidence and the original hash/signature inventory. Temporary
paths in the historical build record identify original locations, not current
artifact dependencies. The original preserved bundle is immutable; it does not
include this later documentation commit.

Use the preserved **ordered operator runbooks** for any deliberate redeployment
or rollback. `verify-bundle.py --baseline` checks the old rollback package set;
it is a pre-deployment/after-rollback check and is expected to fail on the accepted
target installation. `verify-bundle.py` without `--baseline` checks the immutable
bundle and signed RPM identities without requiring old installed packages.
The reference plans below remain intact. No backup, RPM, rollback instruction,
or active configuration was removed or changed by this documentation cleanup.

## Exact Fedora package transaction

| Package | Exact rollback baseline | Accepted installed target |
| --- | --- | --- |
| alsa-lib | 1.2.14-4.fc43.x86_64 | 1.2.16.1-1.fc43.x86_64 |
| pipewire | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-alsa | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-config-raop | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-gstreamer | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-jack-audio-connection-kit | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-jack-audio-connection-kit-libs | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-libs | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-plugin-libcamera | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-pulseaudio | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| pipewire-utils | 1.4.8-2.fc43.x86_64 | 1.4.11-1.fc43.x86_64 |
| wireplumber | 0.5.11-1.fc43.x86_64 | 0.5.14-1.fc43.x86_64 |
| wireplumber-libs | 0.5.11-1.fc43.x86_64 | 0.5.14-1.fc43.x86_64 |

`alsa-lib` is required because the new `pipewire-alsa` requires
`libasound.so.2(ALSA_1.2.15)(64bit)`. This was included in the accepted local
13-package transaction and remains part of exact rollback. No stock libcamera
or Lua update is required. No package was changed during isolated preparation; hardware deployment subsequently applied
the exact 13 local target RPMs. The preceding security transaction left camera
user space unchanged; kernel/GStreamer exclusions were retained.

## Reference deployment plan — completed; approval required to repeat

1. Preserve signed target and rollback RPMs, manifests, this branch and build
   payload outside volatile /tmp. Recheck installed versions, signatures and
   hashes. Record the media units' enabled/active states and expanded unit
   configuration. Back up every destination below, recording files absent before
   deployment. Record the existing PW/WP drop-ins and working library hashes.
2. Close camera/audio clients. Stop any active camera controller, WirePlumber,
   PipeWire/Pulse services and their activation sockets, recording prior states,
   to avoid mixed-version capture during the transaction. Do not touch RTSP.
3. Copy **only** `prefix/camera` into the new private prefix
   `/home/peter/.local/lib/sp7-camera-userspace/f43-20261018`, preserving layout,
   symlinks and modes. Never deploy `prefix/userspace`. Retain the old custom
   `/usr/local` and user-local libraries untouched.
4. Back up then copy the five staged config/data files: config contents to
   `~/.config`, Lua data to `~/.local/share`. Both services receive the same
   environment. Review expanded drop-in ordering and the unset list. No ExecStart
   override, legacy full installer, package installation script or kernel setup
   is used for this deployment.
5. Upgrade using **only the 13 reviewed local target RPMs**, repositories disabled,
   weak dependencies disabled, and without `--allowerasing`. Preview again and
   reject any different transaction before approval/execution. Include ALSA;
   retain the exact 13 old RPMs for rollback.
6. Reload user systemd configuration and restore normal media sockets/services.
   Inspect both processes' environments/maps and IPA logs: libcamera/base, IPA,
   SPA, tuning and proxy must come from the new camera prefix; core PW/WP
   libraries must come from Fedora RPMs. Run the tests below. Do not recover by
   restarting media services during the cold-boot acceptance test.
7. Reboot on the same kernel, sign in locally, and repeat all five profiles before
   any media-service restart. Keep RTSP disabled and stopped throughout.

## Explicit rollback

1. Close clients and stop user media services/sockets to prevent mixed versions.
2. Restore the backed-up five destinations; remove only candidate files that did
   not exist beforehand. This removes the new late drop-ins/common environment
   while restoring unchanged legacy selection and seat policy. Preserve all old
   custom camera libraries throughout deployment.
3. With repositories disabled, downgrade using the **13 exact signed rollback
   RPMs**, including alsa-lib, after confirming the preview matches the recorded
   installed baseline. Do not use `--allowerasing` or a broad history undo.
4. Reload systemd and restore recorded socket/service states. Verify old library
   paths/hashes and all five profiles; reboot on the unchanged kernel if needed.
   Leave the unused candidate prefix inert until rollback is confirmed.

## Hardware acceptance — 2026-10-18

Peter reports acceptance of the deployed Fedora 43 stack on kernel
`6.19.8-3.surface.fc43.x86_64`, custom libcamera 0.7.2, patched SPA 1.4.11,
Fedora PipeWire 1.4.11-1.fc43 and WirePlumber 0.5.14-1.fc43. The table above lists
all 13 exact package versions, including alsa-lib 1.2.16.1-1.fc43.

The installed private camera prefix is
`/home/peter/.local/lib/sp7-camera-userspace/f43-20261018`. Both user services
receive `~/.config/sp7-camera/userspace.env` through
`99-zz-sp7-camera-userspace.conf`. Their running environments select:

```text
LD_LIBRARY_PATH=/home/peter/.local/lib/sp7-camera-userspace/f43-20261018/lib64
SPA_PLUGIN_DIR=/home/peter/.local/lib/sp7-camera-userspace/f43-20261018/lib64/spa-0.2:/usr/lib64/spa-0.2
```

The same environment selects the prefix's IPA module, configuration and proxy,
with CPU SoftISP, VFLIP=1 and OV8865 mode 15. WirePlumber 0.5.14 is the capture
host. Runtime maps confirm its libcamera.so.0.7.2, libcamera-base.so.0.7.2,
ipa_soft_simple.so and custom libspa-libcamera.so all load from that prefix.
PipeWire/WirePlumber core libraries load from Fedora `/usr/lib64`. Both services
receive the camera environment so discovery/capture cannot select mismatched
camera assets; this does not imply both processes actively host capture.

Reported acceptance:

1. Bundle preflight and the exact 13-package local transaction passed; both media
   services started with the shared environment and late drop-ins.
2. `wpctl status` showed exactly Surface Front Standard, Surface Front HQ,
   Surface Rear Standard, Surface Rear HQ and Surface Rear Fast as video sources.
   Raw IPU devices remained devices, not exposed video sources.
3. GNOME Camera passed before reboot: expected profiles, quick startup, correct
   orientation, acceptable colors and successful switching.
4. Peter reports an all-pass automated regression over 26 rounds, 20 paired frames
   per capture, zero timestamp regressions and zero invalid timestamps. The local
   evidence qualification below must accompany this report.
5. Reboot persistence passed: same Surface kernel, active PipeWire/WirePlumber,
   five restored logical profiles, private camera libraries and Fedora core
   libraries still correctly separated; GNOME Camera passed again.
6. RTSP remained intentionally **disabled and inactive** throughout. Streaming,
   unattended deployment, ACLs and udev are outside this branch's acceptance.

Read-only checks during this cleanup independently reconfirmed the kernel, all
13 target package versions, both running environments, WirePlumber's private
camera mappings, Fedora core mappings and disabled/inactive RTSP. No captures,
service restarts, configuration writes or package transactions were performed.

### Automated evidence qualification

The preserved `validation-profile-check/summary.json` currently reports
`complete: true`, `passed: false`: 338 captures (26 rounds of 13), with 337 passing
and one Front Standard RGBA timeout at zero-based case index 276. The passing
captures have 20 paired frames each; the timeout has one black paired frame.
All 338 captures report zero timestamp regressions and zero invalid timestamps.
This file therefore does **not** substantiate an all-pass run. Peter's hardware
acceptance is recorded as reported, separately from this inspected artifact;
a later all-pass result has been requested. No artifact has been rewritten or
silently excluded. The compact JSON acceptance record includes the summary hash.

### Remaining follow-up

- Reconcile the single-timeout artifact with the reported all-pass run; retain the
  final regression summary when available. No camera behavior is changed here.
- Audio playback/microphone testing was in the operator plan, but a separate audio
  acceptance result was not supplied in the camera acceptance report.
- The inspection source builds remain intentionally different from full Fedora
  builds (PipeWire D-Bus disabled; bundled Lua 5.5 versus Fedora Lua 5.4). Deployment
  uses the actual Fedora RPMs, whose hardware integration has now been accepted.
- Reproducible rebuilds must use fresh workspaces when pins/patches change; resume
  currently trusts existing source/build directories. The staging command remains
  preparation-only, and the legacy installer is not a substitute for this runbook.

PR #1 and its branch are unchanged. Camera patches, accepted runtime architecture,
rollback material and RTSP/unattended setup remain unchanged.
