import asyncio
import io
import tarfile
import uuid
from typing import Any

import docker
import docker.errors
from docker.models.containers import Container

from app.config import get_settings
from app.infra.sandbox.base import ExecResult, SandboxClient

settings = get_settings()

WORKSPACE = "/workspace"


class DockerSandboxClient(SandboxClient):
    def __init__(self):
        self._docker = docker.from_env()
        self._sessions: dict[str, Container] = {}

    async def create(self, runcard_id: str) -> str:
        session_id = f"millipede-{runcard_id[:8]}-{uuid.uuid4().hex[:6]}"

        def _create():
            return self._docker.containers.run(
                settings.sandbox_image,
                name=session_id,
                detach=True,
                tty=True,
                stdin_open=True,
                working_dir=WORKSPACE,
                mem_limit=settings.sandbox_memory_limit,
                cpu_period=100_000,
                cpu_quota=int(settings.sandbox_cpu_limit * 100_000),
                network_mode=settings.sandbox_network,
                volumes={},
                labels={"millipede.runcard_id": runcard_id},
                remove=False,
            )

        container = await asyncio.to_thread(_create)
        # Create standard directory structure
        await self.exec(session_id, f"mkdir -p {WORKSPACE}/inputs {WORKSPACE}/processing {WORKSPACE}/models {WORKSPACE}/reports {WORKSPACE}/outputs")
        self._sessions[session_id] = container
        return session_id

    async def exec(self, session_id: str, command: str, timeout: int = 300) -> ExecResult:
        container = self._get_container(session_id)

        def _exec():
            result = container.exec_run(
                ["bash", "-c", command],
                workdir=WORKSPACE,
                demux=True,
            )
            stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
            stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
            return ExecResult(exit_code=result.exit_code, stdout=stdout, stderr=stderr)

        return await asyncio.wait_for(asyncio.to_thread(_exec), timeout=timeout)

    async def exec_python(self, session_id: str, code: str, timeout: int = 300) -> ExecResult:
        # Write code to temp file and execute to avoid shell escaping issues
        tmp_path = f"/tmp/_exec_{uuid.uuid4().hex[:8]}.py"
        await self.write_file(session_id, tmp_path, code.encode())
        return await self.exec(session_id, f"python {tmp_path}", timeout=timeout)

    async def write_file(self, session_id: str, path: str, content: bytes) -> None:
        container = self._get_container(session_id)

        def _write():
            import os
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                info = tarfile.TarInfo(name=os.path.basename(path))
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
            buf.seek(0)
            container.put_archive(os.path.dirname(path) or "/", buf.getvalue())

        await asyncio.to_thread(_write)

    async def read_file(self, session_id: str, path: str) -> bytes:
        container = self._get_container(session_id)

        def _read():
            bits, _ = container.get_archive(path)
            buf = io.BytesIO()
            for chunk in bits:
                buf.write(chunk)
            buf.seek(0)
            with tarfile.open(fileobj=buf) as tar:
                member = tar.getmembers()[0]
                f = tar.extractfile(member)
                return f.read() if f else b""

        return await asyncio.to_thread(_read)

    async def list_files(self, session_id: str, path: str = WORKSPACE) -> list[str]:
        result = await self.exec(session_id, f"find {path} -type f | sort")
        return [line for line in result.stdout.splitlines() if line]

    async def snapshot(self, session_id: str) -> str:
        container = self._get_container(session_id)
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"

        def _commit():
            container.commit(repository="millipede-snapshots", tag=snapshot_id)

        await asyncio.to_thread(_commit)
        return snapshot_id

    async def restore(self, session_id: str, snapshot_id: str) -> None:
        # Stop current container, start new one from snapshot image
        await self.destroy(session_id)
        runcard_id = session_id.split("-")[1]

        def _restore():
            return self._docker.containers.run(
                f"millipede-snapshots:{snapshot_id}",
                name=session_id,
                detach=True,
                tty=True,
                stdin_open=True,
                working_dir=WORKSPACE,
                mem_limit=settings.sandbox_memory_limit,
                cpu_period=100_000,
                cpu_quota=int(settings.sandbox_cpu_limit * 100_000),
                network_mode=settings.sandbox_network,
                remove=False,
            )

        container = await asyncio.to_thread(_restore)
        self._sessions[session_id] = container

    async def destroy(self, session_id: str) -> None:
        container = self._sessions.pop(session_id, None)
        if container is None:
            try:
                container = await asyncio.to_thread(self._docker.containers.get, session_id)
            except docker.errors.NotFound:
                return

        def _stop_remove():
            try:
                container.stop(timeout=5)
            except Exception:
                pass
            try:
                container.remove(force=True)
            except Exception:
                pass

        await asyncio.to_thread(_stop_remove)

    def _get_container(self, session_id: str) -> Container:
        if session_id in self._sessions:
            return self._sessions[session_id]
        # Re-attach to existing container (e.g. after worker restart)
        container = self._docker.containers.get(session_id)
        self._sessions[session_id] = container
        return container


_sandbox_client: DockerSandboxClient | None = None


def get_sandbox() -> DockerSandboxClient:
    global _sandbox_client
    if _sandbox_client is None:
        _sandbox_client = DockerSandboxClient()
    return _sandbox_client
