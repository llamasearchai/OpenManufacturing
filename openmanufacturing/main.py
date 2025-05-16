import asyncio
import logging
import os
import argparse
import uvicorn
import signal
import sys
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

# Flag for graceful shutdown
shutdown_event = asyncio.Event()


async def shutdown(signal=None):
    """Perform graceful shutdown"""
    if signal:
        logger.info(f"Received exit signal {signal.name}...")

    logger.info("Shutting down...")

    # Set shutdown event
    shutdown_event.set()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signals = (signal.SIGINT, signal.SIGTERM) if sys.platform != "win32" else (signal.SIGINT,)

    for s in signals:
        asyncio.get_event_loop().add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration file

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    import json

    if not os.path.exists(config_path):
        logger.warning(f"Configuration file {config_path} not found. Using defaults.")
        return {}

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        return {}


async def initialize_services(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initialize all services

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary of initialized services
    """
    from openmanufacturing.core.hardware.motion_controller import MotionController
    from openmanufacturing.core.vision.image_processing import ImageProcessor
    from openmanufacturing.core.process.calibration import CalibrationProfile
    from openmanufacturing.core.alignment.service import AlignmentService
    from openmanufacturing.core.process.workflow_manager import WorkflowManager
    from openmanufacturing.core.database.db import init_db

    services = {}

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Initialize motion controller
        controller_config = config.get("motion_controller", {})
        motion_controller = MotionController(
            controller_type=controller_config.get("type", "simulated"),
            port=controller_config.get("port", "/dev/ttyUSB0"),
            simulation_mode=controller_config.get("simulation_mode", True),
        )
        await motion_controller.initialize()
        services["motion_controller"] = motion_controller

        # Initialize image processor
        vision_config = config.get("vision", {})
        image_processor = ImageProcessor(
            camera_id=vision_config.get("camera_id", "default"),
            config_path=vision_config.get("config_path", "config/vision.json"),
            simulation_mode=vision_config.get("simulation_mode", True),
        )
        services["image_processor"] = image_processor

        # Load or create calibration profile
        calibration_path = config.get("calibration_path", "config/calibration.json")
        calibration_profile = CalibrationProfile.load_from_file(calibration_path)

        if calibration_profile is None:
            calibration_profile = CalibrationProfile()
            # Optionally save default profile
            calibration_profile.save_to_file(calibration_path)

        services["calibration_profile"] = calibration_profile

        # Initialize alignment service
        alignment_service = AlignmentService(
            motion_controller=motion_controller,
            image_processor=image_processor,
            calibration_profile=calibration_profile,
        )
        services["alignment_service"] = alignment_service

        # Initialize workflow manager
        workflow_manager = WorkflowManager()
        services["workflow_manager"] = workflow_manager

        # Register components with workflow manager
        workflow_manager.register_component("alignment", alignment_service)

        logger.info("All services initialized successfully")
        return services

    except Exception as e:
        logger.error(f"Error initializing services: {str(e)}")
        # Clean up any services that were initialized
        for name, service in services.items():
            if hasattr(service, "close") and callable(service.close):
                try:
                    if asyncio.iscoroutinefunction(service.close):
                        await service.close()
                    else:
                        service.close()
                except Exception as cleanup_error:
                    logger.error(f"Error closing {name}: {str(cleanup_error)}")

        raise


async def cleanup_services(services: Dict[str, Any]):
    """
    Clean up all services

    Args:
        services: Dictionary of services to clean up
    """
    for name, service in services.items():
        logger.info(f"Closing {name}...")
        try:
            if hasattr(service, "close") and callable(service.close):
                if asyncio.iscoroutinefunction(service.close):
                    await service.close()
                else:
                    service.close()
        except Exception as e:
            logger.error(f"Error closing {name}: {str(e)}")


async def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """
    Start API server

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    from openmanufacturing.api.main import app

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    # Start server in background
    api_task = asyncio.create_task(server.serve())

    # Wait for shutdown signal
    await shutdown_event.wait()

    logger.info("Stopping API server...")
    server.should_exit = True
    await api_task


async def main_async():
    """Main async function"""
    parser = argparse.ArgumentParser(description="OpenManufacturing Platform")
    parser.add_argument(
        "--config", "-c", default="config/config.json", help="Path to configuration file"
    )
    parser.add_argument("--host", "-H", default="0.0.0.0", help="API server host")
    parser.add_argument("--port", "-p", type=int, default=8000, help="API server port")
    args = parser.parse_args()

    # Setup signal handlers
    setup_signal_handlers()

    logger.info("Starting OpenManufacturing Platform")

    # Load configuration
    config = load_config(args.config)

    # Initialize services
    try:
        services = await initialize_services(config)

        # Start API server
        await start_api_server(host=args.host, port=args.port)

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return 1
    finally:
        # Clean up
        try:
            if "services" in locals():
                await cleanup_services(services)
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    logger.info("Shutdown complete")
    return 0


def main():
    """Main entry point"""
    try:
        exit_code = asyncio.run(main_async())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
