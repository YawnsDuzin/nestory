"""Rate limiter (slowapi) — IP 기반 throttle.

라우트에 @limiter.limit("N/minute") 데코레이터로 적용. request: Request 인자가
시그니처에 있어야 IP를 추출 가능.

테스트는 conftest에서 limiter.enabled = False로 비활성화.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter"]
