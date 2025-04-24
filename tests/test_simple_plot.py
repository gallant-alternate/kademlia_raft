import asyncio
import random
import time
import matplotlib.pyplot as plt
from network import Server

async def main():
    NUM_NODES = 20
    BASE_PORT = 9000
    servers = []
    for i in range(NUM_NODES):
        s = Server()
        await s.listen(BASE_PORT + i)
        servers.append(s)
    for i in range(1, NUM_NODES):
        await servers[i].bootstrap([("127.0.0.1", BASE_PORT)])
    client = servers[0]
    latencies = []
    for i in range(500):
        key = f"key{i}"
        value = f"val{i}"
        start = time.perf_counter()
        await client.set(key, value)
        await client.get(key)
        latencies.append(time.perf_counter() - start)
    for s in servers:
        s.stop()
    plt.hist(latencies, bins=20)
    plt.title(f"Kademlia Set+Get Latency Distribution\nNodes: {NUM_NODES}, Operations: {len(latencies)}")
    plt.xlabel("Latency (seconds)")
    plt.ylabel("Frequency")
    # Add text box with node and operation info
    plt.text(0.95, 0.95, f"Nodes: {NUM_NODES}\nOps: {len(latencies)}", 
             ha='right', va='top', transform=plt.gca().transAxes, 
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray'))
    plt.savefig("simple_latency_plot.png")
    print("Test complete. Plot saved as simple_latency_plot.png.")

if __name__ == "__main__":
    asyncio.run(main())
