from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from .errors import LifecycleError
from .security import assert_no_links


@contextmanager
def registry_lock(root: Path):
    root=Path(root); lockdir=root/"tmp"/"locks"; lockdir.mkdir(parents=True,exist_ok=True); assert_no_links(lockdir)
    path=lockdir/"lifecycle-registry.lock"; acquired=False; fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
    try:
        if os.name=="nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        acquired=True; yield
    except OSError as exc: raise LifecycleError("LIFECYCLE_CONCURRENCY_CONFLICT","registry is busy") from exc
    finally:
        if acquired:
            try:
                if os.name=="nt":
                    import msvcrt
                    msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(fd,fcntl.LOCK_UN)
            except OSError: pass
        os.close(fd)
