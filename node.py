from operator import itemgetter
import heapq
from typing import Self

class Node:
    '''
    Node contains there thing <node id, port, ip>
    '''

    def __init__(self, node_id, ip=None, port=None):
        self.id = node_id
        self.ip = ip
        self.port = port
        self.long_id = int(node_id.hex(),16)

    
    def same_as_home(self, node):
        return self.ip == node.ip and self.port == node.port
    
    def distance_to(self, node : Self ):
        return self.long_id ^ node.long_id
    
    def __iter__(self):
        """
        Enables use of Node as a tuple - i.e., tuple(node) works.
        """
        return iter([self.id, self.ip, self.port])

    def __repr__(self):
        return repr([self.long_id, self.ip, self.port])

    def __str__(self):
        return "%s:%s" % (self.ip, str(self.port))
    

class NodeHeap:
    '''
    Current implementation uses priority queue
    Improvement can be made by using binary search tree
    '''
    def __init__(self, node: Node, maxsize):
        self.node = node
        self.heap = []
        self.maxsize = maxsize
        self.contacted = set()
    
    def remove(self, peers):
        peers = set(peers)
        if not len(peers):
            return

        nheap = []

        for dist, node in self.heap:
            if node.id not in peers:
                heapq.heappush(nheap, (dist, node))
        
        self.heap = nheap

    def get_node(self, node_id):
        for _,node in self.heap:
            if node.id == node_id:
                return node
        return None
