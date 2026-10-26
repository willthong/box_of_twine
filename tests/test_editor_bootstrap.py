"""The editor bootstrap owns Twine's localStorage seeding contract.

The bootstrap runs before Twine's bundle and must leave localStorage holding
exactly the current story, because Twine's loader attaches every indexed
passage record to its story. These tests run the real bootstrap in a Node
sandbox with a persistent fake localStorage; see ``tests/js``.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE_SCRIPT = ROOT / "tests" / "js" / "editor_bootstrap_test.js"


@pytest.mark.skipif(
    shutil.which("node") is None, reason="node is needed to run the bootstrap"
)
def test_editor_bootstrap_replaces_a_storys_passages_instead_of_appending():
    result = subprocess.run(
        ["node", str(NODE_SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
        cwd=ROOT,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
