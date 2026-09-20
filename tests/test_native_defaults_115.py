"""Offline 11.5 saved-default regressions, including the real verify_live entry.

Synthetic fixtures use no codec, app, user draft, media or network. The live
entry fixture substitutes JSON for codec IO and a synthetic draft-root/runtime;
all comparison, evidence, source, mirror and registration checks run normally.
These fixtures do not establish native UI save or compound persistence support.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
import native_edit as edit

PROFILE = 'jy14-headless-macos-11.5.0'
LEGACY_PROFILE = 'jy14-headless-macos-11.4.2'


def timeline():
    """Small native-shaped tree with identifiable speed-bearing owners."""
    return {
        'id': 'synthetic-timeline',
        'new_version': '187.0.0',
        'version': 360000,
        'fps': 30.0,
        'duration': 1000000,
        'canvas_config': {'width': 640, 'height': 360},
        'materials': {
            'videos': [{'id': 'video-material', 'type': 'video'}],
            'audios': [{'id': 'audio-material', 'type': 'music'}],
            'speeds': [
                {'id': 'video-speed', 'type': 'speed', 'speed': 1},
                {'id': 'audio-speed', 'type': 'speed', 'speed': 1},
            ],
        },
        'tracks': [
            {
                'id': kind + '-track',
                'type': kind,
                'segments': [{
                    'id': kind + '-segment',
                    'material_id': kind + '-material',
                    'extra_material_refs': [kind + '-speed'],
                    'speed': 1,
                    'source_timerange': {'start': 0, 'duration': 1000000},
                    'target_timerange': {'start': 0, 'duration': 1000000},
                }],
            }
            for kind in ('video', 'audio')
        ],
    }


def field_owner(document, location):
    """Return exactly one known owner; this is fixture setup, not comparison."""
    if location == 'fps':
        return document, 'fps'
    if location == 'speed_material':
        return document['materials']['speeds'][0], 'speed'
    if location == 'video_segment':
        return document['tracks'][0]['segments'][0], 'speed'
    if location == 'audio_segment':
        return document['tracks'][1]['segments'][0], 'speed'
    raise AssertionError('Unknown fixture location: ' + location)


LOCATIONS = ('fps', 'speed_material', 'video_segment', 'audio_segment')


def compound_timeline():
    document, child = timeline(), timeline()
    child['id'] = 'synthetic-child-timeline'
    document['materials']['drafts'] = [{
        'id': 'compound-material', 'type': 'combination', 'combination_type': 'none',
        'combination_id': 'synthetic-combination', 'draft': child,
    }]
    document['tracks'][0]['segments'][0]['extra_material_refs'].append('compound-material')
    document['materials']['videos'][0].update(
        extra_type_option=2, duration=1000000, width=640, height=360)
    return document


class ComparisonAssertions(unittest.TestCase):
    def assertAccepted(self, expected, actual):
        before_expected, before_actual = deepcopy(expected), deepcopy(actual)
        try:
            try:
                edit.compare_saved_timeline(expected, actual, PROFILE)
            except ValueError as error:
                self.fail('Equivalent saved defaults should be accepted: ' + str(error))
        finally:
            self.assertEqual(expected, before_expected, 'Comparison mutated expected input')
            self.assertEqual(actual, before_actual, 'Comparison mutated actual input')

    def assertRejected(self, expected, actual):
        before_expected, before_actual = deepcopy(expected), deepcopy(actual)
        try:
            with self.assertRaises(ValueError):
                edit.compare_saved_timeline(expected, actual, PROFILE)
        finally:
            self.assertEqual(expected, before_expected, 'Comparison mutated expected input')
            self.assertEqual(actual, before_actual, 'Comparison mutated actual input')


class DefaultOmissionAcceptance(ComparisonAssertions):
    """Omission of a known 11.5 default is semantically equal."""

    def check_default_omitted(self, location):
        expected = timeline()
        actual = deepcopy(expected)
        owner, key = field_owner(actual, location)
        del owner[key]
        self.assertAccepted(expected, actual)

    def test_root_fps_30_omitted(self):
        self.check_default_omitted('fps')

    def test_speed_material_1_omitted(self):
        self.check_default_omitted('speed_material')

    def test_video_segment_speed_1_omitted(self):
        self.check_default_omitted('video_segment')

    def test_audio_segment_speed_1_omitted_synthetic_coverage(self):
        # This additional synthetic case is not claimed as a captured UI save.
        self.check_default_omitted('audio_segment')

    def test_known_child_timeline_fps_30_omitted(self):
        expected = compound_timeline()
        actual = deepcopy(expected)
        del actual['materials']['drafts'][0]['draft']['fps']
        self.assertAccepted(expected, actual)

    def test_known_child_defaults_work_in_both_directions(self):
        for location in LOCATIONS:
            with self.subTest(location=location):
                explicit = compound_timeline()
                omitted = deepcopy(explicit)
                owner, key = field_owner(omitted['materials']['drafts'][0]['draft'], location)
                del owner[key]
                self.assertAccepted(explicit, omitted)
                self.assertAccepted(omitted, explicit)
                field_owner(explicit['materials']['drafts'][0]['draft'], location)[0][key] = 60 if key == 'fps' else 1.5
                self.assertRejected(omitted, explicit)


class EquivalentRepresentationControls(ComparisonAssertions):
    """Green on upstream and the old patch; preserve these existing cases."""

    def test_unchanged_explicit_defaults(self):
        expected = timeline()
        self.assertAccepted(expected, deepcopy(expected))

    def test_both_sides_omit_known_default(self):
        for location in LOCATIONS:
            with self.subTest(location=location):
                expected = timeline()
                owner, key = field_owner(expected, location)
                del owner[key]
                self.assertAccepted(expected, deepcopy(expected))

    def test_missing_default_becomes_explicit_default(self):
        for location in LOCATIONS:
            with self.subTest(location=location):
                actual = timeline()
                expected = deepcopy(actual)
                owner, key = field_owner(expected, location)
                del owner[key]
                self.assertAccepted(expected, actual)


class PreservationRejectionControls(ComparisonAssertions):
    """Green upstream; full plugin suffixes expose the old patch's regression."""

    def test_nondefault_speed_omission_is_rejected(self):
        for location in LOCATIONS[1:]:
            with self.subTest(location=location):
                expected = timeline()
                owner, key = field_owner(expected, location)
                owner[key] = 1.5
                actual = deepcopy(expected)
                owner, key = field_owner(actual, location)
                del owner[key]
                self.assertRejected(expected, actual)

    def test_nondefault_fps_omission_is_rejected(self):
        expected = timeline()
        expected['fps'] = 25
        actual = deepcopy(expected)
        del actual['fps']
        self.assertRejected(expected, actual)

    def test_explicit_default_changes_to_nondefault_is_rejected(self):
        for location in LOCATIONS:
            with self.subTest(location=location):
                expected = timeline()
                actual = deepcopy(expected)
                owner, key = field_owner(actual, location)
                owner[key] = 60 if key == 'fps' else 1.5
                self.assertRejected(expected, actual)

    def test_entire_speed_material_disappears_is_rejected(self):
        expected = timeline()
        actual = deepcopy(expected)
        actual['materials']['speeds'].pop(0)
        self.assertRejected(expected, actual)

    def test_entire_segment_disappears_is_rejected(self):
        for track_index in (0, 1):
            with self.subTest(track_index=track_index):
                expected = timeline()
                actual = deepcopy(expected)
                actual['tracks'][track_index]['segments'].clear()
                self.assertRejected(expected, actual)

    def test_unknown_plugin_materials_speeds_suffix_is_rejected(self):
        expected = timeline()
        expected['plugin'] = {'materials': {'speeds': [{'id': 'plugin-speed', 'speed': 1}]}}
        actual = deepcopy(expected)
        del actual['plugin']['materials']['speeds'][0]['speed']
        self.assertRejected(expected, actual)

    def test_unknown_plugin_tracks_segments_suffix_is_rejected(self):
        expected = timeline()
        expected['plugin'] = {'tracks': [{
            'id': 'plugin-track',
            'segments': [{'id': 'plugin-segment', 'speed': 1}],
        }]}
        actual = deepcopy(expected)
        del actual['plugin']['tracks'][0]['segments'][0]['speed']
        self.assertRejected(expected, actual)

    def test_unknown_plugin_fps_omission_is_rejected(self):
        expected = timeline()
        expected['plugin'] = {'fps': 30}
        actual = deepcopy(expected)
        del actual['plugin']['fps']
        self.assertRejected(expected, actual)

    def test_unknown_nonempty_field_omission_is_rejected(self):
        expected = timeline()
        expected['plugin'] = {'required_value': 'synthetic-payload'}
        actual = deepcopy(expected)
        del actual['plugin']['required_value']
        self.assertRejected(expected, actual)


