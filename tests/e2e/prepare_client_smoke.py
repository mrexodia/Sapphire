"""Prepare (never automatically launch) an opt-in, offline Windows Sandbox smoke run."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

from .support.catalog import load_quest_catalog
from .support.client_smoke import CLIENT_SHA256, CLIENT_VERSION, REVIEW_CHECKS, validate_review
from .support.environment import REPO, sha256
from .support.client_snapshot import freeze_source

LEGACY_DLLS = ("d3dx9_43.dll", "d3dx11_43.dll", "D3DCompiler_43.dll", "XINPUT1_3.dll",
               "XAPOFX1_5.dll", "XactEngine3_7.dll", "XAudio2_7.dll", "X3DAudio1_7.dll")


def sandbox_xml(mappings):
    root = ET.Element("Configuration")
    for key, value in {"Networking": "Disable", "ClipboardRedirection": "Disable",
                       "AudioInput": "Disable", "VideoInput": "Disable",
                       "PrinterRedirection": "Disable", "vGPU": "Enable", "MemoryInMB": "8192"}.items():
        ET.SubElement(root, key).text = value
    folders = ET.SubElement(root, "MappedFolders")
    if sum(not readonly for _, _, readonly in mappings) != 1:
        raise ValueError("exactly one writable output mapping required")
    for host, guest, readonly in mappings:
        if not readonly and guest != "C:/e2e-output":
            raise ValueError("only diagnostic output may be writable")
        node = ET.SubElement(folders, "MappedFolder")
        ET.SubElement(node, "HostFolder").text = str(host)
        ET.SubElement(node, "SandboxFolder").text = guest.replace("/", "\\")
        ET.SubElement(node, "ReadOnly").text = str(readonly).lower()
    command = ET.SubElement(root, "LogonCommand")
    ET.SubElement(command, "Command").text = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/e2e-input/bootstrap.ps1")
    return ET.tostring(root, encoding="unicode")


def approve(output):
    output = Path(output)
    ticket = json.loads((output / "review-ticket.json").read_text(encoding="utf-8"))
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if status.get("phase") != "review" or status.get("run") != ticket["run"]:
        raise ValueError("no active review for this run")
    if sha256(output / "review.png") != ticket["frame_sha256"]:
        raise ValueError("review frame changed")
    review = {"version": 1, **ticket, "checks": REVIEW_CHECKS, "manual_review": True}
    validate_review(review, ticket)
    temporary = output / "review.tmp"
    temporary.write_text(json.dumps(review, indent=2), encoding="utf-8")
    temporary.replace(output / "review.json")


def stage_guest_catalog(catalog_path, inputs):
    """Localize only provenance's mesh path; preserve route/content and exact mesh bytes."""
    catalog_path, inputs = Path(catalog_path), Path(inputs)
    original = load_quest_catalog(catalog_path)
    navigation = original.get("navigation", {})
    if (navigation.get("format") != "TSET-v1" or type(navigation.get("polyref_bits")) is not int
            or navigation["polyref_bits"] != 64 or not isinstance(navigation.get("mesh"), str)):
        raise ValueError("development catalog requires supported navigation provenance")
    mesh = Path(navigation["mesh"])
    if not mesh.is_file():
        raise ValueError("catalog provenance mesh is missing")
    shutil.copy2(catalog_path, inputs / "quest_catalog.original.json")
    shutil.copy2(mesh, inputs / "catalog-mesh.nav")
    localized = copy.deepcopy(original)
    localized["navigation"]["mesh"] = "C:/e2e-input/catalog-mesh.nav"
    (inputs / "quest_catalog.json").write_text(json.dumps(localized, indent=2), encoding="utf-8")
    proof = {"scope": "navigation-path-localization-only-not-route-generation",
             "source_catalog_sha256": sha256(catalog_path),
             "staged_catalog_sha256": sha256(inputs / "quest_catalog.json"),
             "mesh_sha256": sha256(mesh), "changed_field": "navigation.mesh"}
    if sha256(inputs / "catalog-mesh.nav") != proof["mesh_sha256"]:
        raise ValueError("staged catalog mesh differs from source")
    (inputs / "catalog-provenance.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return proof


def prepare(profile_path, client_path, destination, crt_dirs=(), *, development_check=False):
    if type(development_check) is not bool:
        raise ValueError("development-check must be an explicit boolean")
    if os.name != "nt":
        raise RuntimeError("preparation requires Windows with Windows Sandbox installed")
    destination = Path(destination).resolve()
    if not destination.is_relative_to(REPO / ".e2e-artifacts"):
        raise ValueError("private preparation directory must be under .e2e-artifacts")
    if destination.exists():
        raise FileExistsError("refuse to overwrite or reuse a prepared run")
    for module in ("PIL.ImageGrab", "psutil"):
        if importlib.util.find_spec(module) is None:
            raise ValueError(f"preparing Python installation requires {module}")
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    client = Path(client_path).resolve()
    if sha256(client) != CLIENT_SHA256:
        raise ValueError("only the verified unmodified 3.3 DX11 executable is supported")
    game = client.parent
    data = Path(profile["game_data"]).resolve()
    for version in (game / "ffxivgame.ver", data.parent / "ffxivgame.ver"):
        if version.read_text(encoding="utf-8").strip() != CLIENT_VERSION:
            raise ValueError("client/data version mismatch")
    catalog_path = Path(profile["quest_catalog"]).resolve()
    catalog = load_quest_catalog(catalog_path)
    fixture = {"position": catalog["route"][0], "territory": 130,
               "catalog_sha256": sha256(catalog_path), "placement_is_travel": False,
               "development_check": development_check}
    binary_root = Path(profile["binaries"]).resolve()
    system = Path(os.environ["WINDIR"]) / "System32"
    git_exe = shutil.which("git")
    if not git_exe:
        raise ValueError("Git for Windows required")
    git_root = next((p for p in Path(git_exe).resolve().parents if (p / "cmd/git.exe").is_file()), None)
    if git_root is None:
        raise ValueError("cannot locate Git for Windows installation")
    navigation = Path(profile["navigation"]).resolve()
    maria = Path(profile["mariadb_bin"]).resolve().parent
    directories = [REPO, data, game / "movie", git_root, navigation, maria, Path(sys.executable).parent]
    copies = [(binary_root / (name + ".exe"), "bin/" + name + ".exe")
              for name in ("api", "lobby", "server", "dbm")]
    copies += [(p, "bin/" + p.name) for p in binary_root.glob("*.dll")]
    copies += [(Path(profile["worker"]).resolve(), "bin/sapphire_test_client.exe")]
    for directory in crt_dirs:
        directory = Path(directory).resolve()
        if not directory.is_dir() or not list(directory.glob("*.dll")):
            raise ValueError("CRT directory must contain DLLs")
        copies += [(p, "bin/" + p.name) for p in directory.glob("*.dll")]
    if crt_dirs:  # Debug CRT needs this SDK component in addition to compiler redists.
        copies.append((system / "ucrtbased.dll", "bin/ucrtbased.dll"))
    copies += [(client, "client/ffxiv_dx11.exe")]
    copies += [(game / name, "client/" + name) for name in ("bink2w64.dll", "ffxivgame.ver", "fileinfo.fiin")]
    copies += [(system / name, "client/" + name) for name in LEGACY_DLLS]
    for directory in directories + [binary_root / "compiledscripts"]:
        if not directory.is_dir():
            raise FileNotFoundError(directory)
    for source, _ in copies:
        if not source.is_file():
            raise FileNotFoundError(source)
    if not (system / "WindowsSandbox.exe").is_file():
        raise ValueError("Windows Sandbox must already be installed")
    # No services, network configuration, DLL registration or installed game settings
    # are changed here. All setup is copying private inputs and writing a WSB file.
    inputs, output = destination / "input", destination / "output"
    inputs.mkdir(parents=True)
    output.mkdir()
    source_root = destination / "source"
    source_manifest = freeze_source(REPO, source_root)
    (inputs / "source.json").write_text(json.dumps(source_manifest, indent=2), encoding="utf-8")
    for source, relative in copies:
        target = inputs / relative
        target.parent.mkdir(exist_ok=True)
        if target.exists() and sha256(target) != sha256(source):
            raise ValueError(f"conflicting staged library: {target.name}")
        shutil.copy2(source, target)
    shutil.copytree(binary_root / "compiledscripts", inputs / "bin/compiledscripts",
                    ignore=shutil.ignore_patterns("*.pdb", "cache", "*_LOCK"))
    guest_profile = {"binaries": "C:/e2e-input/bin", "worker": "C:/e2e-input/bin/sapphire_test_client.exe",
                     "game_data": "C:/e2e-sqpack", "mariadb_bin": "C:/e2e-mariadb/bin",
                     "navigation": "C:/e2e-navigation"}
    if development_check:
        provenance = stage_guest_catalog(catalog_path, inputs)
        fixture["source_catalog_sha256"] = provenance["source_catalog_sha256"]
        fixture["catalog_sha256"] = provenance["staged_catalog_sha256"]
        guest_profile["quest_catalog"] = "C:/e2e-input/quest_catalog.json"
    (inputs / "profile.json").write_text(json.dumps(guest_profile, indent=2), encoding="utf-8")
    (inputs / "fixture.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    (inputs / "bootstrap.ps1").write_text(
        '$ErrorActionPreference="Stop"\n'
        '$env:PATH="C:/e2e-python;C:/e2e-git/cmd;C:/e2e-input/bin;"+$env:PATH\n'
        '$env:PYTHONDONTWRITEBYTECODE="1"\n'
        '$env:GIT_CONFIG_COUNT="1"\n$env:GIT_CONFIG_KEY_0="safe.directory"\n'
        '$env:GIT_CONFIG_VALUE_0="C:/sapphire-repo"\nSet-Location C:/sapphire-repo\n'
        '& C:/e2e-python/python.exe -m tests.e2e.run_client_smoke *> C:/e2e-output/bootstrap.log\n',
        encoding="utf-8")
    mappings = [(source_root, "C:/sapphire-repo", True), (inputs, "C:/e2e-input", True),
                (output, "C:/e2e-output", False), (Path(sys.executable).parent, "C:/e2e-python", True),
                (git_root, "C:/e2e-git", True), (data, "C:/e2e-sqpack", True),
                (game / "movie", "C:/e2e-movie", True), (maria, "C:/e2e-mariadb", True),
                (navigation, "C:/e2e-navigation", True)]
    (destination / "run.wsb").write_text(sandbox_xml(mappings), encoding="utf-8")
    manifest = {"version": 1, "status": "prepared_not_executed", "client_sha256": CLIENT_SHA256,
                "config_sha256": sha256(destination / "run.wsb"),
                "source_revision": source_manifest["revision"],
                "source_manifest_sha256": sha256(inputs / "source.json"),
                "working_tree_changes_included": False,
                "inputs": {p.relative_to(inputs).as_posix(): sha256(p) for p in inputs.rglob("*") if p.is_file()}}
    (destination / "inputs.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination / "run.wsb"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    setup = modes.add_parser("prepare")
    for name in ("profile", "client", "output"):
        setup.add_argument("--" + name, required=True)
    setup.add_argument("--crt-dir", action="append", default=[])
    setup.add_argument("--development-check", action="store_true",
                       help="After manual rendering review, run two separate bots with manual viewer Say checkpoints")
    review = modes.add_parser("approve-rendering", help="ONLY after manually examining the requested evidence")
    review.add_argument("--output", required=True)
    review.add_argument("--reviewed-all-checks", action="store_true", required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        print(prepare(args.profile, args.client, args.output, args.crt_dir, development_check=args.development_check))
    else:
        approve(args.output)


if __name__ == "__main__":
    main()
