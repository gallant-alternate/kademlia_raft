# Enhancing Kademlia with Quorum-Based Replication and Caching

This project augments the classic Kademlia distributed hash table (DHT) by integrating quorum-based leaderless replication with an in-node caching system. The goal is to achieve higher consistency, fault tolerance, and performance in distributed environments without relying on a centralized leader.

---

## Table of Contents

- [Overview](#overview)
- [Motivation](#motivation)
- [Key Features](#key-features)
- [Architecture](#architecture)

---

## Overview

This project implements a robust, scalable distributed hash table based on Kademlia. By embedding Memcached instances within each node and utilizing leaderless quorum-based replication, the system:
- Serves frequently accessed ("hot") keys from memory.
- Eliminates bottlenecks associated with a single leader.
- Provides consistency through configurable quorum parameters (R, W, and N).

---

## Motivation

Traditional leader-based systems such as Raft can become bottlenecks and points of failure. Inspired by Amazon’s Dynamo, our system adopts a leaderless model. The integration of an in-memory caching layer addresses performance challenges by reducing lookup latency and network overhead under heavy read traffic.

---

## Key Features

- **Leaderless Replication:**  
  Utilizes quorum-based replication (parameters R, W, and total replicas N) to ensure that write and read operations satisfy strong consistency guarantees without a centralized leader.

- **Embedded Caching:**  
  Each node runs an instance of Memcached, allowing for low-latency access to frequently requested data and reducing the load on the network.

- **Efficient Routing:**  
  Based on Kademlia’s XOR metric, lookups complete in O(log N) hops, ensuring efficient data retrieval in the distributed network.

- **Fault Tolerance & Scalability:**  
  The design gracefully handles node failures and supports horizontal scaling through consistent hashing and dynamic node management.

---

## Architecture

### Core Components

- **Kademlia Node:**  
  Serves as a building block for the DHT, handling join/leave protocols, requests from clients, and local data management.

- **Quorum Replication Handler:**  
  Manages leaderless replication by propagating write operations to multiple replicas and collecting quorum acknowledgments before considering a write committed.

- **Cache Manager:**  
  Interfaces with the local Memcached instance to manage data caching, employing standard LRU eviction policies with future plans to incorporate advanced policies like ARC.

- **Routing Table Manager:**  
  Organizes nodes into k-buckets based on the XOR distance, optimizing key lookups and ensuring efficient query resolution.

- **Network Manager:**  
  Handles the communication between nodes, including serialization, message transmission, and asynchronous coordination of quorum responses.