class ExistingReverseComparisonGap(ComparisonAssertions):
    """Red before either fix: old one-way comparison ignores newly added fields.

    These assert only the known native defaults' desired 11.5 semantics, not a
    general policy that every newly added JSON field should be rejected.
    """

    def check_missing_becomes_nondefault(self, location):
        expected = timeline()
        owner, key = field_owner(expected, location)
        del owner[key]
        actual = deepcopy(expected)
        owner, key = field_owner(actual, location)
        owner[key] = 60 if key == 'fps' else 1.5
        self.assertRejected(expected, actual)

    def test_existing_gap_missing_fps_becomes_60(self):
        self.check_missing_becomes_nondefault('fps')

    def test_existing_gap_missing_material_speed_becomes_1_5(self):
        self.check_missing_becomes_nondefault('speed_material')

    def test_existing_gap_missing_video_speed_becomes_1_5(self):
        self.check_missing_becomes_nondefault('video_segment')

    def test_existing_gap_missing_audio_speed_becomes_1_5(self):
        self.check_missing_becomes_nondefault('audio_segment')


class ContextAndTypeBoundaries(ComparisonAssertions):
    def test_generic_preserved_retains_upstream_material_only_exception(self):
        for location in LOCATIONS:
            with self.subTest(location=location):
                expected = timeline()
                actual = deepcopy(expected)
                owner, key = field_owner(actual, location)
                del owner[key]
                if location == 'speed_material':
                    edit.preserved(expected, actual)  # Existing upstream exception.
                else:
                    with self.assertRaisesRegex(ValueError, 'disappeared'):
                        edit.preserved(expected, actual)

    def test_legacy_profile_does_not_normalize_defaults(self):
        for location in LOCATIONS:
            with self.subTest(location=location):
                expected = timeline()
                expected['new_version'] = '185.0.0'
                actual = deepcopy(expected)
                edit.compare_saved_timeline(expected, actual, LEGACY_PROFILE)
                owner, key = field_owner(actual, location)
                del owner[key]
                if location == 'speed_material':
                    edit.compare_saved_timeline(expected, actual, LEGACY_PROFILE)
                else:
                    with self.assertRaisesRegex(ValueError, 'disappeared'):
                        edit.compare_saved_timeline(expected, actual, LEGACY_PROFILE)
                # The legacy one-way policy stays unchanged in the reverse case.
                expected, actual = actual, expected
                owner, key = field_owner(actual, location)
                owner[key] = 60 if key == 'fps' else 1.5
                edit.compare_saved_timeline(expected, actual, LEGACY_PROFILE)

    def test_unknown_missing_and_mismatched_profiles_are_rejected(self):
        for profile in (None, '', '11.5.0', 'jy14-headless-macos-11.5.1', LEGACY_PROFILE):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                edit.compare_saved_timeline(timeline(), timeline(), profile)
        with self.assertRaises(TypeError):
            edit.compare_saved_timeline(timeline(), timeline())

    def test_invalid_present_values_are_never_default_values(self):
        for location in LOCATIONS:
            for invalid in (None, True, False, '1', [], {}, 0, -1, float('nan'), float('inf')):
                with self.subTest(location=location, invalid=invalid):
                    expected = timeline()
                    actual = deepcopy(expected)
                    owner, key = field_owner(actual, location)
                    owner[key] = invalid
                    self.assertRejected(expected, actual)
                    self.assertRejected(actual, expected)
                    self.assertRejected(actual, deepcopy(actual))

    def test_text_effect_unknown_tracks_do_not_acquire_speed_semantics(self):
        for kind in ('text', 'effect', 'plugin'):
            with self.subTest(kind=kind):
                expected = timeline()
                expected['tracks'][0]['type'] = kind
                actual = deepcopy(expected)
                del actual['tracks'][0]['segments'][0]['speed']
                self.assertRejected(expected, actual)

    def test_unknown_material_owners_do_not_acquire_speed_semantics(self):
        expected = timeline()
        expected['materials']['plugin'] = expected['materials'].pop('videos')
        actual = deepcopy(expected)
        del actual['tracks'][0]['segments'][0]['speed']
        self.assertRejected(expected, actual)
        expected = timeline()
        expected['materials']['speeds'][0]['type'] = 'plugin'
        actual = deepcopy(expected)
        del actual['materials']['speeds'][0]['speed']
        self.assertRejected(expected, actual)

    def test_unverified_compound_shape_and_lost_child_are_rejected(self):
        expected = compound_timeline()
        bad = deepcopy(expected)
        bad['materials']['videos'][0]['extra_type_option'] = 0
        self.assertRejected(bad, deepcopy(bad))
        bad = deepcopy(expected)
        bad['materials']['drafts'][0]['combination_type'] = 'unknown'
        self.assertRejected(bad, deepcopy(bad))
        actual = deepcopy(expected)
        actual['materials']['drafts'].clear()
        self.assertRejected(expected, actual)

    def test_timeline_shaped_plugin_child_stays_strict(self):
        expected = timeline()
        expected['plugin'] = compound_timeline()
        actual = deepcopy(expected)
        del actual['plugin']['materials']['drafts'][0]['draft']['fps']
        self.assertRejected(expected, actual)

    def test_duplicate_ids_and_dangling_refs_are_rejected(self):
        for mutate in (
            lambda doc: doc['materials']['speeds'].append(deepcopy(doc['materials']['speeds'][0])),
            lambda doc: doc['tracks'][0]['segments'][0]['extra_material_refs'].append('missing'),
        ):
            expected = timeline()
            mutate(expected)
            self.assertRejected(expected, deepcopy(expected))

    def test_existing_numeric_and_frame_tolerances_are_preserved(self):
        expected = timeline()
        actual = deepcopy(expected)
        actual['materials']['speeds'][0]['speed'] += 0.000001
        self.assertAccepted(expected, actual)
        actual['tracks'][0]['segments'][0]['source_timerange']['start'] = 20000
        quantized = []
        before = deepcopy(actual)
        edit.compare_saved_timeline(expected, actual, PROFILE, frame_tolerance=33334, quantized=quantized)
        self.assertEqual(len(quantized), 1)
        self.assertEqual(quantized[0]['actual_us'], 20000)
        self.assertEqual(actual, before)
        actual['tracks'][0]['segments'][0]['source_timerange']['start'] = 40000
        with self.assertRaises(ValueError):
            edit.compare_saved_timeline(expected, actual, PROFILE, frame_tolerance=33334)
        actual = deepcopy(expected)
        actual['materials']['speeds'][0]['speed'] += 0.001
        self.assertRejected(expected, actual)


