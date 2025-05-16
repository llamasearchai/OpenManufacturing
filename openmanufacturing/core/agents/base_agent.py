import asyncio
import logging
import time
from typing import List, Dict, Any
import uuid

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all agents in the system

    Provides common functionality and interface for specific agent implementations.
    """

    def __init__(self, name: str):
        """
        Initialize the agent

        Args:
            name: Unique name for this agent
        """
        self.name = name
        self.id = str(uuid.uuid4())
        self.tasks: List[asyncio.Task] = []
        self.stopping = False
        self.start_time = 0
        self.last_heartbeat = 0
        self.status = "initialized"
        self.metrics: Dict[str, Any] = {}

    async def start(self):
        """
        Start the agent's background tasks

        This method should be extended by subclasses to start their specific tasks.
        """
        self.stopping = False
        self.start_time = time.time()
        self.last_heartbeat = time.time()
        self.status = "running"

        # Start heartbeat task
        self.tasks.append(asyncio.create_task(self._heartbeat()))

        logger.info(f"Agent {self.name} started")

    async def stop(self):
        """
        Stop the agent and clean up resources
        """
        logger.info(f"Stopping agent {self.name}")
        self.stopping = True

        # Cancel all background tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete cancellation
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.status = "stopped"
        logger.info(f"Agent {self.name} stopped")

    def is_healthy(self) -> bool:
        """
        Check if the agent is healthy

        Returns:
            True if the agent is running and responsive
        """
        # Simple health check: ensure we've had a heartbeat in the last 30 seconds
        return (time.time() - self.last_heartbeat) < 30

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the agent

        Returns:
            Dict containing status information
        """
        uptime = time.time() - self.start_time if self.start_time > 0 else 0
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "uptime_seconds": uptime,
            "last_heartbeat": self.last_heartbeat,
            "metrics": self.metrics,
        }

    async def _heartbeat(self):
        """
        Background task to update the agent's heartbeat
        """
        while not self.stopping:
            self.last_heartbeat = time.time()

            # Update basic metrics
            self.metrics["uptime_seconds"] = time.time() - self.start_time
            self.metrics["task_count"] = len(self.tasks)

            await asyncio.sleep(5)  # Heartbeat every 5 seconds
