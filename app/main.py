from fastapi import FastAPI
import pymongo
import os

app = FastAPI()

# Get MongoDB connection string from environment variables
mongodb_uri = os.getenv("MONGODB_URI", "mongodb://db:27017/")
client = pymongo.MongoClient(mongodb_uri)
db = client.get_database() # The database name is specified in the URI

@app.get("/")
def read_root():
    return {"message": "AI Agent Platform is running."}

@app.get("/agents")
def get_agents():
    # A simple endpoint to test MongoDB connection based on the roadmap
    # In docker-compose, the db name is not specified, so we list databases.
    # A real implementation would use a specific database.
    try:
        # The 'list_database_names' command is a good way to check the connection
        # and see what databases are available.
        database_names = client.list_database_names()
        return {"databases": database_names}
    except Exception as e:
        return {"error": str(e)}
