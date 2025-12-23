import asyncio
import logging
import time

from typing import Optional, Any, Tuple
from redis.asyncio import Redis
from redis.exceptions import LockNotOwnedError

from db.redis_database import REDIS_ASYNC_CLIENT

scheduler_lock_key = "mediafusion_scheduler_lock"
heartbeat_key = "mediafusion_scheduler_heartbeat"
heartbeat_timeout = 300  # 5 minutes


async def acquire_scheduler_lock() -> Tuple[bool, Optional[Any]]:
    """
    Acquire scheduler lock with heartbeat check.
    
    Checks if current scheduler is active via heartbeat before attempting lock.
    Sets heartbeat timestamp on successful acquisition.
    
    Returns:
        Tuple of (acquired: bool, lock: Optional[RedisLock])
        - acquired: True if lock was acquired, False otherwise
        - lock: Redis lock object if acquired, None otherwise
    """
    current_time = int(time.time())
    # Check if the current scheduler is active
    last_heartbeat = await REDIS_ASYNC_CLIENT.get(heartbeat_key)
    if last_heartbeat and (current_time - int(last_heartbeat) <= heartbeat_timeout):
        logging.info("Scheduler is still active, not acquiring lock")
        return False, None  # Scheduler is still active, do not acquire lock

    # Attempt to acquire the lock
    acquired, lock = await acquire_redis_lock(
        scheduler_lock_key, timeout=heartbeat_timeout, block=False
    )
    if acquired:
        logging.info("Acquired scheduler lock")
        await REDIS_ASYNC_CLIENT.set(heartbeat_key, current_time)
        return True, lock
    logging.info("Failed to acquire scheduler lock")
    return False, None


async def release_scheduler_lock(lock: Any) -> None:
    """
    Release scheduler lock and clear heartbeat.
    
    Args:
        lock: Redis lock object to release
    """
    logging.info("Releasing scheduler lock")
    await release_redis_lock(lock)
    await REDIS_ASYNC_CLIENT.delete(heartbeat_key)


async def maintain_heartbeat() -> None:
    """
    Maintain scheduler heartbeat to indicate active status.
    
    Updates heartbeat timestamp every half timeout period.
    Runs indefinitely until cancelled.
    """
    while True:
        await asyncio.sleep(heartbeat_timeout // 2)
        await REDIS_ASYNC_CLIENT.set(heartbeat_key, int(time.time()))


async def acquire_redis_lock(key: str, timeout: int = 60, block: bool = False) -> Tuple[bool, Any]:
    """
    Acquire a Redis distributed lock.
    
    Args:
        key: Lock key identifier
        timeout: Lock timeout in seconds (default: 60)
        block: If True, block until lock is acquired. If False, return immediately.
        
    Returns:
        Tuple of (acquired: bool, lock: RedisLock)
        - acquired: True if lock was acquired, False otherwise
        - lock: Redis lock object (even if not acquired)
    """
    lock = REDIS_ASYNC_CLIENT.lock(key, timeout=timeout)
    acquired = await lock.acquire(blocking=block)
    return acquired, lock


async def release_redis_lock(lock):
    try:
        await lock.release()
    except LockNotOwnedError:
        logging.error("Failed to release lock, lock not owned")
        pass
