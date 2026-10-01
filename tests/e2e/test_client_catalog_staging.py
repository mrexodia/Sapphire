"""Path localization contracts: never route generation or graphical evidence."""
import copy
import json

import pytest

from . import prepare_client_smoke as prepare
from .support.environment import sha256


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    mesh=tmp_path/'host-only.nav'; mesh.write_bytes(b'exact synthetic navigation bytes')
    value={'navigation':{'format':'TSET-v1','polyref_bits':64,'mesh':str(mesh)},
           'route':[[1,2,3],[2,2,3]],'actors':{'fixture':'unchanged'},'quest':65686}
    source=tmp_path/'catalog.json'; source.write_text(json.dumps(value))
    inputs=tmp_path/'input'; inputs.mkdir()
    # Route validation is covered by catalog tests; isolate the staging transform.
    monkeypatch.setattr(prepare,'load_quest_catalog',lambda path:json.loads(path.read_text()))
    return source,inputs,value,mesh


def test_only_mesh_path_is_localized_and_original_bytes_retained(catalog):
    source,inputs,original,mesh=catalog
    proof=prepare.stage_guest_catalog(source,inputs)
    staged=json.loads((inputs/'quest_catalog.json').read_text())
    expected=copy.deepcopy(original); expected['navigation']['mesh']='C:/e2e-input/catalog-mesh.nav'
    assert staged==expected
    assert (inputs/'quest_catalog.original.json').read_bytes()==source.read_bytes()
    assert (inputs/'catalog-mesh.nav').read_bytes()==mesh.read_bytes()
    assert proof['source_catalog_sha256']==sha256(source)
    assert proof['staged_catalog_sha256']==sha256(inputs/'quest_catalog.json')
    assert proof['mesh_sha256']==sha256(mesh)
    assert original['navigation']['mesh']==str(mesh)


@pytest.mark.parametrize('change',['missing_mesh','wrong_format','wrong_bits','boolean_bits','missing_provenance'])
def test_unknown_or_missing_provenance_is_not_fabricated(catalog,change):
    source,inputs,value,mesh=catalog
    if change=='missing_mesh': mesh.unlink()
    if change=='wrong_format': value['navigation']['format']='unknown'
    if change=='wrong_bits': value['navigation']['polyref_bits']=32
    if change=='boolean_bits': value['navigation']['polyref_bits']=True
    if change=='missing_provenance': value.pop('navigation')
    source.write_text(json.dumps(value))
    with pytest.raises(ValueError): prepare.stage_guest_catalog(source,inputs)
    assert not list(inputs.iterdir())
