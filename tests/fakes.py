"""Small in-memory stand-ins for the Supabase client used by the API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Resolver = Callable[[str, list[tuple[Any, ...]]], list[dict[str, Any]]]


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeQuery:
    def __init__(self, table: str, resolver: Resolver) -> None:
        self.table = table
        self.resolver = resolver
        self.calls: list[tuple[Any, ...]] = []

    def select(self, fields: str, **_: Any) -> FakeQuery:
        self.calls.append(("select", fields))
        return self

    def eq(self, column: str, value: Any) -> FakeQuery:
        self.calls.append(("eq", column, value))
        return self

    def gt(self, column: str, value: Any) -> FakeQuery:
        self.calls.append(("gt", column, value))
        return self

    def or_(self, expression: str) -> FakeQuery:
        self.calls.append(("or_", expression))
        return self

    def order(self, column: str, **_: Any) -> FakeQuery:
        self.calls.append(("order", column))
        return self

    def limit(self, value: int) -> FakeQuery:
        self.calls.append(("limit", value))
        return self

    def execute(self) -> FakeResponse:
        self.calls.append(("execute",))
        return FakeResponse(self.resolver(self.table, self.calls))


class FakeSupabase:
    def __init__(self, resolver: Resolver) -> None:
        self.resolver = resolver
        self.queries: list[FakeQuery] = []

    def table(self, name: str) -> FakeQuery:
        query = FakeQuery(name, self.resolver)
        self.queries.append(query)
        return query
