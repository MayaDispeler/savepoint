"""File-volume snapshot (tar.gz) and restore (clear then extract)."""
import hashlib
import shutil
import tarfile
from pathlib import Path


def tar_dir(src: str, dest: str) -> int:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as t:
        for p in sorted(Path(src).rglob("*")):
            t.add(p, arcname=p.relative_to(src).as_posix(), recursive=False)
    return Path(dest).stat().st_size


def untar_dir(tarball: str, dst: str) -> None:
    d = Path(dst)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    with tarfile.open(tarball, "r:gz") as t:
        t.extractall(d, filter="data")


def files_digest(directory: str) -> dict[str, dict[str, str]]:
    """Digest-shaped view of a directory: pk = relative path, one column `sha`."""
    out: dict[str, dict[str, str]] = {}
    root = Path(directory)
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = {
                    "sha": hashlib.blake2b(p.read_bytes(), digest_size=8).hexdigest()}
    return out
