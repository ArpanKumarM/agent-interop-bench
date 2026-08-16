"""Run storage.

Phase 1 uses an in-memory repository behind an interface so a persistent
(e.g. database-backed) implementation can be swapped in later without
changing the API layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.run import Run


class RunRepository(ABC):
    @abstractmethod
    def save(self, run: Run) -> None: ...

    @abstractmethod
    def get(self, run_id: str) -> Run | None: ...

    @abstractmethod
    def list_all(self) -> list[Run]: ...


class InMemoryRunRepository(RunRepository):
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._runs[run.summary.run_id] = run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list_all(self) -> list[Run]:
        return list(self._runs.values())
