"""Private runtime packaging only, not DLL-load or graphical compatibility proof."""
import pytest

from .prepare_client_smoke import crt_inputs


def test_release_crt_is_explicit_and_does_not_require_debug_ucrt(tmp_path):
    release=tmp_path/'release'; release.mkdir()
    for name in ('msvcp140.dll','vcruntime140.dll','msvcp140_1.dll'):
        (release/name).write_bytes(b'synthetic fixture')
    inputs=crt_inputs([], [release], tmp_path/'no-system-directory')
    assert {name for path,name in inputs}=={'bin/msvcp140.dll','bin/vcruntime140.dll','bin/msvcp140_1.dll'}
    assert all(path.parent==release for path,name in inputs)


def test_debug_ucrt_behavior_is_preserved(tmp_path):
    debug=tmp_path/'debug'; debug.mkdir(); (debug/'msvcp140d.dll').write_bytes(b'fixture')
    system=tmp_path/'system'
    assert (system/'ucrtbased.dll','bin/ucrtbased.dll') in crt_inputs([debug],[],system)


@pytest.mark.parametrize('names',[[],['vcruntime140.dll'],['msvcp140.dll'],['unrelated.dll']])
def test_incomplete_release_crt_folder_rejected(tmp_path,names):
    for name in names: (tmp_path/name).write_bytes(b'fixture')
    with pytest.raises(ValueError): crt_inputs([], [tmp_path], tmp_path/'system')


def test_no_implicit_host_runtime_search(tmp_path):
    assert crt_inputs([],[],tmp_path)==[]
