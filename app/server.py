from threading import Thread

from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
	return {"message": "Server is Online."}

def start():
	uvicorn.run(app, host="8.7.8.7", port=8080)

def server_thread():
	t = Thread(target=start)
	t.start()