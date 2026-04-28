from __future__ import annotations

from enum import StrEnum


class LiveClassStatus(StrEnum):
    SCHEDULED = "scheduled"
    OPEN = "open"
    LIVE = "live"
    ENDED = "ended"
    CANCELLED = "cancelled"


class LiveProvider(StrEnum):
    MEDIASOUP = "mediasoup"


class LiveParticipantRole(StrEnum):
    INSTRUCTOR = "instructor"
    CO_INSTRUCTOR = "co_instructor"
    STUDENT = "student"
    ADMIN = "admin"
    GUEST = "guest"


class LiveJoinStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    KICKED = "kicked"
    COMPLETED = "completed"


class LiveInviteStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class LiveRecordingStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class LiveClassEventType(StrEnum):
    SCHEDULED = "live.class.scheduled"
    CANCELLED = "live.class.cancelled"
    STARTED = "live.class.started"
    ENDED = "live.class.ended"
    PARTICIPANT_JOINED = "live.participant.joined"
    PARTICIPANT_LEFT = "live.participant.left"
    RECORDING_ADDED = "live.recording.added"
