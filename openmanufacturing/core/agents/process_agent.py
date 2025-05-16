import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from ..process.workflow_manager import ProcessState, WorkflowManager
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class ProcessAgentState:
    """State maintained by the process agent"""

    active_processes: Dict[str, str] = field(default_factory=dict)  # process_id -> state
    process_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    templates: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class ProcessAgent(BaseAgent):
    """Agent responsible for process workflow management"""

    def __init__(self, workflow_manager: WorkflowManager):
        super().__init__(name="process_agent")
        self.workflow_manager = workflow_manager
        self.state = ProcessAgentState()

    async def start(self):
        """Start the process agent's background tasks"""
        await super().start()
        self.tasks.append(asyncio.create_task(self._monitor_processes()))
        self.tasks.append(asyncio.create_task(self._collect_process_metrics()))
        logger.info("Process agent started")

    async def create_process(
        self,
        template_id: str,
        batch_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new process instance from a template

        Args:
            template_id: ID of the process template to use
            batch_id: Optional batch identifier
            metadata: Optional metadata for the process

        Returns:
            Process ID of the created process
        """
        try:
            process = await self.workflow_manager.create_process_instance(
                template_id=template_id, batch_id=batch_id, metadata=metadata or {}
            )

            self.state.active_processes[process.id] = ProcessState.PENDING.name

            # Initialize metrics tracking for this process
            self.state.process_metrics[process.id] = {
                "template_id": template_id,
                "batch_id": batch_id,
                "created_at": datetime.now().isoformat(),
                "status_history": [
                    {"status": ProcessState.PENDING.name, "timestamp": datetime.now().isoformat()}
                ],
                "duration_ms": 0,
                "steps_completed": 0,
                "steps_total": len(process.steps),
                "error_count": 0,
            }

            logger.info(f"Created process {process.id} from template {template_id}")
            return process.id

        except Exception as e:
            logger.exception(f"Error creating process: {str(e)}")
            raise

    async def start_process(self, process_id: str) -> bool:
        """
        Start execution of a process

        Args:
            process_id: ID of the process to start

        Returns:
            True if the process was started successfully
        """
        try:
            await self.workflow_manager.start_process(process_id)
            self.state.active_processes[process_id] = ProcessState.RUNNING.name

            # Update metrics
            if process_id in self.state.process_metrics:
                self.state.process_metrics[process_id]["status_history"].append(
                    {"status": ProcessState.RUNNING.name, "timestamp": datetime.now().isoformat()}
                )

            logger.info(f"Started process {process_id}")
            return True

        except Exception as e:
            logger.exception(f"Error starting process {process_id}: {str(e)}")
            return False

    async def get_process_status(self, process_id: str) -> Dict[str, Any]:
        """
        Get the current status of a process

        Args:
            process_id: ID of the process

        Returns:
            Dict containing process status information
        """
        try:
            status = await self.workflow_manager.get_process_status(process_id)
            return status

        except Exception as e:
            logger.exception(f"Error getting process status for {process_id}: {str(e)}")
            raise

    async def abort_process(self, process_id: str) -> bool:
        """
        Abort a running process

        Args:
            process_id: ID of the process to abort

        Returns:
            True if the process was aborted successfully
        """
        try:
            await self.workflow_manager.abort_process(process_id)
            self.state.active_processes[process_id] = ProcessState.ABORTED.name

            # Update metrics
            if process_id in self.state.process_metrics:
                self.state.process_metrics[process_id]["status_history"].append(
                    {"status": ProcessState.ABORTED.name, "timestamp": datetime.now().isoformat()}
                )
                self.state.process_metrics[process_id]["aborted_at"] = datetime.now().isoformat()

            logger.info(f"Aborted process {process_id}")
            return True

        except Exception as e:
            logger.exception(f"Error aborting process {process_id}: {str(e)}")
            return False

    async def get_process_metrics(self, process_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for processes

        Args:
            process_id: Optional ID of a specific process to get metrics for

        Returns:
            Dict containing process metrics
        """
        if process_id:
            if process_id not in self.state.process_metrics:
                raise ValueError(f"Process {process_id} not found in metrics")
            return self.state.process_metrics[process_id]

        # Return summary metrics for all processes if no specific ID provided
        summary = {
            "total_processes": len(self.state.process_metrics),
            "active_processes": len(
                [
                    p
                    for p, s in self.state.active_processes.items()
                    if s in [ProcessState.RUNNING.name, ProcessState.PAUSED.name]
                ]
            ),
            "completed_processes": len(
                [
                    p
                    for p, s in self.state.active_processes.items()
                    if s == ProcessState.COMPLETED.name
                ]
            ),
            "failed_processes": len(
                [p for p, s in self.state.active_processes.items() if s == ProcessState.FAILED.name]
            ),
            "avg_duration_ms": 0,
            "success_rate": 0,
        }

        # Calculate average duration and success rate
        completed = [
            m
            for p, m in self.state.process_metrics.items()
            if self.state.active_processes.get(p) == ProcessState.COMPLETED.name
        ]

        if completed:
            summary["avg_duration_ms"] = sum(m["duration_ms"] for m in completed) / len(completed)

            total_finished = len(
                [
                    p
                    for p, s in self.state.active_processes.items()
                    if s in [ProcessState.COMPLETED.name, ProcessState.FAILED.name]
                ]
            )

            if total_finished > 0:
                summary["success_rate"] = (len(completed) / total_finished) * 100

        return summary

    async def _monitor_processes(self):
        """Background task to monitor active processes"""
        while not self.stopping:
            try:
                # Check active processes for status changes
                process_ids = list(self.state.active_processes.keys())
                for process_id in process_ids:
                    try:
                        status = await self.workflow_manager.get_process_status(process_id)
                        current_state = status["state"]

                        # If state has changed, update our tracking
                        if current_state != self.state.active_processes.get(process_id):
                            old_state = self.state.active_processes.get(process_id)
                            self.state.active_processes[process_id] = current_state

                            # Update metrics
                            if process_id in self.state.process_metrics:
                                self.state.process_metrics[process_id]["status_history"].append(
                                    {
                                        "status": current_state,
                                        "timestamp": datetime.now().isoformat(),
                                    }
                                )

                            logger.info(
                                f"Process {process_id} state changed: {old_state} -> {current_state}"
                            )

                            # Handle completed processes
                            if current_state == ProcessState.COMPLETED.name:
                                # Calculate duration
                                if process_id in self.state.process_metrics:
                                    history = self.state.process_metrics[process_id][
                                        "status_history"
                                    ]
                                    start_time = None
                                    for entry in history:
                                        if entry["status"] == ProcessState.RUNNING.name:
                                            start_time = datetime.fromisoformat(entry["timestamp"])
                                            break

                                    if start_time:
                                        end_time = datetime.now()
                                        duration_ms = int(
                                            (end_time - start_time).total_seconds() * 1000
                                        )
                                        self.state.process_metrics[process_id][
                                            "duration_ms"
                                        ] = duration_ms
                                        self.state.process_metrics[process_id][
                                            "completed_at"
                                        ] = end_time.isoformat()

                            # Handle failed processes
                            elif current_state == ProcessState.FAILED.name:
                                if process_id in self.state.process_metrics:
                                    self.state.process_metrics[process_id]["error_count"] += 1
                                    self.state.process_metrics[process_id][
                                        "failed_at"
                                    ] = datetime.now().isoformat()

                            # Update current step
                            if "current_step" in status:
                                self.state.process_metrics[process_id]["current_step"] = status[
                                    "current_step"
                                ]

                            # Example: Update progress (assuming progress is available in status)
                            # if "progress" in status:
                            #    self.state.process_metrics[process_id]["progress"] = status["progress"]

                    except Exception as e:
                        logger.error(f"Error monitoring process {process_id}: {str(e)}")

            except Exception as e:
                logger.exception(f"Error in process monitoring: {str(e)}")

            await asyncio.sleep(2)  # Check every 2 seconds

    async def _collect_process_metrics(self):
        """Background task to collect and update process metrics"""
        while not self.stopping:
            try:
                # For active processes, update steps completed
                active_process_ids = [
                    p
                    for p, s in self.state.active_processes.items()
                    if s == ProcessState.RUNNING.name
                ]

                for process_id in active_process_ids:
                    try:
                        status = await self.workflow_manager.get_process_status(process_id)

                        if process_id in self.state.process_metrics:
                            # Update steps completed
                            if "step_results" in status:
                                completed_steps = sum(
                                    1
                                    for step, result in status["step_results"].items()
                                    if result == "completed"
                                )
                                self.state.process_metrics[process_id][
                                    "steps_completed"
                                ] = completed_steps

                            # Update current step
                            if "current_step" in status:
                                self.state.process_metrics[process_id]["current_step"] = status[
                                    "current_step"
                                ]

                            # Example: Update progress (assuming progress is available in status)
                            # if "progress" in status:
                            #    self.state.process_metrics[process_id]["progress"] = status["progress"]

                    except Exception as e:
                        logger.error(f"Error collecting process metrics for {process_id}: {str(e)}")

            except Exception as e:
                logger.exception(f"Error in process metrics collection: {str(e)}")

            await asyncio.sleep(2)  # Collect metrics every 2 seconds
