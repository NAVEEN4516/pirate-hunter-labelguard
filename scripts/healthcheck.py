import socket
import sys
import time
import urllib.request

if sys.argv[1] == "http":
    with urllib.request.urlopen(sys.argv[2], timeout=3) as response:
        assert response.status == 200
else:
    from labelguard import store
    from labelguard.config import settings

    with store.connection() as db:
        row = db.execute(
            "SELECT max(timestamp) FROM heartbeats WHERE worker LIKE ? AND stage=?",
            (socket.gethostname() + "-%", sys.argv[2]),
        ).fetchone()
    assert row and row[0] and time.time() - row[0] < settings().run_timeout_s + 15
