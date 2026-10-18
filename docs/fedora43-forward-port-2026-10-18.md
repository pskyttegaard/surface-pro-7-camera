# Fedora 43 capture-host forward port — 2026-10-18

Status: built and inspected in isolation; **not deployed or hardware validated**.
Branch: `codex/camera-fedora43-forward-port`, based on PR #1 head
`2eb4916295a9090694fca7cdb84d66c4db2b9e06`. The published PR and working
installation remain unchanged. Kernel 6.19.8-3.surface.fc43.x86_64, IPU4,
firmware, GStreamer packages and RTSP/unattended setup are outside this change.

## Source and configuration changes

WirePlumber 0.5.14's packaged `monitors/libcamera/create-node.lua` creates a
`LocalNode("spa-node-factory", ...)`: WirePlumber now hosts capture. Its existing
`UnsetEnvironment=LD_LIBRARY_PATH` would discard the custom library selection.
The candidate supplies **both** PipeWire and WirePlumber with one environment
file through matching late service drop-ins. `UnsetEnvironment=` resets the
legacy final environment removal before `EnvironmentFile=` is applied. Before
deployment, inspect expanded units for any additional unset variables that must
be retained; the reviewed baseline removes only LD_LIBRARY_PATH.

The common environment selects one camera-only private prefix for libcamera,
libcamera-base, IPA module, IPA configuration, IPA proxy, and custom SPA.
It retains CPU SoftISP, VFLIP=1 and OV8865 mode 15. SPA fallback is Fedora's
`/usr/lib64/spa-0.2`, excluding the old mixed `/usr/local` build. The prefix must
contain no libpipewire/libwireplumber libraries: core/audio libraries remain
Fedora RPM libraries. The existing seat-aware policy and Lua are staged unchanged.
No sensor, orientation, exposure, timestamp, queueing or suspension-guard patch
is altered. No source patch is necessary for this first target.

New files:

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

## Build and inspection results

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
checks do not prove runtime capture, Lua policy execution, or audio behavior.
No camera/audio device was opened for these candidate checks.

Artifacts (volatile /tmp): `sp7-f43-candidate/build-report.json`,
`inspection-report.json`, `staging-check.json`, build/source logs;
`sp7-f43-deployment-stage-final/manifest.json`;
`sp7-f43-rpm-review/{manifest.json,rpm-inspection.json,offline-solver.txt}`;
`sp7-f43-package-solver.txt`. Keep these and both RPM sets before any reboot.

## Exact Fedora package transaction

| Package | Installed | Proposed |
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
`libasound.so.2(ALSA_1.2.15)(64bit)`. This adds an audio dependency to deployment
approval and testing. No stock libcamera or Lua update is required. No package
was changed during preparation. Today's security update left the installed
camera user space unchanged; excluded kernel/GStreamer packages stay excluded.

## Proposed deployment — only after explicit approval

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

## Hardware acceptance: Peter and ChatGPT

- Peter: in normal Camera, verify exactly five logical profiles, image/orientation,
  autofocus where applicable, and useful front/rear images in dim and brighter
  scenes. Check the first rear capture after cold boot, not only a warmed sensor.
- ChatGPT: measure startup, nonblack frame content and valid timestamps for all
  five profiles; repeat the prior 26 captures / 520 frames validation and rapid
  HQ↔Standard and front↔rear switching. Inspect WP capture hosting and matched
  runtime paths; require no media-service recovery or new errors.
- Together: check playback, volume and microphone during/after camera switching
  because PW and ALSA change; then repeat a clean reboot/local-login test.

PR #1, kernel/IPU4/firmware and Step 2 remain unchanged. Hardware acceptance is
pending a separately approved deployment.
