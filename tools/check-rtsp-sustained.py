#!/usr/bin/env python3
"""Continuously decode RTSP and check every sampled frame for black output."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time

import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst
from PIL import Image

Gst.init(None)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('url')
parser.add_argument('--duration', type=float, default=610)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--fps', type=float, default=15)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
decoder = next((name for name in ('avdec_h264', 'openh264dec')
                if Gst.ElementFactory.find(name)), None)
if decoder is None:
    raise SystemExit('No installed H.264 decoder available')
# URL is assigned as a property rather than interpolated into pipeline syntax.
pipeline = Gst.parse_launch(
    'rtspsrc name=source protocols=tcp latency=250 ! rtph264depay ! h264parse ! '
    f'{decoder} ! videoconvert ! videoscale ! '
    'video/x-raw,format=GRAY8,width=64,height=48 ! '
    'appsink name=check emit-signals=true sync=false max-buffers=2 drop=true')
pipeline.get_by_name('source').set_property('location', args.url)
lock = threading.Lock()
state = dict(frames=0, black_frames=0, first=None, last=None, first_pts=None,
             last_pts=None, max_gap=0.0, min_mean=255.0, max_mean=0.0,
             timestamp_regressions=0, first_utc=None, last_utc=None)
last_pixels = None
hashes = set()
frame_log = (args.output / 'frames.jsonl').open('w', buffering=1)


def sample_ready(sink):
    global last_pixels
    sample = sink.emit('pull-sample')
    buffer = sample.get_buffer()
    mapped, mapping = buffer.map(Gst.MapFlags.READ)
    if not mapped:
        return Gst.FlowReturn.ERROR
    now = time.monotonic()
    utc = datetime.now(timezone.utc).isoformat()
    try:
        pixels = bytes(mapping.data)
    finally:
        buffer.unmap(mapping)
    mean = sum(pixels) / len(pixels)
    bright_fraction = sum(v > 16 for v in pixels) / len(pixels)
    nonblack = mean > 5 and max(pixels) > 20 and bright_fraction > .01
    digest = hashlib.sha256(pixels).hexdigest()
    with lock:
        if state['first'] is None:
            state['first'] = now
            state['first_pts'] = buffer.pts
            state['first_utc'] = utc
            Image.frombytes('L', (64, 48), pixels).save(args.output / 'first.png')
        if state['last'] is not None:
            state['max_gap'] = max(state['max_gap'], now - state['last'])
            if buffer.pts != Gst.CLOCK_TIME_NONE and state['last_pts'] is not None:
                state['timestamp_regressions'] += int(buffer.pts <= state['last_pts'])
        state['last'] = now
        state['last_pts'] = buffer.pts
        state['last_utc'] = utc
        state['frames'] += 1
        state['black_frames'] += int(not nonblack)
        state['min_mean'] = min(state['min_mean'], mean)
        state['max_mean'] = max(state['max_mean'], mean)
        hashes.add(digest)
        last_pixels = pixels
        frame_log.write(json.dumps(dict(frame=state['frames'], utc=utc,
            elapsed=now - state['first'], pts=buffer.pts, mean=round(mean, 3),
            bright_fraction=round(bright_fraction, 4), nonblack=nonblack,
            sha256=digest)) + '\n')
    return Gst.FlowReturn.OK


pipeline.get_by_name('check').connect('new-sample', sample_ready)
started = time.monotonic()
next_report = 0
error = None
warnings = []
try:
    pipeline.set_state(Gst.State.PLAYING)
    bus = pipeline.get_bus()
    while True:
        message = bus.timed_pop_filtered(Gst.SECOND,
            Gst.MessageType.ERROR | Gst.MessageType.EOS | Gst.MessageType.WARNING)
        if message:
            if message.type == Gst.MessageType.ERROR:
                detail, debug = message.parse_error()
                error = f'{detail}: {debug}'
                break
            if message.type == Gst.MessageType.EOS:
                error = 'unexpected end of RTSP stream'
                break
            warning, debug = message.parse_warning()
            warnings.append(f'{warning}: {debug}')
        now = time.monotonic()
        with lock:
            current = dict(state)
        if current['first'] is None:
            if now - started > 35:
                error = 'no decoded frame within 35 seconds'
                break
            continue
        elapsed = now - current['first']
        if now - current['last'] > 5:
            error = 'decoded frame delivery stalled for more than 5 seconds'
            break
        if current['black_frames']:
            error = 'decoded black frame detected'
            break
        if elapsed >= next_report:
            print(json.dumps(dict(elapsed=round(elapsed, 1), frames=current['frames'],
                black_frames=current['black_frames'], min_mean=round(current['min_mean'], 2),
                max_gap=round(current['max_gap'], 3))), flush=True)
            next_report += 60
        if elapsed >= args.duration:
            break
finally:
    pipeline.set_state(Gst.State.NULL)
    frame_log.close()
    if last_pixels is not None:
        Image.frombytes('L', (64, 48), last_pixels).save(args.output / 'last.png')

span = 0 if state['first'] is None else state['last'] - state['first']
pts_span = 0 if state['first_pts'] is None else (state['last_pts'] - state['first_pts']) / Gst.SECOND
passed = (error is None and span >= args.duration - 2 and
          state['frames'] >= args.duration * args.fps * .8 and
          state['black_frames'] == 0 and state['timestamp_regressions'] == 0 and
          state['max_gap'] <= 5)
summary = dict(url=args.url, requested_duration=args.duration, decoded_span_seconds=span,
    pts_span_seconds=pts_span, frames=state['frames'], black_frames=state['black_frames'],
    min_mean=state['min_mean'], max_mean=state['max_mean'], max_frame_gap=state['max_gap'],
    timestamp_regressions=state['timestamp_regressions'], unique_frame_hashes=len(hashes),
    average_fps=state['frames'] / span if span else 0, first_utc=state['first_utc'],
    last_utc=state['last_utc'], warnings=warnings, error=error, passed=passed)
(args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary), flush=True)
raise SystemExit(0 if passed else 1)
