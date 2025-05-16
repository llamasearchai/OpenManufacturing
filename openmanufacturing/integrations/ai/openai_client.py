import logging
import os
import json
from typing import Dict, List, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    Client for interacting with OpenAI APIs

    Used for:
    - Alignment parameter optimization
    - Process anomaly detection
    - Workflow suggestions
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the OpenAI client

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY environment variable)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(timeout=60.0)

        if not self.api_key:
            logger.warning("No OpenAI API key provided, AI features will be disabled")

    async def analyze_alignment_parameters(
        self,
        device_type: str,
        alignment_history: List[Dict[str, Any]],
        current_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze alignment history and suggest optimized parameters

        Args:
            device_type: Type of device being aligned
            alignment_history: List of past alignment results
            current_params: Current alignment parameters

        Returns:
            Dict with suggested parameter improvements
        """
        if not self.api_key:
            logger.warning("Cannot analyze alignment parameters: No OpenAI API key")
            return {}

        try:
            # Format the alignment history for the model
            formatted_history = []
            for item in alignment_history[-10:]:  # Use most recent 10 entries
                formatted_history.append(
                    {
                        "success": item.get("success", False),
                        "optical_power_dbm": item.get("optical_power_dbm", -60),
                        "duration_ms": item.get("duration_ms", 0),
                        "parameters": item.get("parameters", {}),
                    }
                )

            # Create the prompt for the model
            prompt = f"""
            You are an expert in optical alignment systems. Analyze this alignment history for {device_type} devices and suggest parameter improvements.
            
            Current parameters:
            {json.dumps(current_params, indent=2)}
            
            Recent alignment history:
            {json.dumps(formatted_history, indent=2)}
            
            Based on this data, suggest optimized alignment parameters. Consider success rate, optical power, and duration.
            """

            # Make the API call
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an alignment parameter optimization assistant.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )

            response.raise_for_status()
            result = response.json()

            # Extract the suggested parameters from the response
            assistant_message = result["choices"][0]["message"]["content"]

            # For production use, we would implement more robust parsing logic
            # For now, we'll use a simple approach to extract JSON blocks from the response

            # Try to find parameter suggestions in the response
            import re

            json_pattern = r"\s*([\s\S]*?)\s*"
            json_matches = re.findall(json_pattern, assistant_message)

            if json_matches:
                # Parse the first JSON block found
                try:
                    suggested_params = json.loads(json_matches[0])
                    logger.info("Received suggested alignment parameters from AI")
                    return suggested_params
                except json.JSONDecodeError:
                    logger.error("Failed to parse parameters from AI response")

            # If no JSON found or parsing failed, return empty dict
            logger.warning("No parameter suggestions found in AI response")
            return {}

        except Exception as e:
            logger.exception(f"Error in AI parameter analysis: {str(e)}")
            return {}

    async def detect_alignment_anomalies(
        self, device_type: str, current_result: Dict[str, Any], expected_ranges: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect anomalies in alignment results

        Args:
            device_type: Type of device being aligned
            current_result: Current alignment result
            expected_ranges: Expected parameter ranges

        Returns:
            Dict with anomaly analysis and suggestions
        """
        if not self.api_key:
            logger.warning("Cannot detect anomalies: No OpenAI API key")
            return {}

        try:
            # Create the prompt for anomaly detection
            prompt = f"""
            You are an expert in optical alignment anomaly detection. Analyze this alignment result for a {device_type} device.
            
            Expected parameter ranges:
            {json.dumps(expected_ranges, indent=2)}
            
            Current alignment result:
            {json.dumps(current_result, indent=2)}
            
            Identify any anomalies in the alignment result compared to expected ranges.
            For each anomaly, provide:
            1. The parameter name
            2. The observed value
            3. The expected range
            4. Possible causes of the anomaly
            5. Suggested actions to resolve it
            
            Structure your response as JSON with keys: "anomalies" (array of objects) and "summary" (string).
            """

            # Make the API call
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an alignment anomaly detection assistant.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )

            response.raise_for_status()
            result = response.json()

            # Parse the response content as JSON
            try:
                assistant_message = result["choices"][0]["message"]["content"]
                anomaly_data = json.loads(assistant_message)
                logger.info("Received anomaly analysis from AI")
                return anomaly_data
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse anomaly data from AI response: {str(e)}")
                return {}

        except Exception as e:
            logger.exception(f"Error in AI anomaly detection: {str(e)}")
            return {}

    async def suggest_workflow_optimization(
        self, workflow_template: Dict[str, Any], execution_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Suggest optimizations for a workflow based on execution statistics

        Args:
            workflow_template: The current workflow template
            execution_stats: Statistics from past workflow executions

        Returns:
            Dict with workflow optimization suggestions
        """
        if not self.api_key:
            logger.warning("Cannot suggest workflow optimizations: No OpenAI API key")
            return {}

        try:
            # Create the prompt for workflow optimization
            prompt = f"""
            You are an expert in manufacturing process optimization. Analyze this workflow and its execution statistics.
            
            Workflow template:
            {json.dumps(workflow_template, indent=2)}
            
            Execution statistics:
            {json.dumps(execution_stats, indent=2)}
            
            Suggest optimizations to improve:
            1. Overall process efficiency
            2. Success rate
            3. Throughput
            4. Resource utilization
            
            Consider step sequencing, parallel execution opportunities, and dependency optimization.
            Structure your response as JSON with keys: "optimizations" (array of objects) and "summary" (string).
            """

            # Make the API call
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a manufacturing workflow optimization assistant.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )

            response.raise_for_status()
            result = response.json()

            # Parse the response content as JSON
            try:
                assistant_message = result["choices"][0]["message"]["content"]
                optimization_data = json.loads(assistant_message)
                logger.info("Received workflow optimization suggestions from AI")
                return optimization_data
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse optimization data from AI response: {str(e)}")
                return {}

        except Exception as e:
            logger.exception(f"Error in AI workflow optimization: {str(e)}")
            return {}
