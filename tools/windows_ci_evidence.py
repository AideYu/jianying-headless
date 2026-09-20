#!/usr/bin/env python3
"""Create retained Windows FFmpeg evidence from the reviewed public media fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
import windows_portable


def main():
    work = ROOT / 'work'
    input_dir = work / 'windows-ci-input'
    build = work / 'windows-ci-build'
    export = work / 'windows-ci-export'
    if any(path.exists() for path in (input_dir, build, export)):
        raise SystemExit('Windows CI evidence paths must not already exist')
    input_dir.mkdir(parents=True)
    source = ROOT / 'docs/media/hypit-original-preview.mp4'
    if not source.is_file():
        raise SystemExit('Reviewed public media fixture is missing')
    media = input_dir / '真实 media with spaces.mp4'
    shutil.copyfile(source, media)
    font = next((Path(item) for item in
                 (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf')
                 if Path(item).is_file()), None)
    if font is None:
        raise SystemExit('A Windows Chinese system font is required')
    plan = {'schema': 'jy14-headless-plan/v1', 'name': 'windows-ci-evidence',
            'canvas': {'width': 640, 'height': 360, 'fps': 25},
            'tracks': [
                {'type': 'video', 'name': 'main', 'segments': [{
                    'source': str(media.resolve()), 'start_us': 0, 'duration_us': 2_000_000,
                    'source_start_us': 0, 'source_duration_us': 2_000_000,
                    'speed': 1, 'volume': .75}]},
                {'type': 'text', 'name': 'caption one', 'segments': [{
                    'text': 'Windows 中文验收', 'start_us': 100_000, 'duration_us': 1_000_000}]},
                {'type': 'text', 'name': 'caption two', 'segments': [{
                    'text': '重叠字幕与空格路径', 'start_us': 700_000, 'duration_us': 1_000_000}]}
            ]}
    plan_path = input_dir / 'plan.json'
    plan_path.write_bytes(windows_portable.packed(plan))
    entry = ROOT / 'skills/yichen-jianying-edit/scripts/headless_draft.py'
    environment = dict(os.environ, JIANYING_HEADLESS_ROOT=str(ROOT))
    commands = [
        [sys.executable, str(entry), 'build', '--plan', str(plan_path), '--out', str(build)],
        [sys.executable, str(entry), 'verify-build', '--build', str(build)],
        [sys.executable, str(entry), 'export', '--backend', 'windows-ffmpeg',
         '--build', str(build), '--out', str(export), '--font', str(font)],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, env=environment, check=True, timeout=900)
    result = windows_portable.read_json(export / 'result.json')
    if not result['full_decode_passed'] or not result['source_build_unchanged']:
        raise SystemExit('Windows evidence did not pass final verification')
    print(json.dumps({'status': result['status'], 'output_sha256': result['output_sha256'],
                      'font_sha256': result['font']['sha256'],
                      'full_decode_passed': result['full_decode_passed']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
