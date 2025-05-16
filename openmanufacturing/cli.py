import argparse
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="OpenManufacturing Platform CLI")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (for development)")
    
    args = parser.parse_args()

    print(f"Starting OpenManufacturing server on {args.host}:{args.port}")
    if args.reload:
        print("Auto-reload enabled.")

    uvicorn.run(
        "openmanufacturing.api.main:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload,
        # workers=4 # Consider adding for production, but not with reload
    )

if __name__ == "__main__":
    main() 