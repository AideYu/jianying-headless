"""Portable Windows build/export integration and fail-closed checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
import ffmpeg_graph
import windows_export
import windows_portable as portable


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg is required')
class WindowsFfmpegTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix='windows-ffmpeg-'))
        self.original_project_root = portable.ROOT
        portable.ROOT = self.temp / 'project'
        (portable.ROOT / 'work').mkdir(parents=True)
        self.root = portable.ROOT / 'work' / 'case with spaces'
        self.root.mkdir()
        self.source = self.root / '中文 source with spaces.mp4'
        self.silent = self.root / 'silent source.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc=size=320x240:rate=25', '-f', 'lavfi', '-i',
                        'sine=frequency=880:sample_rate=48000', '-t', '2', '-shortest',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        '-y', str(self.source)], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=blue:size=320x240:rate=25', '-t', '1',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(self.silent)],
                       check=True)
        self.font = next((Path(item) for item in
                          (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf',
                           r'C:\Windows\Fonts\arial.ttf') if Path(item).is_file()), None)
        self.plan = self.root / 'plan.json'
        value = {'schema': 'jy14-headless-plan/v1', 'name': 'portable-test',
                 'canvas': {'width': 320, 'height': 240, 'fps': 25},
                 'tracks': [
                    {'type': 'video', 'name': 'main', 'segments': [
                        {'source': str(self.source), 'start_us': 0, 'duration_us': 800_000,
                         'source_start_us': 0, 'source_duration_us': 800_000,
                         'speed': 1, 'volume': .5},
                        {'source': str(self.silent), 'start_us': 1_200_000,
                         'duration_us': 800_000, 'source_start_us': 0,
                         'source_duration_us': 800_000}]},
                    {'type': 'text', 'name': 'captions', 'segments': [
                        {'text': '第一条字幕', 'start_us': 100_000, 'duration_us': 700_000}]},
                    {'type': 'text', 'name': 'overlapping captions', 'segments': [
                        {'text': '重叠字幕', 'start_us': 500_000, 'duration_us': 700_000}]}
                 ]}
        self.plan.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        self.build = self.root / 'build'
        portable.build(self.plan, self.build)

    def record(self):
        return portable.read_json(self.build / 'build.json')

    def rewrite_record_for_timeline(self):
        record = self.record()
        timeline = self.build / 'render' / portable.TIMELINE_NAME
        record['timeline_sha256'] = portable.digest(timeline)
        record['files'] = portable.files_manifest(self.build / 'render')
        (self.build / 'build.json').write_bytes(portable.packed(record))

    def test_snapshot_binds_timeline_and_resources(self):
        portable.verify_build(self.build)
        timeline = self.build / 'render' / portable.TIMELINE_NAME
        raw = timeline.read_bytes()
        changed = raw.replace(b'"volume":0.5', b'"volume":0.6', 1)
        self.assertEqual(len(changed), len(raw))
        timeline.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'snapshot changed|timeline changed'):
            portable.verify_build(self.build)

    def test_external_media_path_is_rejected_even_with_updated_record(self):
        timeline_path = self.build / 'render' / portable.TIMELINE_NAME
        timeline = portable.read_json(timeline_path)
        timeline['materials']['videos'][0]['path'] = str(self.source)
        timeline_path.write_bytes(portable.packed(timeline))
        self.rewrite_record_for_timeline()
        with self.assertRaisesRegex(ValueError, 'Unsafe media dependency path'):
            portable.verify_build(self.build)

    def test_changed_and_missing_resources_are_rejected(self):
        _, record, timeline = portable.verify_build(self.build)
        relative = timeline['materials']['videos'][0]['path']
        path = self.build / 'render' / relative
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            portable.verify_build(self.build)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            portable.verify_build(self.build)

    def test_caption_graph_is_one_connected_chain(self):
        _, record, timeline = portable.verify_build(self.build)
        job = self.root / 'graph-job'
        job.mkdir()
        staged, _ = windows_export.stage_timeline(timeline, self.build, record, job)
        _, graph, video, _, _ = ffmpeg_graph.build(staged, job, self.font)
        self.assertIn('[vtext0]drawtext=', graph)
        self.assertEqual(video, '[vout]')
        self.assertIn('color=c=black', graph)
        self.assertIn('adelay=0:all=1', graph)

    def test_render_gap_captions_audio_and_full_decode(self):
        if self.font is None:
            self.skipTest('A local test font is required')
        try:
            result = windows_export.run(self.build, self.root / 'export', font=self.font)
        except Exception as error:
            log = self.root / 'export' / 'ffmpeg.stderr.log'
            graph = self.root / 'export' / 'filter_complex.txt'
            self.fail(str(error) + '\n' + (log.read_text(encoding='utf-8', errors='replace')
                                           if log.is_file() else 'FFmpeg log is missing') + '\nGRAPH:\n' +
                      (graph.read_text(encoding='utf-8', errors='replace')
                       if graph.is_file() else 'Graph is missing'))
        self.assertEqual(result['schema'], 'jy14-ffmpeg-export/v2')
        self.assertTrue(result['full_decode_passed'])
        self.assertTrue(result['source_build_unchanged'])
        self.assertEqual(result['media']['streams'][0]['width'], 320)
        self.assertEqual(result['media']['streams'][0]['height'], 240)
        self.assertEqual(Path(result['output']).name, 'render.mp4')
        graph = (self.root / 'export' / 'filter_complex.txt').read_text(encoding='utf-8')
        self.assertIn('[vtext0]drawtext=', graph)
        self.assertIn('adelay=0:all=1', graph)

    def test_unsupported_native_track_is_rejected(self):
        plan = json.loads(self.plan.read_text(encoding='utf-8'))
        plan['tracks'].append({'type': 'effect', 'segments': [
            {'name': 'light-shake', 'start_us': 0, 'duration_us': 100_000}]})
        bad = self.root / 'bad-plan.json'
        bad.write_text(json.dumps(plan), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'supports only'):
            portable.build(bad, self.root / 'bad-build')

    def tearDown(self):
        portable.ROOT = self.original_project_root
        shutil.rmtree(self.temp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
