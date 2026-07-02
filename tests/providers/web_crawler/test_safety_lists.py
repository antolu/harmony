from __future__ import annotations

import json
import threading
from pathlib import Path

from harmony.core import FileSafetyListsWriter
from harmony.providers.web_crawler.runtime._safety_lists import SafetyListsManager


def _make_manager(tmp_path: Path) -> tuple[SafetyListsManager, Path]:
    writer = FileSafetyListsWriter(tmp_path)
    return SafetyListsManager(writer), tmp_path / "safety-lists.json"


def test_init_creates_empty_lists(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)

    assert manager.get_allow_patterns() == []
    assert manager.get_deny_patterns() == []


def test_add_allow_pattern_saves_to_file(tmp_path: Path) -> None:
    manager, file_path = _make_manager(tmp_path)

    manager.add_allow_pattern(r"example\.com/admin")

    assert file_path.exists()
    data = json.loads(file_path.read_text())
    assert r"example\.com/admin" in data["allow_patterns"]


def test_add_deny_pattern_saves_to_file(tmp_path: Path) -> None:
    manager, file_path = _make_manager(tmp_path)

    manager.add_deny_pattern(r"/private/.*")

    data = json.loads(file_path.read_text())
    assert r"/private/.*" in data["deny_patterns"]


def test_load_existing_file(tmp_path: Path) -> None:
    file_path = tmp_path / "safety-lists.json"
    data = {
        "allow_patterns": [r"test\.com"],
        "deny_patterns": [r"/secret/"],
        "metadata": {"test": "value"},
    }
    file_path.write_text(json.dumps(data))

    manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))

    assert r"test\.com" in manager.get_allow_patterns()
    assert r"/secret/" in manager.get_deny_patterns()


def test_no_duplicate_patterns(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)

    manager.add_allow_pattern(r"example\.com")
    manager.add_allow_pattern(r"example\.com")

    assert manager.get_allow_patterns().count(r"example\.com") == 1


def test_remove_pattern(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)

    manager.add_allow_pattern(r"example\.com")
    manager.remove_pattern(r"example\.com")

    assert r"example\.com" not in manager.get_allow_patterns()


def test_thread_safety(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)

    num_threads = 10
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=manager.add_allow_pattern, args=(f"pattern{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    patterns = manager.get_allow_patterns()
    assert len(patterns) == num_threads


def test_corrupted_file_starts_fresh(tmp_path: Path) -> None:
    file_path = tmp_path / "safety-lists.json"
    file_path.write_text("corrupted json{{{")

    manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))

    assert manager.get_allow_patterns() == []
