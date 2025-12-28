"""
Rate Limiter Service

Implements sliding window rate limiting per user/role to prevent abuse.
"""

import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from app.utils.logger import logger


class RateLimiter:
    """
    Sliding window rate limiter with role-based limits.
    
    Tracks request timestamps per user and enforces hourly limits.
    """
    
    # Rate limits per role (requests per hour)
    ROLE_LIMITS = {
        "admin": None,           # Unlimited
        "super_admin": None,     # Unlimited
        "dba": 200,              # 200 requests/hour
        "senior_dev": 150,       # 150 requests/hour
        "power_user": 100,       # 100 requests/hour
        "junior_dba": 50,        # 50 requests/hour
        "qa_tester": 50,         # 50 requests/hour
        "read_only": 30,         # 30 requests/hour
        "contractor": 20,        # 20 requests/hour
        "default": 30,           # Default for unknown roles
    }
    
    # Window size in seconds (1 hour)
    WINDOW_SIZE = 3600
    
    def __init__(self):
        """Initialize rate limiter with empty request history."""
        # Store request timestamps per user: {user_id: [timestamp1, timestamp2, ...]}
        self._requests: Dict[str, List[float]] = defaultdict(list)
        
        # Track when we last cleaned up old entries
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Cleanup every 5 minutes
    
    def check_rate_limit(
        self,
        user_id: str,
        role: str = "default"
    ) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Check if user has exceeded rate limit.
        
        Args:
            user_id: User email address
            role: User role (for determining limit)
            
        Returns:
            Tuple of (allowed, current_count, limit)
            - allowed: True if request is allowed
            - current_count: Number of requests in current window
            - limit: Maximum requests allowed (None for unlimited)
        """
        # Get limit for role
        limit = self.ROLE_LIMITS.get(role, self.ROLE_LIMITS["default"])
        
        # Admins have unlimited access
        if limit is None:
            logger.debug(
                "Rate limit check - unlimited",
                user=user_id,
                role=role
            )
            return True, 0, None
        
        # Clean up old entries periodically
        self._periodic_cleanup()
        
        # Get current time
        now = time.time()
        window_start = now - self.WINDOW_SIZE
        
        # Get user's request history
        user_requests = self._requests[user_id]
        
        # Remove requests outside the current window
        user_requests[:] = [ts for ts in user_requests if ts >= window_start]
        
        # Count requests in window
        current_count = len(user_requests)
        
        # Check if limit exceeded
        allowed = current_count < limit
        
        if allowed:
            # Add current request timestamp
            user_requests.append(now)
            logger.debug(
                "✅ Rate limit check passed",
                user=user_id,
                role=role,
                count=current_count + 1,
                limit=limit
            )
        else:
            logger.warning(
                "🚫 Rate limit exceeded",
                user=user_id,
                role=role,
                count=current_count,
                limit=limit
            )
        
        return allowed, current_count, limit
    
    def get_remaining_requests(
        self,
        user_id: str,
        role: str = "default"
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Get remaining requests for user in current window.
        
        Args:
            user_id: User email address
            role: User role
            
        Returns:
            Tuple of (remaining, limit)
            - remaining: Requests remaining (None for unlimited)
            - limit: Maximum requests allowed (None for unlimited)
        """
        limit = self.ROLE_LIMITS.get(role, self.ROLE_LIMITS["default"])
        
        # Admins have unlimited
        if limit is None:
            return None, None
        
        # Get current time
        now = time.time()
        window_start = now - self.WINDOW_SIZE
        
        # Get user's request history
        user_requests = self._requests[user_id]
        
        # Count requests in window
        current_count = sum(1 for ts in user_requests if ts >= window_start)
        
        remaining = max(0, limit - current_count)
        
        return remaining, limit
    
    def get_window_reset_time(self, user_id: str) -> Optional[float]:
        """
        Get time when oldest request in window expires.
        
        Args:
            user_id: User email address
            
        Returns:
            Timestamp when rate limit window resets (oldest request expires)
            Returns None if no requests in window
        """
        user_requests = self._requests[user_id]
        
        if not user_requests:
            return None
        
        now = time.time()
        window_start = now - self.WINDOW_SIZE
        
        # Find oldest request in current window
        requests_in_window = [ts for ts in user_requests if ts >= window_start]
        
        if not requests_in_window:
            return None
        
        oldest = min(requests_in_window)
        reset_time = oldest + self.WINDOW_SIZE
        
        return reset_time
    
    def reset_user(self, user_id: str) -> None:
        """
        Reset rate limit for specific user (admin override).
        
        Args:
            user_id: User email address
        """
        if user_id in self._requests:
            del self._requests[user_id]
            logger.info(
                "🔄 Rate limit reset for user",
                user=user_id
            )
    
    def _periodic_cleanup(self) -> None:
        """
        Clean up old request timestamps to prevent memory bloat.
        
        Runs every 5 minutes automatically.
        """
        now = time.time()
        
        # Only cleanup if enough time has passed
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        window_start = now - self.WINDOW_SIZE
        
        # Clean up old timestamps for all users
        users_to_remove = []
        cleaned_count = 0
        
        for user_id, timestamps in self._requests.items():
            # Remove expired timestamps
            old_count = len(timestamps)
            timestamps[:] = [ts for ts in timestamps if ts >= window_start]
            cleaned_count += old_count - len(timestamps)
            
            # Remove user entirely if no recent requests
            if not timestamps:
                users_to_remove.append(user_id)
        
        # Remove users with no recent requests
        for user_id in users_to_remove:
            del self._requests[user_id]
        
        if cleaned_count > 0 or users_to_remove:
            logger.debug(
                "🧹 Rate limiter cleanup",
                cleaned_timestamps=cleaned_count,
                removed_users=len(users_to_remove),
                active_users=len(self._requests)
            )
    
    def get_stats(self) -> Dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dict with stats about active users and request counts
        """
        now = time.time()
        window_start = now - self.WINDOW_SIZE
        
        active_users = 0
        total_requests_in_window = 0
        
        for timestamps in self._requests.values():
            requests_in_window = [ts for ts in timestamps if ts >= window_start]
            if requests_in_window:
                active_users += 1
                total_requests_in_window += len(requests_in_window)
        
        return {
            "active_users": active_users,
            "total_users_tracked": len(self._requests),
            "requests_in_window": total_requests_in_window,
            "window_size_seconds": self.WINDOW_SIZE,
            "role_limits": self.ROLE_LIMITS
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get or create global rate limiter instance.
    
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        logger.info("🚦 Rate limiter initialized")
    
    return _rate_limiter
