"""Strict graphical consumption of one isolated Environment identity manifest.

The manifest identifies exact staged executables/scripts/catalog/combat inputs and
records external data/navigation hashes. It is not native-build provenance or a
compatibility, execution, rendering, or external-root completeness oracle.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from .development import DevelopmentError

SCOPE = "exact-graphical-environment-input-identities-not-native-build-provenance"


def _hex(value, length=64):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _hash_map(value, *, nonempty=True):
    if not isinstance(value, dict) or (nonempty and not value):
        raise DevelopmentError("graphical environment hash map is malformed")
    for relative, digest in value.items():
        pure = PurePosixPath(relative) if isinstance(relative, str) else None
        if (pure is None or pure.is_absolute() or not pure.parts
                or pure.as_posix() != relative or "\\" in relative
                or any(part in {"", ".", ".."} for part in pure.parts)
                or not _hex(digest)):
            raise DevelopmentError("graphical environment hash entry is malformed")
    return value


def require_graphical_environment_manifest(manifest, inputs_manifest, source_manifest):
    fields = {"revision", "dirty", "profile", "fixture_version", "deadline_scale",
              "database", "runtime", "game_data", "navmesh", "ports", "binaries",
              "worker_sha256", "scripts", "server_navigation", "combat_data",
              "quest_catalog", "quest_catalog_navigation"}
    if (not isinstance(manifest, dict) or set(manifest) != fields
            or not _hex(manifest.get("revision"), 40)
            or manifest.get("revision") != source_manifest.get("revision")
            or manifest.get("dirty") is not False
            or manifest.get("profile") != "sapphire-3.3"
            or type(manifest.get("fixture_version")) is not int
            or manifest["fixture_version"] != 2
            or type(manifest.get("deadline_scale")) is not int
            or manifest["deadline_scale"] != 1):
        raise DevelopmentError("graphical environment manifest boundary is invalid")
    database = manifest.get("database")
    if (not isinstance(database, str) or not database.startswith("sapphire_e2e_")
            or len(database) != len("sapphire_e2e_") + 32
            or any(char not in "0123456789abcdef" for char in database[len("sapphire_e2e_"):])
            or any(not isinstance(manifest.get(key), str) or not manifest[key]
                   for key in ("runtime", "game_data", "navmesh"))):
        raise DevelopmentError("graphical environment runtime identity is malformed")
    ports = manifest.get("ports")
    if (not isinstance(ports, dict) or set(ports) != {"database", "api", "lobby", "world"}
            or any(type(value) is not int or not 0 < value <= 65535 for value in ports.values())
            or len(set(ports.values())) != 4):
        raise DevelopmentError("graphical environment ports are malformed")

    prepared = inputs_manifest.get("inputs") if isinstance(inputs_manifest, dict) else None
    tracked = source_manifest.get("sha256") if isinstance(source_manifest, dict) else None
    if not isinstance(prepared, dict) or not isinstance(tracked, dict):
        raise DevelopmentError("graphical environment provenance inputs are malformed")
    binaries = manifest.get("binaries")
    expected_binaries = {name: prepared.get(f"bin/{name}.exe")
                         for name in ("api", "lobby", "server", "dbm")}
    if (not isinstance(binaries, dict) or binaries != expected_binaries
            or any(not _hex(value) for value in expected_binaries.values())
            or manifest.get("worker_sha256") != prepared.get("bin/sapphire_test_client.exe")
            or not _hex(manifest.get("worker_sha256"))):
        raise DevelopmentError("graphical environment executable identities differ from preparation")

    prefix = "bin/compiledscripts/"
    expected_scripts = {}
    for relative, digest in prepared.items():
        if relative.startswith(prefix):
            tail = relative[len(prefix):]
            if "/" not in tail and tail:
                expected_scripts[tail] = digest
    scripts = manifest.get("scripts")
    if not expected_scripts or scripts != expected_scripts or _hash_map(scripts) != scripts:
        raise DevelopmentError("graphical environment script identities differ from preparation")

    expected_combat = {relative: tracked.get("data/" + relative) for relative in
        ("actions/player.json", "bnpcs/w1f2/w1f2.json", "bnpcs/w1f2/w1f2_paths.json")}
    if (manifest.get("combat_data") != expected_combat
            or any(not _hex(value) for value in expected_combat.values())):
        raise DevelopmentError("graphical environment combat-data identities differ from source")
    catalog, navigation = manifest.get("quest_catalog"), manifest.get("quest_catalog_navigation")
    if (not isinstance(catalog, dict) or set(catalog) != {"path", "sha256"}
            or not isinstance(catalog.get("path"), str) or not catalog["path"]
            or catalog.get("sha256") != prepared.get("quest_catalog.json")
            or not isinstance(navigation, dict) or set(navigation) != {"path", "sha256"}
            or not isinstance(navigation.get("path"), str) or not navigation["path"]
            or navigation.get("sha256") != prepared.get("catalog-mesh.nav")
            or not _hex(catalog.get("sha256")) or not _hex(navigation.get("sha256"))):
        raise DevelopmentError("graphical environment catalog identities differ from preparation")
    server_navigation = _hash_map(manifest.get("server_navigation"))
    return {"verified": True, "scope": SCOPE,
            "revision": manifest["revision"], "worker_sha256": manifest["worker_sha256"],
            "binary_sha256": binaries, "script_count": len(scripts),
            "server_navigation_file_count": len(server_navigation),
            "quest_catalog_sha256": catalog["sha256"],
            "quest_navigation_sha256": navigation["sha256"],
            "combat_data_sha256": expected_combat,
            "note": "External root completeness, native builds, execution and rendering are out of scope."}


def read_json_object(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read graphical {label}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"graphical {label} is not an object")
    return value


def sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise DevelopmentError("cannot hash graphical environment manifest") from error
