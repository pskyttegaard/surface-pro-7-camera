#!/usr/bin/env python3
"""Inspect isolated candidate linkage without enumerating or opening cameras."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', required=True, type=Path)
a = p.parse_args()
w = a.workspace.resolve()
camera = w / 'prefix/camera'
userspace = w / 'prefix/userspace'
env = dict(os.environ, LD_LIBRARY_PATH=str(camera / 'lib64'))
report = dict(camera_prefix=str(camera), checks=[], hardware_access=False)
for name in ['lib64/libcamera.so.0.7', 'lib64/libcamera-base.so.0.7',
             'lib64/libcamera/ipa/ipa_soft_simple.so',
             'lib64/spa-0.2/libcamera/libspa-libcamera.so',
             'libexec/libcamera/soft_ipa_proxy']:
    target = camera / name
    result = subprocess.run(['ldd', str(target)], env=env, text=True, capture_output=True, check=True)
    assert 'not found' not in result.stdout, result.stdout
    lines = [line.strip() for line in result.stdout.splitlines() if 'libcamera' in line]
    assert all(str(camera / 'lib64') in line for line in lines), lines
    report['checks'].append(dict(file=name, camera_dependencies=lines))
# RTLD_NOW resolves plugin and IPA symbols without constructing factories,
# starting a CameraManager, touching devices, or connecting to PipeWire.
probe = '''import ctypes,sys
ctypes.CDLL(sys.argv[1], mode=2)
print('dlopen RTLD_NOW passed')'''
for name in ['lib64/libcamera/ipa/ipa_soft_simple.so',
             'lib64/spa-0.2/libcamera/libspa-libcamera.so']:
    subprocess.run([sys.executable, '-c', probe, str(camera / name)], env=env, check=True)
# Only this inspection environment loads the candidate daemon/client libraries.
# Deployed service config uses camera/lib64 alone, leaving RPM audio libraries.
tool_env = dict(env, LD_LIBRARY_PATH=str(userspace / 'lib64') + ':' + str(camera / 'lib64'))
for binary, version in [('pipewire', '1.4.11'), ('wireplumber', '0.5.14')]:
    output = subprocess.check_output([str(userspace / 'bin' / binary), '--version'],
                                     text=True, env=tool_env)
    assert version in output, output
    report['checks'].append(dict(binary=binary, version_output=output.strip()))
report['passed'] = True
(w / 'inspection-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(w / 'inspection-report.json')
