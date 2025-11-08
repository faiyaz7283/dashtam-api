"""Commands - Write operations that change state.

Commands represent user intent to perform an action. They are immutable
dataclasses with imperative names (RegisterUser, UpdatePassword).

Each command has a corresponding handler that contains the business logic
to execute the command.
"""
