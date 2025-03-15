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

    def push(self, nodes):
        if not isinstance(nodes, list):
            nodes = [nodes]

        for node in nodes:
            if node not in self:
                heapq.heappush(self.heap,(self.node.distance_to(node), node))

    def mark_contacted(self, node):
        self.contacted.add(node.id)

    def popleft(self):
        return heapq.heappop(self.heap)[1] if self else None

    def get_id(self):
        return [n.id for n in self.heap]


    def have_contacted_all(self):
        return len(self.get_not_contacted()) == 0

    def get_not_contacted(self):
        return [node for node in self if node.id not in self.contacted]


    def __len__(self):
        return min(len(self.heap), self.maxsize)


    def __contains__(self, node):
        for _, other in self.heap:
            if node.id == other.id:
                return True

        return False

    def __iter__(self):
        nodes = heapq.nsmallest(self.maxsize, self.heap)
        return iter(map(itemgetter(1), nodes))

