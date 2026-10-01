"""Local Git snapshot contracts; no graphical execution or network fetches."""
import json
import subprocess
import sys
import types

import pytest

from .support.client_snapshot import freeze_source, git, verify_source


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / 'repository'; root.mkdir()
    subprocess.run(['git','init','--quiet',str(root)],check=True,capture_output=True)
    (root / 'coordinator.py').write_bytes(b'print("committed")\n')
    (root / '.gitignore').write_text('ignored.py\n')
    git(root,'add','.')
    git(root,'-c','user.name=Snapshot Test','-c','user.email=snapshot@example.invalid','commit','--quiet','-m','fixture')
    return root


def test_snapshot_excludes_dirty_staged_and_untracked_host_inputs(repository, tmp_path):
    revision = git(repository,'rev-parse','HEAD').decode().strip()
    (repository / 'coordinator.py').write_text('uncommitted experiment\n')
    (repository / 'staged.py').write_text('staged but not committed\n'); git(repository,'add','staged.py')
    (repository / 'private.json').write_text('private credentials\n')
    before = git(repository,'status','--porcelain')
    root = tmp_path / 'snapshot'; manifest = freeze_source(repository,root)
    assert manifest['revision']==revision and manifest['dirty'] is False
    assert (root/'coordinator.py').read_bytes()==b'print("committed")\n'
    assert not (root/'private.json').exists() and not (root/'staged.py').exists()
    assert not git(root,'remote').strip() and not (root/'.git/objects/info/alternates').exists()
    assert git(repository,'status','--porcelain')==before
    repository.rename(tmp_path/'host-source-unavailable')
    assert verify_source(root,manifest)==revision


@pytest.mark.parametrize('change',['modified','missing','untracked','ignored','remote','alternates','digest','revision','version'])
def test_changed_source_or_manifest_fails_before_guest_setup(repository,tmp_path,change):
    root=tmp_path/'snapshot'; manifest=freeze_source(repository,root)
    if change=='modified': (root/'coordinator.py').write_text('changed\n')
    if change=='missing': (root/'coordinator.py').unlink()
    if change=='untracked': (root/'extra.py').write_text('extra\n')
    if change=='ignored': (root/'ignored.py').write_text('must not shadow imports\n')
    if change=='remote': git(root,'remote','add','unexpected',str(repository))
    if change=='alternates':
        (root/'.git/objects/info/alternates').write_text(str(repository/'.git/objects')+'\n')
    if change=='digest': manifest['sha256']['coordinator.py']='0'*64
    if change=='revision': manifest['revision']='0'*40
    if change=='version': manifest['version']=True
    with pytest.raises(ValueError): verify_source(root,manifest)


def test_snapshot_refuses_reuse(repository,tmp_path):
    root=tmp_path/'snapshot'; root.mkdir(); marker=root/'keep'; marker.write_text('unchanged')
    with pytest.raises(FileExistsError): freeze_source(repository,root)
    assert marker.read_text()=='unchanged'


def test_snapshot_records_but_does_not_fetch_gitlinks(repository,tmp_path):
    revision=git(repository,'rev-parse','HEAD').decode().strip()
    git(repository,'update-index','--add','--cacheinfo',f'160000,{revision},deps/unfetched')
    git(repository,'-c','user.name=Snapshot Test','-c','user.email=snapshot@example.invalid','commit','--quiet','-m','gitlink')
    root=tmp_path/'snapshot'; manifest=freeze_source(repository,root)
    assert manifest['gitlinks']==[{'path':'deps/unfetched','revision':revision,'materialized':False}]
    assert verify_source(root,manifest)==manifest['revision']
    directory=root/'deps/unfetched'; directory.mkdir(parents=True,exist_ok=True)
    (directory/'unexpected').write_text('not committed coordinator content')
    with pytest.raises(ValueError): verify_source(root,manifest)


def test_guest_rejects_source_before_registry_client_or_environment_setup(tmp_path, monkeypatch):
    from . import run_client_smoke as guest
    inputs, output = tmp_path/'input', tmp_path/'output'
    inputs.mkdir(); output.mkdir(); (inputs/'source.json').write_text('{}')
    monkeypatch.setattr(guest,'INPUT',inputs); monkeypatch.setattr(guest,'OUTPUT',output)
    monkeypatch.setattr(guest,'require_guest',lambda:'synthetic isolated Documents')
    called=[]
    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError('setup happened before source verification')
    monkeypatch.setitem(sys.modules,'winreg',types.SimpleNamespace(CreateKey=forbidden,HKEY_CURRENT_USER=0))
    monkeypatch.setitem(sys.modules,'PIL',types.SimpleNamespace(ImageGrab=types.SimpleNamespace(grab=forbidden)))
    monkeypatch.setattr(guest,'Environment',forbidden)
    monkeypatch.setattr(guest.shutil,'copytree',forbidden)
    assert guest.run()==1 and not called
    result=json.loads((output/'result.json').read_text())
    assert result['status']=='failed' and result['failure_stage']=='setup'
    assert result['error'].startswith('ValueError: unsupported source snapshot manifest')
