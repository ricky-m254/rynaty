"""
Communication Domain Entities — Phase 9 (Prompt 18)
Pure Python dataclasses. No Django. No ORM.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Message:
    id: Optional[int]
    sender_id: int
    recipient_ids: List[int] = field(default_factory=list)
    subject: Optional[str] = None
    body: str = ""
    channel: str = "INTERNAL"
    is_read: bool = False
    sent_at: Optional[str] = None

    CHANNELS = ("INTERNAL", "SMS", "EMAIL", "PUSH")

    def validate(self) -> None:
        if not self.body:
            raise ValueError("Message body is required")
        if self.channel not in self.CHANNELS:
            raise ValueError(f"channel must be one of {self.CHANNELS}")


@dataclass
class Announcement:
    id: Optional[int]
    title: str
    body: str
    author_id: int
    audience: str = "ALL"
    published_at: Optional[str] = None
    is_active: bool = True

    AUDIENCES = ("ALL", "PARENTS", "STUDENTS", "STAFF", "TEACHERS")

    def validate(self) -> None:
        if not self.title:
            raise ValueError("Announcement title is required")
        if self.audience not in self.AUDIENCES:
            raise ValueError(f"audience must be one of {self.AUDIENCES}")
