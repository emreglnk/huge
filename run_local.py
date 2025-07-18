"""
Local development server for the AI Agent Platform.
"""
import uvicorn
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    print("Starting local development server...")
    print("Access the application at http://localhost:8000/")
    print("Access the API documentation at http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
