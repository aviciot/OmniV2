"""
Circuit Breaker Service - Database-Driven Failure Management

Features:
- CLOSED/OPEN/HALF_OPEN state management
- Database-driven configuration
- Per-MCP state tracking
- Automatic recovery testing
"""

import time
from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Omni2Config
from app.utils.logger import logger


class CircuitBreaker:
    """Circuit breaker for MCP failure management."""
    
    # States
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Fast-fail mode
    HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(self):
        self.states: Dict[str, str] = {}
        self.failure_counts: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}
        self.half_open_calls: Dict[str, int] = {}
        
        # Config (loaded from database)
        self.enabled = True
        self.failure_threshold = 5
        self.timeout_seconds = 60
        self.half_open_max_calls = 3
    
    async def load_config(self, db: AsyncSession):
        """Load circuit breaker config from database."""
        try:
            result = await db.execute(
                select(Omni2Config).where(
                    Omni2Config.config_key == 'circuit_breaker',
                    Omni2Config.is_active == True
                )
            )
            config = result.scalar_one_or_none()
            
            if config:
                self.enabled = config.config_value.get('enabled', True)
                self.failure_threshold = config.config_value.get('failure_threshold', 5)
                self.timeout_seconds = config.config_value.get('timeout_seconds', 60)
                self.half_open_max_calls = config.config_value.get('half_open_max_calls', 3)
                
                logger.info(
                    "Circuit breaker config loaded",
                    enabled=self.enabled,
                    failure_threshold=self.failure_threshold,
                    timeout_seconds=self.timeout_seconds
                )
        except Exception as e:
            logger.warning("Failed to load circuit breaker config, using defaults", error=str(e))
    
    def is_open(self, mcp_name: str) -> bool:
        """Check if circuit is open (should fast-fail)."""
        if not self.enabled:
            return False
        
        state = self.states.get(mcp_name, self.CLOSED)
        
        if state == self.OPEN:
            # Check if timeout expired
            elapsed = time.time() - self.last_failure_time.get(mcp_name, 0)
            if elapsed > self.timeout_seconds:
                # Move to HALF_OPEN for testing
                self.states[mcp_name] = self.HALF_OPEN
                self.half_open_calls[mcp_name] = 0
                logger.info("Circuit breaker moved to HALF_OPEN", mcp=mcp_name)
                return False
            return True
        
        if state == self.HALF_OPEN:
            # Limit calls in HALF_OPEN state
            calls = self.half_open_calls.get(mcp_name, 0)
            if calls >= self.half_open_max_calls:
                return True
        
        return False
    
    def record_success(self, mcp_name: str):
        """Record successful call - close circuit."""
        old_state = self.states.get(mcp_name, self.CLOSED)
        self.states[mcp_name] = self.CLOSED
        self.failure_counts[mcp_name] = 0
        self.half_open_calls[mcp_name] = 0
        
        if old_state != self.CLOSED:
            logger.info("Circuit breaker CLOSED", mcp=mcp_name, previous_state=old_state)
    
    def record_failure(self, mcp_name: str):
        """Record failed call - open circuit if threshold reached."""
        state = self.states.get(mcp_name, self.CLOSED)
        
        if state == self.HALF_OPEN:
            # Failure in HALF_OPEN -> back to OPEN
            self.states[mcp_name] = self.OPEN
            self.last_failure_time[mcp_name] = time.time()
            logger.warning("Circuit breaker reopened from HALF_OPEN", mcp=mcp_name)
            return
        
        # Increment failure count
        count = self.failure_counts.get(mcp_name, 0) + 1
        self.failure_counts[mcp_name] = count
        
        # Open circuit if threshold reached
        if count >= self.failure_threshold:
            self.states[mcp_name] = self.OPEN
            self.last_failure_time[mcp_name] = time.time()
            logger.warning(
                "Circuit breaker OPENED",
                mcp=mcp_name,
                failures=count,
                threshold=self.failure_threshold
            )
    
    def get_state(self, mcp_name: str) -> str:
        """Get current circuit state."""
        return self.states.get(mcp_name, self.CLOSED)
    
    def get_retry_after(self, mcp_name: str) -> Optional[int]:
        """Get seconds until retry allowed."""
        if self.states.get(mcp_name) != self.OPEN:
            return None
        
        elapsed = time.time() - self.last_failure_time.get(mcp_name, 0)
        remaining = max(0, int(self.timeout_seconds - elapsed))
        return remaining if remaining > 0 else None
    
    def reset(self, mcp_name: str):
        """Manually reset circuit breaker."""
        self.states[mcp_name] = self.CLOSED
        self.failure_counts[mcp_name] = 0
        self.half_open_calls[mcp_name] = 0
        logger.info("Circuit breaker manually reset", mcp=mcp_name)


# Global instance
_circuit_breaker = CircuitBreaker()


def get_circuit_breaker() -> CircuitBreaker:
    """Get global circuit breaker instance."""
    return _circuit_breaker
