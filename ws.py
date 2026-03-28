import asyncio
import websockets

# A set to keep track of all active connections
connected_clients = set()

async def handler(websocket):
    # 1. Register the new client
    connected_clients.add(websocket)
    print(f"A client connected! Total clients: {len(connected_clients)}")
    
    try:
        async for message in websocket:
            print(f"Received: {message}. Broadcasting to {len(connected_clients)} clients.")
            
            # 2. Broadcast the message to EVERYONE in the set
            if connected_clients:  # Check if the set is not empty
                # Create a list of send tasks so they run concurrently
                broadcast_message = f"Broadcast from someone: {message}"
                
                # websockets.broadcast is a helper that handles this efficiently
                websockets.broadcast(connected_clients, broadcast_message)
                
    except websockets.exceptions.ConnectionClosed:
        print("Client connection closed.")
    finally:
        # 3. Unregister the client when they disconnect
        connected_clients.remove(websocket)
        print(f"Client removed. Remaining: {len(connected_clients)}")

async def main():
    async with websockets.serve(handler, "localhost", 8765):
        print("WebSocket Broadcast Server started on ws://localhost:8765")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())