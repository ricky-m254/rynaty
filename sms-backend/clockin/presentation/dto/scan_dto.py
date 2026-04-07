"""
ScanRequestDTO / ScanResponseDTO
Validates and structures the data flowing in/out of the scan endpoints.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScanRequestDTO:
    """Validated input for POST /clockin/scan/"""
    fingerprint_id: str
    device_api_key: str
    timestamp: Optional[str] = None   # ISO string — parsed by use case
    card_no: Optional[str] = None
    direction: str = 'auto'

    @classmethod
    def from_request_data(cls, data: dict) -> 'ScanRequestDTO':
        fid = data.get('fingerprint_id') or data.get('id') or ''
        if not fid:
            raise ValueError("fingerprint_id is required")
        return cls(
            fingerprint_id = fid,
            device_api_key = data.get('api_key', ''),
            timestamp      = data.get('timestamp'),
            card_no        = data.get('card_no', ''),
            direction      = data.get('direction', 'auto'),
        )


@dataclass
class ScanResponseDTO:
    """Standardised response returned by scan endpoints."""
    status: str               # 'ok' | 'duplicate' | 'unknown_person' | 'error'
    event_type: Optional[str] = None
    is_late: bool = False
    person: Optional[str] = None
    message: str = ''

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}
