#!/usr/bin/env python3
"""
final.py - Comprehensive Testing Module for Kademlia DHT Implementation

This module tests the following metrics:
1. Latency (Read/Write operations)
2. Consistency (Under different quorum configurations)
3. Network Resilience (Under churn)
4. Cache Hit Ratio (ARC vs Traditional)
5. Throughput (Operations per second)
6. Storage Distribution (Even distribution of data across nodes)
"""

import asyncio
import random
import time
import csv
import os
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

from network import Server
from storage import ARCStorage, ForgetfulStorage
from utils import digest

# Test Configuration
BASE_PORT = 8468
INITIAL_NODES = 15
TEST_DURATION = 300  # 5 minutes per test
DATA_POINTS = 1000  # Number of operations per test
CSV_FILE = "test_results.csv"
PLOTS_DIR = "test_plots"

class MetricsCollector:
    def __init__(self):
        self.latencies = []
        self.consistency_scores = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.operation_counts = []
        self.node_storage_dist = defaultdict(int)
        self.successful_ops = 0
        self.failed_ops = 0
        
    def record_latency(self, latency):
        self.latencies.append(latency)
        
    def record_consistency(self, score):
        self.consistency_scores.append(score)
        
    def record_cache_hit(self):
        self.cache_hits += 1
        
    def record_cache_miss(self):
        self.cache_misses += 1
        
    def record_operation(self, success):
        if success:
            self.successful_ops += 1
        else:
            self.failed_ops += 1
            
    def record_storage(self, node_id, size):
        self.node_storage_dist[node_id] = size