@contextmanager
def saved_copy_fixture(expected, actual, profile=PROFILE):
    """Real verify_live files; isolate codec/runtime IO in a synthetic root."""
    work = ROOT / 'work/native-defaults-tests'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='case-', dir=work) as temporary:
        folder = Path(temporary)
        draft_root, out, source = folder / 'draft-root', folder / 'build', folder / 'source'
        target = draft_root / 'saved-defaults-fixture'
        target.mkdir(parents=True)
        source.mkdir()
        out.mkdir()
        (source / 'unchanged.bin').write_bytes(b'synthetic frozen source')
        for mirror in edit.mirrors(target, expected['id']):
            mirror.parent.mkdir(parents=True, exist_ok=True)
            edit.j.write(mirror, actual)
        draft_id = 'synthetic-draft-identity'
        edit.j.write(target / 'draft_meta_info.json', {'draft_id': draft_id, 'draft_fold_path': str(target)})
        edit.j.write(draft_root / 'root_meta_info.json', {'all_draft_store': [
            {'draft_id': draft_id, 'draft_fold_path': str(target)},
        ]})
        edit.j.write(out / 'plan.json', {'name': target.name})
        edit.j.write(out / 'expected-timeline.json', expected)
        edit.j.write(out / 'build.json', {
            'schema': edit.BUILD_SCHEMA, 'runtime_manifest': edit.j.nd.MANIFEST_SHA,
            'runtime_profile': profile, 'target': str(target), 'draft_id': draft_id,
            'timeline_id': expected['id'], 'source': str(source),
            'source_files': edit.j.files_manifest(source), 'resources': {}, 'media_dependencies': [],
            'operations': [{'op': 'rename_track'}],
            'plan_sha256': edit.j.nd.digest(out / 'plan.json'),
            'expected_timeline_sha256': edit.j.nd.digest(out / 'expected-timeline.json'),
        })
        helper = SimpleNamespace(_decrypt_metadata_in_memory=edit.j.read_json)
        with patch.object(edit.j.nd, 'DRAFT_ROOT', draft_root), \
                patch.object(edit.j.nd, 'helper', return_value=helper), \
                patch.object(edit.j.nd, 'doctor', return_value={'runtime_profile': profile}):
            yield out, target, source


