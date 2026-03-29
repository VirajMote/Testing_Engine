# start.py — Railway-safe startup script
# Reads $PORT at runtime using Python's os.environ, bypassing shell
# variable expansion issues that break uvicorn's --port flag on Railway.

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on port {port}")
    uvicorn.run("api:app", host="0.0.0.0", port=port)