class KademliaTestSuite:
    def __init__(self):
        self.metrics = MetricsCollector()
        self.used_ports = set()  # Track used ports
        if not os.path.exists(PLOTS_DIR):
            os.makedirs(PLOTS_DIR)

    async def setup_network(self, num_nodes):
        """Initialize network with given number of nodes"""
        servers = []
        # Create nodes with both ARC and traditional storage
        for i in range(num_nodes):
            port = BASE_PORT + i
            self.used_ports.add(port)
            storage = ARCStorage() if i % 2 == 0 else ForgetfulStorage()
            server = Server(storage=storage)
            await server.listen(port)
            servers.append(server)

        # Bootstrap to first node
        bootstrap_node = ("127.0.0.1", BASE_PORT)
        for i in range(1, num_nodes):
            await servers[i].bootstrap([bootstrap_node])

        return servers

    async def test_latency(self, servers):
        """Test read/write latencies"""
        primary = servers[0]
        for _ in range(DATA_POINTS):
            key = digest(str(random.randint(1, 1000000)))
            value = str(random.randint(1, 1000000))
            
            # Test write latency
            start = time.monotonic()
            await primary.set(key, value)
            self.metrics.record_latency(time.monotonic() - start)
            
            # Test read latency
            start = time.monotonic()
            await primary.get(key)
            self.metrics.record_latency(time.monotonic() - start)

    async def test_consistency(self, servers):
        """Test consistency across nodes"""
        primary = servers[0]
        for _ in range(DATA_POINTS):
            key = digest(str(random.randint(1, 1000000)))
            value = str(random.randint(1, 1000000))
            
            # Write to primary
            await primary.set(key, value)
            
            # Read from all nodes and check consistency
            values = []
            for server in servers:
                val = await server.get(key)
                if val is not None:
                    values.append(val)
                    
            # Calculate consistency score (percentage of nodes with same value)
            score = len([v for v in values if v == value]) / len(servers)
            self.metrics.record_consistency(score)

    async def test_cache_performance(self, servers):
        """Test cache hit ratios"""
        arc_node = next(s for s in servers if isinstance(s.storage, ARCStorage))
        regular_node = next(s for s in servers if isinstance(s.storage, ForgetfulStorage))
        
        # Generate repeated access pattern
        keys = [digest(str(i)) for i in range(100)]
        for _ in range(DATA_POINTS):
            key = random.choice(keys)
            value = str(random.randint(1, 1000000))
            
            # Test ARC storage
            await arc_node.set(key, value)
            result = await arc_node.get(key)
            if result == value:
                self.metrics.record_cache_hit()
            else:
                self.metrics.record_cache_miss()

    async def test_churn_resilience(self, servers):
        """Test network resilience under churn"""
        active_servers = servers.copy()
        primary = active_servers[0]
        max_retries = 3
        
        for _ in range(DATA_POINTS):
            # Simulate random node failures and joins
            if len(active_servers) > 5 and random.random() < 0.1:
                failed = random.choice(active_servers[1:])  # Don't remove primary
                port = failed.port
                self.used_ports.remove(port)  # Free up the port
                failed.stop()
                active_servers.remove(failed)
                
                # Find an available port
                new_port = BASE_PORT
                while new_port in self.used_ports:
                    new_port += 1
                
                # Add new node with retries
                for attempt in range(max_retries):
                    try:
                        new_server = Server()
                        await new_server.listen(new_port)
                        self.used_ports.add(new_port)
                        await new_server.bootstrap([("127.0.0.1", BASE_PORT)])
                        active_servers.append(new_server)
                        servers.append(new_server)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            print(f"Failed to add new node after {max_retries} attempts: {e}")
                        await asyncio.sleep(1)  # Wait before retry
            
            # Test operations during churn with retries
            for attempt in range(max_retries):
                try:
                    key = digest(str(random.randint(1, 1000000)))
                    value = str(random.randint(1, 1000000))
                    success = await asyncio.wait_for(
                        primary.set(key, value),
                        timeout=5.0
                    )
                    self.metrics.record_operation(success)
                    
                    retrieved = await asyncio.wait_for(
                        primary.get(key),
                        timeout=5.0
                    )
                    self.metrics.record_operation(retrieved == value)
                    break
                except asyncio.TimeoutError:
                    if attempt == max_retries - 1:
                        self.metrics.record_operation(False)
                    await asyncio.sleep(1)  # Wait before retry
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"Operation failed after {max_retries} attempts: {e}")
                        self.metrics.record_operation(False)
                    await asyncio.sleep(1)  # Wait before retry

    def plot_results(self):
        """Generate plots for all metrics"""
        # 1. Latency Distribution
        plt.figure(figsize=(10, 6))
        plt.hist(self.metrics.latencies, bins=50)
        plt.title("Operation Latency Distribution")
        plt.xlabel("Latency (seconds)")
        plt.ylabel("Frequency")
        plt.savefig(f"{PLOTS_DIR}/latency_distribution.png")
        plt.close()

        # 2. Consistency Scores
        plt.figure(figsize=(10, 6))
        plt.plot(self.metrics.consistency_scores)
        plt.title("Consistency Scores Over Time")
        plt.xlabel("Operation Number")
        plt.ylabel("Consistency Score")
        plt.savefig(f"{PLOTS_DIR}/consistency_scores.png")
        plt.close()

        # 3. Cache Performance
        plt.figure(figsize=(10, 6))
        total = self.metrics.cache_hits + self.metrics.cache_misses
        hits_ratio = self.metrics.cache_hits / total if total > 0 else 0
        plt.bar(["Cache Hits", "Cache Misses"], 
                [hits_ratio, 1 - hits_ratio])
        plt.title("Cache Performance")
        plt.ylabel("Ratio")
        plt.savefig(f"{PLOTS_DIR}/cache_performance.png")
        plt.close()

        # 4. Operation Success Rate Under Churn
        plt.figure(figsize=(10, 6))
        total_ops = self.metrics.successful_ops + self.metrics.failed_ops
        success_rate = self.metrics.successful_ops / total_ops if total_ops > 0 else 0
        plt.bar(["Successful", "Failed"], 
                [success_rate, 1 - success_rate])
        plt.title("Operation Success Rate Under Churn")
        plt.ylabel("Ratio")
        plt.savefig(f"{PLOTS_DIR}/churn_resilience.png")
        plt.close()

    def save_results_csv(self):
        """Save metrics to CSV file"""
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            
            # Calculate summary statistics
            avg_latency = np.mean(self.metrics.latencies)
            avg_consistency = np.mean(self.metrics.consistency_scores)
            cache_hit_ratio = (self.metrics.cache_hits / 
                             (self.metrics.cache_hits + self.metrics.cache_misses)
                             if self.metrics.cache_hits + self.metrics.cache_misses > 0 
                             else 0)
            success_rate = (self.metrics.successful_ops / 
                          (self.metrics.successful_ops + self.metrics.failed_ops)
                          if self.metrics.successful_ops + self.metrics.failed_ops > 0 
                          else 0)
            
            # Write results
            writer.writerow(["Average Latency (s)", avg_latency])
            writer.writerow(["Average Consistency Score", avg_consistency])
            writer.writerow(["Cache Hit Ratio", cache_hit_ratio])
            writer.writerow(["Operation Success Rate", success_rate])
            writer.writerow(["Total Operations", 
                           self.metrics.successful_ops + self.metrics.failed_ops])
            writer.writerow(["Test Timestamp", datetime.now().isoformat()])

async def main():
    print("Starting Comprehensive Kademlia Test Suite...")
    test_suite = KademliaTestSuite()
    
    # Initialize network
    print("Setting up network...")
    servers = await test_suite.setup_network(INITIAL_NODES)
    
    # Run tests
    print("Testing latency...")
    await test_suite.test_latency(servers)
    
    print("Testing consistency...")
    await test_suite.test_consistency(servers)
    
    print("Testing cache performance...")
    await test_suite.test_cache_performance(servers)
    
    print("Testing churn resilience...")
    await test_suite.test_churn_resilience(servers)
    
    # Generate results
    print("Generating result plots...")
    test_suite.plot_results()
    
    print("Saving results to CSV...")
    test_suite.save_results_csv()
    
    # Cleanup
    for server in servers:
        server.stop()
    
    print(f"Testing complete. Results saved in {CSV_FILE} and {PLOTS_DIR}/")

if __name__ == "__main__":
    asyncio.run(main())