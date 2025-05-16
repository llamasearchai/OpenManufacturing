import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..alignment.alignment_engine import AlignmentEngine, AlignmentParameters
from ...integrations.ai.openai_client import OpenAIClient
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

@dataclass
class AlignmentState:
    """State maintained by the alignment agent"""
    current_device_id: Optional[str] = None
    alignment_history: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    current_parameters: Optional[AlignmentParameters] = None
    is_aligning: bool = False
    active_requests: Dict[str, Dict[str, Any]] = field(default_factory=dict)

class AlignmentAgent(BaseAgent):
    """Autonomous agent responsible for optical alignment operations"""
    
    def __init__(self, alignment_engine: AlignmentEngine, openai_client: Optional[OpenAIClient] = None):
        super().__init__(name="alignment_agent")
        self.alignment_engine = alignment_engine
        self.openai_client = openai_client
        self.state = AlignmentState()
        
    async def start(self):
        """Start the alignment agent's background tasks"""
        await super().start()
        self.tasks.append(asyncio.create_task(self._monitor_alignment_performance()))
        logger.info("Alignment agent started")
        
    async def align_device(self, 
                          request_id: str, 
                          device_id: str, 
                          parameters: Optional[AlignmentParameters] = None,
                          process_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute an alignment operation for a specific device
        
        Args:
            request_id: Unique ID for this alignment request
            device_id: ID of the device to align
            parameters: Alignment parameters, or None to use defaults
            process_id: Optional ID of a parent process
            metadata: Optional metadata about this alignment
            
        Returns:
            Dict containing alignment results
        """
        if self.state.is_aligning:
            return {
                "success": False,
                "error": "Another alignment operation is already in progress"
            }
            
        # Initialize state for this alignment
        self.state.is_aligning = True
        self.state.current_device_id = device_id
        self.state.current_parameters = parameters or AlignmentParameters()
        
        # Add to active requests
        self.state.active_requests[request_id] = {
            "device_id": device_id,
            "status": "running",
            "process_id": process_id,
            "metadata": metadata or {},
            "start_time": asyncio.get_event_loop().time()
        }
        
        try:
            # If AI optimization is available, get suggestions
            if self.openai_client and device_id in self.state.alignment_history:
                device_history = self.state.alignment_history[device_id]
                if len(device_history) >= 3:  # Only if we have enough history
                    device_type = metadata.get("device_type", "unknown") if metadata else "unknown"
                    ai_params = await self.openai_client.optimize_alignment_parameters(
                        device_history, device_type
                    )
                    if ai_params:
                        # Merge AI suggestions with provided parameters
                        if not parameters:
                            self.state.current_parameters = AlignmentParameters(**ai_params)
                        else:
                            # Update only parameters not explicitly set
                            for param, value in ai_params.items():
                                if param not in parameters.__dict__:
                                    setattr(self.state.current_parameters, param, value)
                            
                        logger.info(f"Using AI-optimized parameters for device {device_id}")
            
            # Execute the alignment
            result = await self.alignment_engine.align()
            
            # Update alignment history
            if device_id not in self.state.alignment_history:
                self.state.alignment_history[device_id] = []
                
            history_entry = {
                "request_id": request_id,
                "timestamp": result.get("timestamp", ""),
                "success": result.get("success", False),
                "optical_power_dbm": result.get("fine_alignment", {}).get("final_power_dbm", 0),
                "parameters": self.state.current_parameters.__dict__,
                "process_id": process_id,
                "duration_ms": int((asyncio.get_event_loop().time() - self.state.active_requests[request_id]["start_time"]) * 1000)
            }
            
            self.state.alignment_history[device_id].append(history_entry)
            
            # Limit history size
            if len(self.state.alignment_history[device_id]) > 100:
                self.state.alignment_history[device_id] = self.state.alignment_history[device_id][-100:]
                
            # Update request status
            self.state.active_requests[request_id]["status"] = "completed" if result.get("success", False) else "failed"
            self.state.active_requests[request_id]["result"] = result
                
            return result
            
        except Exception as e:
            logger.exception(f"Error during alignment: {str(e)}")
            self.state.active_requests[request_id]["status"] = "failed"
            self.state.active_requests[request_id]["error"] = str(e)
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            self.state.is_aligning = False
            
    def get_alignment_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get the result of a specific alignment request"""
        if request_id not in self.state.active_requests:
            return None
            
        request = self.state.active_requests[request_id]
        return {
            "request_id": request_id,
            "device_id": request.get("device_id", ""),
            "status": request.get("status", "unknown"),
            "process_id": request.get("process_id"),
            "result": request.get("result", {}),
            "error": request.get("error")
        }
        
    def get_alignment_history(self, device_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get alignment history for a specific device"""
        if device_id not in self.state.alignment_history:
            return []
            
        return self.state.alignment_history[device_id][-limit:]
        
    def cancel_alignment(self, request_id: str) -> bool:
        """Cancel an ongoing alignment operation"""
        if not self.state.is_aligning or request_id not in self.state.active_requests:
            return False
            
        # Mark as cancelled in the active requests
        self.state.active_requests[request_id]["status"] = "cancelled"
        
        # Attempt to stop the alignment engine
        try:
            # This would need to be implemented in the alignment engine
            self.alignment_engine.stop_alignment()
            self.state.is_aligning = False
            return True
        except Exception as e:
            logger.exception(f"Error cancelling alignment: {str(e)}")
            return False
            
    async def _monitor_alignment_performance(self):
        """Background task to monitor alignment performance and adapt parameters"""
        while not self.stopping:
            await asyncio.sleep(3600)  # Check every hour
            
            try:
                # Analyze alignment success rates for each device type
                device_stats = {}
                
                for device_id, history in self.state.alignment_history.items():
                    if not history:
                        continue
                        
                    # Get device type from metadata if available
                    device_type = history[-1].get("metadata", {}).get("device_type", "unknown")
                    if device_type not in device_stats:
                        device_stats[device_type] = {
                            "total": 0,
                            "success": 0,
                            "avg_duration_ms": 0,
                            "avg_power_dbm": 0
                        }
                    
                    # Calculate statistics
                    for entry in history:
                        device_stats[device_type]["total"] += 1
                        if entry.get("success", False):
                            device_stats[device_type]["success"] += 1
                            device_stats[device_type]["avg_duration_ms"] += entry.get("duration_ms", 0)
                            device_stats[device_type]["avg_power_dbm"] += entry.get("optical_power_dbm", 0)
                
                # Calculate averages and log insights
                for device_type, stats in device_stats.items():
                    if stats["success"] > 0:
                        stats["avg_duration_ms"] /= stats["success"]
                        stats["avg_power_dbm"] /= stats["success"]
                        success_rate = (stats["success"] / stats["total"]) * 100
                        
                        logger.info(f"Device type {device_type} statistics:")
                        logger.info(f"  Success rate: {success_rate:.1f}%")
                        logger.info(f"  Average duration: {stats['avg_duration_ms']:.1f} ms")
                        logger.info(f"  Average optical power: {stats['avg_power_dbm']:.2f} dBm")
                        
                        if success_rate < 80:
                            logger.warning(f"Low success rate for device type {device_type}")
            
            except Exception as e:
                logger.exception(f"Error in alignment performance monitoring: {str(e)}")