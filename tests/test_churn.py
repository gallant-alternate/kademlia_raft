import asyncio
import random
import time
import matplotlib.pyplot as plt
from network import Server

async def main():
    NUM_NODES = 5
    BASE_PORT = 9200
    servers = []
    for i in range(NUM_NODES):
        s = Server()
        await s.listen(BASE_PORT + i)
        servers.append(s)
    for i in range(1, NUM_NODES):
        await servers[i].bootstrap([("127.0.0.1", BASE_PORT)])
    client = servers[0]
    churn_scores = []
    keys = [f"churnkey{i}" for i in range(10)]
    values = [f"churnval{i}" for i in range(10)]
    # Initial set
    for key, value in zip(keys, values):
        await client.set(key, value)
    for round in range(50):
        # Randomly stop and restart some nodes to simulate churn
        churn_out = random.sample(range(1, NUM_NODES), k=NUM_NODES // 2)
        for idx in churn_out:
            servers[idx].stop()
        await asyncio.sleep(0.2)
        for idx in churn_out:
            s = Server()
            await s.listen(BASE_PORT + idx)
            await s.bootstrap([("127.0.0.1", BASE_PORT)])
            servers[idx] = s
        # Check consistency after churn
        key = random.choice(keys)
        value = await client.get(key)
        values = [await s.get(key) for s in servers]
        score = sum(1 for v in values if v == value) / len(servers)
        churn_scores.append(score)
    for s in servers:
        s.stop()
    plt.figure(figsize=(10, 6))
    plt.plot(churn_scores, marker='o', linestyle='-', color='royalblue')
    plt.title(f"Kademlia Churn Resilience Test\nNodes: {NUM_NODES}, Rounds: {len(churn_scores)}")
    plt.ylabel("Consistency Score (fraction of nodes correct)")
    plt.xlabel("Churn Round")
    plt.ylim(0, 1.05)
    plt.savefig("new_test_plots/churn_resilience.png")
    print("Churn test complete. Plot saved as test_plots/churn_resilience.png.")

if __name__ == "__main__":
    asyncio.run(main())
