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

class ChurnSimulator:
    def __init__(self, base_port=8468, initial_nodes=10):
        self.base_port = base_port
        self.initial_nodes = initial_nodes
        self.active_nodes = []
        self.failed_nodes = []
        self.next_port = base_port + initial_nodes

    async def setup_initial_network(self):
        """Setup initial network with specified number of nodes"""
        self.active_nodes = await create_and_bootstrap_nodes(self.initial_nodes, self.base_port)
        return self.active_nodes[0]  # Return first node as primary contact

    async def simulate_node_failure(self, fail_percentage=0.2):
        """Simulate sudden failure of nodes"""
        num_to_fail = int(len(self.active_nodes) * fail_percentage)
        for _ in range(num_to_fail):
            if self.active_nodes:
                node = random.choice(self.active_nodes)
                self.active_nodes.remove(node)
                self.failed_nodes.append(node)
                node.stop()
                print(f"Node failed. Active nodes: {len(self.active_nodes)}")

    async def add_new_node(self):
        """Add a new node to the network"""
        if not self.active_nodes:
            return None
            
        bootstrap_node = ("127.0.0.1", self.base_port)
        new_node = Server()
        await new_node.listen(self.next_port)
        await new_node.bootstrap([bootstrap_node])
        
        self.active_nodes.append(new_node)
        self.next_port += 1
        print(f"New node added. Active nodes: {len(self.active_nodes)}")
        return new_node

    def get_active_node_count(self):
        return len(self.active_nodes)

async def test_network_churn():
    """Test network resilience under churn conditions"""
    churn = ChurnSimulator()
    primary_node = await churn.setup_initial_network()
    
    test_data = {}
    successful_ops = 0
    failed_ops = 0
    
    # Test duration and intervals
    test_duration = 300  # 5 minutes
    churn_interval = 30  # Simulate churn every 30 seconds
    operation_interval = 1  # Perform operations every second
    
    start_time = time.monotonic()
    last_churn_time = start_time
    
    while time.monotonic() - start_time < test_duration:
        current_time = time.monotonic()
        
        # Simulate network churn periodically
        if current_time - last_churn_time >= churn_interval:
            await churn.simulate_node_failure(0.2)  # 20% node failure
            for _ in range(2):  # Add some new nodes
                await churn.add_new_node()
            last_churn_time = current_time
            
        # Perform operations
        try:
            key = random_string(8)
            value = random_string(12)
            
            # Try to store value
            store_success = await primary_node.set(key, value)
            if store_success:
                test_data[key] = value
                successful_ops += 1
            else:
                failed_ops += 1
                
            # Try to retrieve a random existing value
            if test_data:
                test_key = random.choice(list(test_data.keys()))
                retrieved = await primary_node.get(test_key)
                if retrieved == test_data[test_key]:
                    successful_ops += 1
                else:
                    failed_ops += 1
                    
        except Exception as e:
            failed_ops += 1
            print(f"Operation failed: {str(e)}")
            
        await asyncio.sleep(operation_interval)
    
    # Calculate and display results
    total_ops = successful_ops + failed_ops
    success_rate = (successful_ops / total_ops) * 100 if total_ops > 0 else 0
    
    print("\n===== Churn Test Results =====")
    print(f"Test Duration: {test_duration} seconds")
    print(f"Initial Nodes: {churn.initial_nodes}")
    print(f"Final Active Nodes: {churn.get_active_node_count()}")
    print(f"Total Operations: {total_ops}")
    print(f"Successful Operations: {successful_ops}")
    print(f"Failed Operations: {failed_ops}")
    print(f"Success Rate: {success_rate:.2f}%")
    print("============================")

if __name__ == "__main__":
    # Run both standard throughput test and churn test
    asyncio.run(main())  # Original throughput test
    print("\nStarting Churn Test...")
    asyncio.run(test_network_churn())  # New churn test
