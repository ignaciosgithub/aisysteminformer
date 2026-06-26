from __future__ import annotations

import os

from aisysteminformer.core import files


def test_find_processes_using_open_file(tmp_path: object) -> None:
    target = os.path.join(str(tmp_path), "held.txt")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("data")
        handle.flush()
        holders = files.find_processes_using_path(target)

    pids = {h.pid for h in holders}
    assert os.getpid() in pids
    mine = [h for h in holders if h.pid == os.getpid()]
    assert any(h.reference == "open_file" for h in mine)


def test_find_processes_using_path_no_match() -> None:
    holders = files.find_processes_using_path("/nonexistent/path/that/should/not/exist-xyz")
    assert isinstance(holders, list)
    assert holders == []
