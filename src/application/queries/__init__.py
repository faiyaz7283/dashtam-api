"""Queries - Read operations that fetch data.

Queries represent a request for information. They are immutable dataclasses
with question-like names (GetUser, ListAccounts).

Each query has a corresponding handler that fetches and returns the requested
data. Queries NEVER change state.
"""
