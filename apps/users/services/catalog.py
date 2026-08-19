"""Read-only presentation of the code-defined role/capability catalog.

These classes encapsulate how the static ``Role`` / ``Capability``
definitions are exposed through the admin read APIs, keeping the views
thin and free of module-level helper functions.
"""

from __future__ import annotations

from typing import Optional

from apps.users.constants import ROLE_CAPABILITIES, Capability, Role


class RoleCatalog:
    """Serialization helpers for the platform roles."""

    @classmethod
    def list(cls) -> list[dict]:
        return [cls.serialize(role) for role in Role]

    @classmethod
    def get(cls, role_key: str) -> Optional[Role]:
        """Return the ``Role`` for ``role_key`` or ``None`` if unknown."""
        try:
            return Role(role_key)
        except ValueError:
            return None

    @staticmethod
    def capabilities(role: Role) -> list[Capability]:
        return sorted(
            ROLE_CAPABILITIES.get(role, frozenset()),
            key=lambda capability: capability.value,
        )

    @classmethod
    def serialize(cls, role: Role) -> dict:
        return {
            "key": role.value,
            "name": role.label,
            "capabilities": [c.value for c in cls.capabilities(role)],
        }

    @classmethod
    def serialize_capabilities(cls, role: Role) -> list[dict]:
        return [
            CapabilityCatalog.serialize(capability)
            for capability in cls.capabilities(role)
        ]


class CapabilityCatalog:
    """Serialization helpers for the platform capabilities."""

    @classmethod
    def list(cls) -> list[dict]:
        return [cls.serialize(capability) for capability in Capability]

    @staticmethod
    def serialize(capability: Capability) -> dict:
        return {"key": capability.value, "name": capability.label}
