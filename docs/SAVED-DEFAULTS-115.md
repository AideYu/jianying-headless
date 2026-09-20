# Saved fps and speed defaults on Jianying 11.5

Jianying 11.5 can omit `fps: 30`, speed-material `speed: 1`, and video
segment `speed: 1` when it saves a draft. `edit verify` previously reported
these omissions as lost nonempty fields. In the reverse direction, a saved
input that already omitted a default could hide a newly added nondefault value.

`native_edit.compare_saved_timeline(expected, actual, runtime_profile)` now
interprets these defaults on independent comparison copies, then uses the
existing preservation comparator. `verify_live()` passes the profile returned
by `doctor()` after handling the existing reviewed schema migration. Neither
the expected snapshot nor the saved draft is rewritten.

## Exact scope

Default interpretation requires `jy14-headless-macos-11.5.0`. Both input graphs
must pass the existing compound/basic structural validation and the runtime
schema validator. Recognized locations are:

| Owner | Missing field | Meaning |
| --- | --- | --- |
| Root or real child timeline from `native_compound.graph()` | `fps` | `30` |
| Direct `materials.speeds` node whose `type` is `speed` | `speed` | `1` |
| Direct video-track segment referencing the `videos` bucket | `speed` | `1` |
| Direct audio-track segment referencing the `audios` bucket | `speed` | `1` |

Video and audio are the existing editor's speed-bearing track kinds. Audio
omission is covered synthetically; the original observed save difference was
video. Text, effect, unknown track kinds and unknown material buckets receive
no segment-speed exception. Similarly named fields below plugins are untouched.
Real nested timelines receive the same interpretation, but this does not enable
compound home registration or establish native compound save persistence.

Only an absent key is filled. Present values must be positive finite numbers;
`null`, booleans, strings and other invalid values are rejected by this 11.5
comparison path. This prevents Python's `True == 1` equality from treating a
boolean as a speed default. Explicit numbers retain the original `1e-5`
absolute comparison tolerance. The existing per-frame source/target time
quantization tolerance and report are unchanged.

Both sides receive the interpretation: omitted speed versus `1.5`, or omitted
fps versus `60`, is a mismatch in either direction. Entire material/segment
loss, unknown nonempty field loss and unreviewed compound structures still
fail. This change is not a general bidirectional rewrite of arbitrary JSON:
the original comparator's policy for newly added unknown fields remains.

Known 11.4 profiles retain the upstream preservation comparison without new
default filling. This includes its existing one-way exception for omitted unit
speed on uncurved speed materials; fps and segment omissions remain strict.
Unknown profiles and incompatible schemas fail the existing schema validator.
Generic `preserved()` is unchanged; source, frozen build and sidecar callers
continue to use its existing rules.

## Current-host OS stamp during the reviewed schema upgrade

A fresh native save also showed `last_modified_platform.os_version` changing
from the blueprint's original OS version to the current Mac's version. The
source `platform` remained unchanged. `verify_live()` now recognizes this
last-save stamp only inside the existing reviewed `185.0.0` to `187.0.0`
migration on the exact 11.5 profile. Both last-modified `os` labels must be
`mac`; old, saved and current-host versions must be nonempty dotted numeric
strings, and the saved version must exactly equal `platform.mac_ver()[0]`.

The comparison copy retains the prior stamp so the content comparison can
proceed. The schema-upgrade report includes `last_modified_os_version_before`
and `last_modified_os_version_after`. Neither saved bytes nor frozen evidence
is rewritten. Source `platform`, other platform fields, unchanged schemas,
legacy/unknown profiles, invalid values and noncurrent OS stamps receive no new
exception. Public tests use synthetic OS values and no captured device IDs.

## Offline regression

From the repository root:

```sh
python3 -m unittest discover -s tests -p test_native_defaults_115.py -v
```

The fixture covers both directions of default omission, explicit nondefault
changes, lost nodes, plugin suffixes, genuine child timelines, invalid types,
numeric/frame tolerances, input immutability, 11.4 controls and invalid profiles.
It also covers current-host OS stamping on the exact schema migration and
rejection outside that context, through the actual `verify_live()` entry.

It also invokes the production `verify_live()` entry with temporary synthetic
files. Only the codec reader, runtime doctor and draft root are substituted;
the actual comparison, evidence hashes, registration, source manifest and four
separate mirror files are checked. This catches missing production wiring while
remaining runnable without an editor, codec, media, network or user drafts.

## Native acceptance

Offline tests do not establish an actual save/cold-reopen result. For that
acceptance, build a fresh normal draft and an independent edit copy using the
reviewed runtime. Open only the copy, play, save, quit, cold-reopen and quit
again; run the full `edit verify --build ...` command afterwards. Retain the
source manifest, saved timeline and verification report. The source must remain
unchanged, the edit must persist, and all four live mirror files must agree.

Negative default-value experiments belong in frozen JSON copies, never in a
user's registered draft. A field-level replay of a historical capture does not
substitute for this fresh native acceptance.
