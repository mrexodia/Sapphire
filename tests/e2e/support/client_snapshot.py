"""Freeze committed coordinator sources for a disposable offline graphical run."""
from pathlib import Path
import hashlib
import subprocess


def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args],
                                   stderr=subprocess.PIPE, timeout=60)


def freeze_source(repository, destination):
    """Local-only shallow checkout, no worktree copies, submodule fetches or launch.

    The retained .git allows the guest Environment to report the actual revision.
    No alternates/hardlinks may depend on the host checkout. A concurrent commit
    changing the shallow tip can fail preparation; never substitute that new tip.
    """
    repository, destination = Path(repository).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('source snapshot destination must be new')
    revision = git(repository, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    subprocess.run(['git', '-c', 'core.fsmonitor=false', 'clone', '--quiet', '--no-local',
                    '--depth=1', '--no-checkout', '--no-recurse-submodules', '--', str(repository), str(destination)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    git(destination, 'config', 'core.autocrlf', 'false')
    git(destination, 'config', 'core.eol', 'lf')
    git(destination, '-c', 'core.hooksPath=/dev/null', 'checkout', '--quiet', '--no-recurse-submodules', '--detach', revision)
    if git(destination, 'rev-parse', 'HEAD').decode().strip() != revision:
        raise ValueError('source snapshot revision changed')
    if (destination / '.git/objects/info/alternates').exists():
        raise ValueError('source snapshot must not depend on host object storage')
    # Remove even the local origin: guest operation must not fetch from a host path.
    git(destination, 'remote', 'remove', 'origin')
    if git(destination, 'status', '--porcelain', '--untracked-files=all', '--ignored').strip():
        raise ValueError('source snapshot is not a clean committed checkout')
    files, gitlinks = {}, []
    for entry in git(destination, 'ls-tree', '-r', '-z', revision).split(b'\0'):
        if not entry: continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        relative = raw_path.decode('utf-8')
        if kind == 'commit':
            gitlinks.append({'path':relative, 'revision':oid, 'materialized':False})
            continue
        path = destination / relative
        if mode == '120000' or path.is_symlink() or not path.is_file():
            raise ValueError('unsupported symbolic or missing coordinator source')
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'version':1, 'scope':'committed-coordinator-source-not-native-build-attestation',
            'revision':revision, 'dirty':False, 'sha256':files, 'gitlinks':gitlinks,
            'submodule_fetch_performed':False, 'remote_configured':False}


def verify_source(repository, manifest):
    """Check the prepared source before guest fixture/process setup, not a signature."""
    repository = Path(repository).resolve()
    if (manifest.get('version') != 1 or type(manifest.get('version')) is not int
            or manifest.get('scope') != 'committed-coordinator-source-not-native-build-attestation'
            or manifest.get('dirty') is not False
            or manifest.get('submodule_fetch_performed') is not False
            or manifest.get('remote_configured') is not False):
        raise ValueError('unsupported source snapshot manifest')
    if git(repository, 'rev-parse', 'HEAD').decode().strip() != manifest.get('revision'):
        raise ValueError('prepared coordinator revision mismatch')
    if git(repository, 'status', '--porcelain', '--untracked-files=all', '--ignored').strip() or git(repository, 'remote').strip():
        raise ValueError('prepared coordinator source changed or has a remote')
    files, links = {}, []
    for entry in git(repository, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not entry: continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        relative = raw_path.decode('utf-8')
        if kind == 'commit':
            directory = repository / relative
            if directory.is_symlink() or (directory.exists() and any(directory.iterdir())):
                raise ValueError('unexpected materialized coordinator submodule')
            links.append({'path':relative, 'revision':oid, 'materialized':False})
            continue
        path = repository / relative
        if mode == '120000' or path.is_symlink() or not path.is_file():
            raise ValueError('unsupported source snapshot entry')
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if files != manifest.get('sha256') or links != manifest.get('gitlinks'):
        raise ValueError('prepared coordinator bytes or gitlinks changed')
    if (repository / '.git/objects/info/alternates').exists():
        raise ValueError('prepared source depends on external object storage')
    return manifest['revision']
