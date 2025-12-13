"""Event handlers - React to domain events.

Event handlers subscribe to domain events and execute side effects:
- Send emails
- Update audit logs
- Invalidate caches
- Trigger workflows

Event handlers are decoupled from the code that emits events, enabling
flexible composition of side effects.
"""
