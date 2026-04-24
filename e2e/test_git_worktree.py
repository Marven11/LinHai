import os
import subprocess
import tempfile

import pytest
from pathlib import Path

from linhai.agent.create import _setup_git_worktree
from linhai.machine_control.main import MachineControl
from linhai.machine_control.master_host.master_host import MasterHostControl
from linhai.registry import Registry
from linhai.sandbox import NoSandbox

pytestmark = pytest.mark.asyncio


def _create_git_repo(tmpdir: Path) -> Path:
    tmpdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(tmpdir), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmpdir),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmpdir),
        capture_output=True,
        check=True,
    )
    (tmpdir / "hello.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "."], cwd=str(tmpdir), capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmpdir),
        capture_output=True,
        check=True,
    )
    return tmpdir


async def test_git_worktree_created():
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = _create_git_repo(Path(tmpdir) / "repo")
            os.chdir(str(repo_dir))

            registry = Registry()
            conversation_folder = Path(tmpdir) / "conversation"
            conversation_folder.mkdir()
            registry.register_member("conversation_folder", conversation_folder)

            ctl = MachineControl(
                registry=registry, remote_machines=[], remote_shell_control="python"
            )
            _setup_git_worktree(registry, ctl)

            worktree_path = conversation_folder / "worktree"
            assert worktree_path.exists()
            assert worktree_path.is_dir()
            assert (worktree_path / "hello.txt").exists()
            assert os.getcwd() == str(worktree_path)

            master_host = ctl.machines["master_host"]
            assert isinstance(master_host, MasterHostControl)
            assert master_host._cwd == str(worktree_path)
    finally:
        os.chdir(original_cwd)


async def test_git_worktree_agent_can_operate():
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = _create_git_repo(Path(tmpdir) / "repo")
            os.chdir(str(repo_dir))

            registry = Registry()
            registry.register_member("process_sandbox", NoSandbox())
            conversation_folder = Path(tmpdir) / "conversation"
            conversation_folder.mkdir()
            registry.register_member("conversation_folder", conversation_folder)

            ctl = MachineControl(
                registry=registry, remote_machines=[], remote_shell_control="python"
            )
            _setup_git_worktree(registry, ctl)

            worktree_path = conversation_folder / "worktree"
            master_host = ctl.machines["master_host"]

            result = await master_host.create_process(["touch", "new_file.txt"])
            assert result.success
            assert (worktree_path / "new_file.txt").exists()

            result = await master_host.create_process(["ls", "hello.txt"])
            assert result.success
            assert "hello.txt" in result.stdout
    finally:
        os.chdir(original_cwd)


async def test_git_worktree_none_machine_control():
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = _create_git_repo(Path(tmpdir) / "repo")
            os.chdir(str(repo_dir))

            registry = Registry()
            conversation_folder = Path(tmpdir) / "conversation"
            conversation_folder.mkdir()
            registry.register_member("conversation_folder", conversation_folder)

            _setup_git_worktree(registry, None)

            worktree_path = conversation_folder / "worktree"
            assert worktree_path.exists()
            assert os.getcwd() == str(worktree_path)
    finally:
        os.chdir(original_cwd)
