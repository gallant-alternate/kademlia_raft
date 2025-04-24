import asyncio
import random
import time
import matplotlib.pyplot as plt
from network import Server

async def main():
    NUM_NODES = 50
    BASE_PORT = 9100
    servers = []
    for i in range(NUM_NODES):
        s = Server()
        await s.listen(BASE_PORT + i)
        servers.append(s)
    for i in range(1, NUM_NODES):
        await servers[i].bootstrap([("127.0.0.1", BASE_PORT)])
    client = servers[0]
    set_scores = []
    update_scores = []
    delete_scores = []
    for i in range(500):
        key = f"conskey{i}"
        value = f"consval{i}"
        # SET
        await client.set(key, value)
        values = [await s.get(key) for s in servers]
        set_score = sum(1 for v in values if v == value) / len(servers)
        set_scores.append(set_score)
        # UPDATE
        new_value = f"consval{i}_updated"
        await client.set(key, new_value)
        updated_values = [await s.get(key) for s in servers]
        update_score = sum(1 for v in updated_values if v == new_value) / len(servers)
        update_scores.append(update_score)
        # DELETE (simulate by setting value to a special marker)
        delete_marker = "__DELETED__"
        await client.set(key, delete_marker)
        deleted_values = [await s.get(key) for s in servers]
        delete_score = sum(1 for v in deleted_values if v == delete_marker) / len(servers)
        delete_scores.append(delete_score)
    for s in servers:
        s.stop()
    plt.figure(figsize=(10, 6))
    plt.boxplot([set_scores, update_scores, delete_scores],
                labels=["Set", "Update", "Delete"],
                patch_artist=True,
                boxprops=dict(facecolor='skyblue', color='royalblue'),
                medianprops=dict(color='crimson', linewidth=2),
                whiskerprops=dict(color='gray'),
                capprops=dict(color='gray'),
                flierprops=dict(markerfacecolor='orange', marker='o', markersize=5, alpha=0.5))
    plt.title(f"Kademlia Consistency Score Distribution\nNodes: {NUM_NODES}, Operations: {len(set_scores)}")
    plt.ylabel("Consistency Score (fraction of nodes correct)")
    plt.xlabel("Operation Type")
    plt.text(2.8, 1.02, f"Nodes: {NUM_NODES}\nOps: {len(set_scores)}", 
             ha='right', va='top', transform=plt.gca().transAxes, 
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray'))
    plt.ylim(0, 1.05)
    plt.savefig("consistency_scores.png")
    print("Consistency test complete. Plot saved as consistency_scores.png.")

if __name__ == "__main__":
    asyncio.run(main())
