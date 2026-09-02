"""
Convenience entry-point — run the TruthHire API without memorising the uvicorn command.

Usage:
    python run.py                     # default: http://127.0.0.1:8000
    python run.py --port 9000         # custom port
    python run.py --host 0.0.0.0      # bind to all interfaces
    python run.py --no-reload         # disable auto-reload (production-like)
"""

import argparse
import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TruthHire Resume Matcher API")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (use for production-like runs)",
    )
    args = parser.parse_args()

    print(f"\n[START]  TruthHire Resume Matcher starting on http://{args.host}:{args.port}")
    print(f"[DOCS]   Swagger UI   -> http://{args.host}:{args.port}/docs")
    print(f"[HEALTH] Health check -> http://{args.host}:{args.port}/health\n")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