class VerifyLiveEntryTests(unittest.TestCase):
    def test_saved_defaults_pass_complete_verification_with_explicit_doctor_profile(self):
        expected = timeline()
        expected['tracks'][0]['name'] = 'renamed fixture track'
        actual = deepcopy(expected)
        for location in LOCATIONS:
            owner, key = field_owner(actual, location)
            del owner[key]
        with saved_copy_fixture(expected, actual) as (out, target, source):
            before = edit.j.files_manifest(out.parent)
            with patch.object(edit, 'compare_saved_timeline', wraps=edit.compare_saved_timeline) as comparison:
                result = edit.verify_live(out)
            self.assertEqual(comparison.call_count, 1)
            self.assertEqual(comparison.call_args.args[2], PROFILE)
            self.assertEqual(result['status'], 'verified')
            self.assertTrue(result['four_mirrors_equal'])
            self.assertTrue(result['source_files_unchanged'])
            self.assertEqual(edit.j.files_manifest(out.parent), before)

    def test_full_entry_rejects_reverse_nondefaults_and_unknown_field_loss(self):
        for case in (*LOCATIONS, 'plugin'):
            with self.subTest(case=case):
                expected = timeline()
                if case == 'plugin':
                    expected['plugin'] = {'materials': {'speeds': [{'id': 'opaque', 'speed': 1}]}}
                    actual = deepcopy(expected)
                    del actual['plugin']['materials']['speeds'][0]['speed']
                else:
                    owner, key = field_owner(expected, case)
                    del owner[key]
                    actual = deepcopy(expected)
                    field_owner(actual, case)[0][key] = 60 if key == 'fps' else 1.5
                with saved_copy_fixture(expected, actual) as (out, target, source):
                    with self.assertRaises(ValueError):
                        edit.verify_live(out)

    def test_legacy_full_entry_stays_strict(self):
        expected = timeline()
        expected['new_version'] = '185.0.0'
        with saved_copy_fixture(expected, deepcopy(expected), LEGACY_PROFILE) as (out, target, source):
            self.assertEqual(edit.verify_live(out)['status'], 'verified')
        actual = deepcopy(expected)
        del actual['fps']
        with saved_copy_fixture(expected, actual, LEGACY_PROFILE) as (out, target, source):
            with self.assertRaisesRegex(ValueError, 'disappeared'):
                edit.verify_live(out)

    def test_full_entry_schema_upgrade_and_frame_rounding_still_work(self):
        expected = timeline()
        expected['new_version'] = '185.0.0'
        actual = deepcopy(expected)
        actual.update(new_version='187.0.0', last_modified_platform={'app_version': '11.5.0'})
        del actual['fps']
        actual['tracks'][0]['segments'][0]['source_timerange']['start'] = 20000
        with saved_copy_fixture(expected, actual) as (out, target, source):
            result = edit.verify_live(out)
        self.assertEqual(result['native_schema_upgrades'][0]['after'], '187.0.0')
        self.assertEqual(result['native_frame_quantization'][0]['actual_us'], 20000)


