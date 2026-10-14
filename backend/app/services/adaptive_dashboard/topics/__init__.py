"""Topics Strangler Package (Phase G5.5).

Authoritative boundaries for analytical story assembly and immutable ExecutiveTopic construction.
"""
from __future__ import annotations

from .contracts import (
    ExecutiveTopic,
    ExecutiveTopicDraft,
    TopicIdGenerator,
    TopicIdentityFactory,
    TopicIdentitySeed,
)
from .factory import ExecutiveTopicFactory
from .integrity import (
    StoryAssemblyIntegrity,
    StoryAssemblyIntegrityError,
)

__all__ = [
    "ExecutiveTopic",
    "ExecutiveTopicDraft",
    "ExecutiveTopicFactory",
    "StoryAssemblyIntegrity",
    "StoryAssemblyIntegrityError",
    "TopicIdGenerator",
    "TopicIdentityFactory",
    "TopicIdentitySeed",
]
