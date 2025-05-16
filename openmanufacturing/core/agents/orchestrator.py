import asyncio
import logging
from typing import Dict, List, Optional

from ...integrations.ai.openai_client import OpenAIClient
from ..alignment.alignment_engine import AlignmentEngine
from ..process.workflow_manager import WorkflowManager
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrator that manages all agents in the system

    The orchestrator is responsible for:
    - Creating and initializing agents
    - Starting and stopping agents
    - Facilitating communication between agents
    - Monitoring agent health
    """

    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        self.agents: Dict[str, BaseAgent] = {}
        self.openai_client = openai_client
        self.stopping = False
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Initialize and start all agents"""
        logger.info("Starting agent orchestrator")

        # Import agent classes dynamically to avoid circular imports
        from .alignment_agent import AlignmentAgent
        from .process_agent import ProcessAgent

        # Create and initialize workflow manager
        workflow_manager = WorkflowManager()

        # Create the process agent
        process_agent = ProcessAgent(workflow_manager)
        self.agents[process_agent.name] = process_agent

        # Create alignment engine and agent
        # Note: In a real implementation, we would initialize hardware connections here
        calibration_profile = self._create_calibration_profile()
        motion_controller = self._create_motion_controller()

        alignment_engine = AlignmentEngine(
            motion_controller=motion_controller, calibration_profile=calibration_profile
        )

        alignment_agent = AlignmentAgent(
            alignment_engine=alignment_engine, openai_client=self.openai_client
        )
        self.agents[alignment_agent.name] = alignment_agent

        # Start all agents
        for name, agent in self.agents.items():
            logger.info(f"Starting agent: {name}")
            await agent.start()

        # Start agent health monitoring
        self.tasks.append(asyncio.create_task(self._monitor_agent_health()))

        logger.info(f"Started {len(self.agents)} agents")

    async def stop(self):
        """Stop all agents and clean up resources"""
        logger.info("Stopping agent orchestrator")
        self.stopping = True

        # Cancel our own tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Stop all agents
        for name, agent in self.agents.items():
            logger.info(f"Stopping agent: {name}")
            await agent.stop()

        logger.info("All agents stopped")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name"""
        return self.agents.get(name)

    def register_agent(self, agent: BaseAgent) -> bool:
        """Register a new agent with the orchestrator"""
        if agent.name in self.agents:
            logger.warning(f"Agent with name {agent.name} already exists")
            return False

        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")
        return True

    async def _monitor_agent_health(self):
        """Background task to monitor agent health"""
        while not self.stopping:
            try:
                for name, agent in self.agents.items():
                    # Check if agent is responding
                    if not agent.is_healthy():
                        logger.warning(f"Agent {name} appears to be unhealthy")

                        # In a production system, we might implement recovery logic here
                        # For now, just log the issue

            except Exception as e:
                logger.exception(f"Error in agent health monitoring: {str(e)}")

            await asyncio.sleep(10)  # Check every 10 seconds

    def _create_calibration_profile(self):
        """Create a calibration profile for the alignment engine"""
        # In a real implementation, this would load calibration data from storage
        # For now, create a mock calibration profile
        from ..process.calibration import CalibrationProfile

        return CalibrationProfile()

    def _create_motion_controller(self):
        """Create and initialize the motion controller"""
        # In a real implementation, this would connect to actual hardware
        # For now, create a mock motion controller
        from ..hardware.motion_controller import MotionController

        return MotionController(simulation_mode=True)
