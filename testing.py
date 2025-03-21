#!/usr/bin/env python3
"""
kademlia_1min_throughput_test.py

1. Spins up multiple local Kademlia nodes on different ports.
2. Bootstraps them to the first node (node_0).
3. For 1 minute, uses the first node to:
   - Store (set) random key-value pairs.
   - Immediately retrieve (get) the same key (to approximate read throughput).
4. Every second, we record how many sets and gets succeeded.
5. At the end, we plot:
   - Writes per second (over time).
   - Reads per second (over time).
"""

import asyncio
import random
import string
import time

import matplotlib.pyplot as plt
from network import Server

NUM_NODES = 10          # Number of local Kademlia nodes (you can adjust)
BASE_PORT = 8468       # Starting port for the nodes
TEST_DURATION = 60     # Test duration in seconds (1 minute)

def random_string(length=8):
    """Generate a random string of uppercase letters and digits."""
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def create_and_bootstrap_nodes(num_nodes: int, base_port: int):
    """
    Create `num_nodes` Kademlia servers on localhost and bootstrap them
    to the first node (node_0). Return the list of servers.
    """
    servers = []
    for i in range(num_nodes):
        server = Server()
        await server.listen(base_port + i)
        servers.append(server)

    # Bootstrap subsequent servers to the first server
    bootstrap_node = ("127.0.0.1", base_port)
    for i in range(1, num_nodes):
        try:
            await servers[i].bootstrap([bootstrap_node])
        except Exception as e:
            print(f"Bootstrap error for node_{i}: {e}")

    return servers

async def main():
    # 1. Create and bootstrap local nodes
    servers = await create_and_bootstrap_nodes(NUM_NODES, BASE_PORT)
    print(f"{NUM_NODES} local Kademlia nodes created and bootstrapped.\n")

    # We'll use the first node (servers[0]) to do the read/write test
    client = servers[0]

    # 2. Throughput test for 1 minute
    start_time = time.perf_counter()
    last_report_time = start_time

    # Counters
    total_sets = 0
    total_gets = 0

    sets_in_last_sec = 0
    gets_in_last_sec = 0

    sets_per_sec_data = []
    gets_per_sec_data = []
    time_stamps = []

    # We'll loop until 1 minute has passed
    while True:
        current_time = time.perf_counter()
        elapsed = current_time - start_time
        if elapsed >= TEST_DURATION:
            break

        # Generate random key-value
        key = random_string(8)
        value = random_string(12)

        # Attempt to store
        try:
            await client.set(key, value)
            total_sets += 1
            sets_in_last_sec += 1
        except Exception as e:
            print(f"Store error for key={key}: {e}")

        # Attempt to retrieve
        try:
            got_value = await client.get(key)
            if got_value == value:
                total_gets += 1
                gets_in_last_sec += 1
        except Exception as e:
            print(f"Retrieve error for key={key}: {e}")

        # If 1 second has passed since the last report, record throughput
        if current_time - last_report_time >= 1.0:
            time_stamps.append(int(elapsed))
            sets_per_sec_data.append(sets_in_last_sec)
            gets_per_sec_data.append(gets_in_last_sec)

            # Reset counters for the next interval
            sets_in_last_sec = 0
            gets_in_last_sec = 0
            last_report_time = current_time

    # ===== Test summary =====
    print("===== 1-Minute Kademlia Throughput Test =====")
    print(f"Number of nodes:            {NUM_NODES}")
    print(f"Test Duration:              {TEST_DURATION} seconds")
    print(f"Total successful stores:    {total_sets}")
    print(f"Total successful retrieves: {total_gets}")
    print("=============================================\n")

    # Shut down all servers
    for s in servers:
        s.stop()

    # 3. Plot the results (two separate charts)
    # Chart 1: Writes (sets) over time
    plt.figure()
    plt.title("Kademlia Writes per Second (1-minute test)")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Successful writes in the last second")
    plt.plot(time_stamps, sets_per_sec_data)
    plt.savefig('write.pdf')

    # Chart 2: Reads (gets) over time
    plt.figure()
    plt.title("Kademlia Reads per Second (1-minute test)")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Successful reads in the last second")
    plt.plot(time_stamps, gets_per_sec_data)
    plt.savefig('read.pdf')

if __name__ == "__main__":
    for i in range(0, 5):
        asyncio.run(main())