class SavedMacOsProvenanceTests(unittest.TestCase):
    """Synthetic public fixtures; no real device identifiers or captured paths."""

    def upgrade_pair(self):
        expected = timeline()
        expected.update(new_version='185.0.0', last_modified_platform={
            'os': 'mac', 'os_version': '13.6.1', 'app_version': '11.4.0',
            'opaque_native_setting': 'keep',
        })
        expected['platform'] = deepcopy(expected['last_modified_platform'])
        actual = deepcopy(expected)
        actual['new_version'] = '187.0.0'
        actual['last_modified_platform'].update(os_version='14.5', app_version='11.5.0')
        return expected, actual

    def verify(self, expected, actual, profile=PROFILE, host='14.5'):
        before_expected, before_actual = deepcopy(expected), deepcopy(actual)
        with saved_copy_fixture(expected, actual, profile) as (out, target, source), \
                patch.object(edit.platform, 'mac_ver', return_value=(host, ('', '', ''), 'arm64')):
            before_files = edit.j.files_manifest(out.parent)
            try:
                return edit.verify_live(out)
            finally:
                self.assertEqual(edit.j.files_manifest(out.parent), before_files)
                self.assertEqual(expected, before_expected)
                self.assertEqual(actual, before_actual)

    def test_current_host_os_restamp_is_reported_on_reviewed_migration(self):
        expected, actual = self.upgrade_pair()
        del actual['fps']
        result = self.verify(expected, actual)
        self.assertEqual(result['status'], 'verified')
        change = result['native_schema_upgrades'][0]
        self.assertEqual((change['before'], change['after']), ('185.0.0', '187.0.0'))
        self.assertEqual(change['last_modified_os_version_before'], '13.6.1')
        self.assertEqual(change['last_modified_os_version_after'], '14.5')
        self.assertEqual(actual['platform']['os_version'], '13.6.1')
        self.assertEqual(actual['last_modified_platform']['os_version'], '14.5')

    def test_noncurrent_or_reverse_os_restamp_is_rejected(self):
        for old, new in (('13.6.1', '14.4'), ('14.5', '13.6.1')):
            with self.subTest(old=old, new=new):
                expected, actual = self.upgrade_pair()
                expected['last_modified_platform']['os_version'] = old
                actual['last_modified_platform']['os_version'] = new
                with self.assertRaisesRegex(ValueError, 'OS provenance'):
                    self.verify(expected, actual)

    def test_both_last_modified_os_labels_must_be_mac(self):
        for old, new in (('windows', 'windows'), ('windows', 'mac'), ('mac', 'windows'), ('mac', None)):
            with self.subTest(old=old, new=new):
                expected, actual = self.upgrade_pair()
                expected['last_modified_platform']['os'] = old
                actual['last_modified_platform']['os'] = new
                with self.assertRaisesRegex(ValueError, 'OS provenance'):
                    self.verify(expected, actual)

    def test_restamp_requires_valid_present_version_strings_and_available_host(self):
        for field in ('expected', 'actual', 'host'):
            for invalid in (None, True, 14.5, '', ' ', '14.latest', '14.5.0 extra'):
                with self.subTest(field=field, invalid=invalid):
                    expected, actual = self.upgrade_pair()
                    host = '14.5'
                    if field == 'host':
                        host = invalid
                    else:
                        (expected if field == 'expected' else actual)['last_modified_platform']['os_version'] = invalid
                    with self.assertRaisesRegex(ValueError, 'OS provenance'):
                        self.verify(expected, actual, host=host)
        expected, actual = self.upgrade_pair()
        del actual['last_modified_platform']['os_version']
        with self.assertRaisesRegex(ValueError, 'OS provenance'):
            self.verify(expected, actual)

    def test_unchanged_schema_and_legacy_profile_do_not_allow_restamp(self):
        for schema, profile, app in (('185.0.0', PROFILE, '11.4.0'), ('187.0.0', PROFILE, '11.5.0'),
                                     ('185.0.0', LEGACY_PROFILE, '11.4.2')):
            with self.subTest(schema=schema, profile=profile):
                expected, actual = self.upgrade_pair()
                expected['new_version'] = actual['new_version'] = schema
                expected['last_modified_platform']['app_version'] = app
                actual['last_modified_platform']['app_version'] = app
                with self.assertRaisesRegex(ValueError, '/last_modified_platform/os_version'):
                    self.verify(expected, actual, profile)

    def test_unknown_profile_cannot_allow_os_restamp(self):
        expected, actual = self.upgrade_pair()
        with self.assertRaisesRegex(ValueError, 'incompatible with this runtime profile'):
            self.verify(expected, actual, 'jy14-headless-macos-11.5.1')

    def test_source_platform_and_other_last_modified_fields_remain_strict(self):
        for case in ('source-os', 'source-app', 'other-last-modified'):
            with self.subTest(case=case):
                expected, actual = self.upgrade_pair()
                if case == 'source-os':
                    actual['platform']['os_version'] = '14.5'
                elif case == 'source-app':
                    actual['platform']['app_version'] = '11.5.0'
                else:
                    actual['last_modified_platform']['opaque_native_setting'] = 'changed'
                with self.assertRaisesRegex(ValueError, 'Preserved value changed'):
                    self.verify(expected, actual)

    def test_no_os_change_does_not_report_or_consult_host_os(self):
        expected, actual = self.upgrade_pair()
        actual['last_modified_platform']['os_version'] = expected['last_modified_platform']['os_version']
        with saved_copy_fixture(expected, actual) as (out, target, source), \
                patch.object(edit.platform, 'mac_ver', side_effect=AssertionError('No OS change to normalize')):
            result = edit.verify_live(out)
        self.assertNotIn('last_modified_os_version_before', result['native_schema_upgrades'][0])
        self.assertNotIn('last_modified_os_version_after', result['native_schema_upgrades'][0])


if __name__ == '__main__':
    unittest.main()
