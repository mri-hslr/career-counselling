import asyncio
import websockets

async def communicate():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Sending data
        message = "Hello from your Career Compass app!"
        await websocket.send(message)
        print(f"Sent: {message}")

        # Receiving data
        greeting = await websocket.recv()
        print(f"Received: {greeting}")

if __name__ == "__main__":
    asyncio.run(communicate())