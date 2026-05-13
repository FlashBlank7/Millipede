from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


class SandboxClient(ABC):
    @abstractmethod
    async def create(self, runcard_id: str) -> str:
        """Create a sandbox session. Returns session_id."""

    @abstractmethod
    async def exec(self, session_id: str, command: str, timeout: int = 300) -> ExecResult:
        """Execute a shell command inside the sandbox."""

    @abstractmethod
    async def exec_python(self, session_id: str, code: str, timeout: int = 300) -> ExecResult:
        """Execute Python code inside the sandbox."""

    @abstractmethod
    async def write_file(self, session_id: str, path: str, content: bytes) -> None:
        """Write a file into the sandbox filesystem."""

    @abstractmethod
    async def read_file(self, session_id: str, path: str) -> bytes:
        """Read a file from the sandbox filesystem."""

    @abstractmethod
    async def list_files(self, session_id: str, path: str = "/workspace") -> list[str]:
        """List files under a directory."""

    @abstractmethod
    async def snapshot(self, session_id: str) -> str:
        """Create a filesystem snapshot. Returns snapshot_id."""

    @abstractmethod
    async def restore(self, session_id: str, snapshot_id: str) -> None:
        """Restore sandbox to a previous snapshot."""

    @abstractmethod
    async def destroy(self, session_id: str) -> None:
        """Terminate and clean up the sandbox."""
