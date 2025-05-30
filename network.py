"""
Package for interacting on the network at a high level.
"""
import random
import pickle
import asyncio
import logging
import time

from protocol import KademliaProtocol
from utils import digest
from storage import ForgetfulStorage
from node import Node
from crawling import ValueSpiderCrawl
from crawling import NodeSpiderCrawl

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class DynamicQuorum:
    def __init__(self, min_r=1, min_w=1, min_n=3):
        self.min_r = min_r  # Minimum read quorum
        self.min_w = min_w  # Minimum write quorum
        self.min_n = min_n  # Minimum total replicas
        self.current_r = min_r
        self.current_w = min_w
        self.current_n = min_n
        self.response_times = []
        self.failure_counts = 0
        self.last_adjustment = time.monotonic()

    def adjust_quorum(self, latency, success):
        """Adjust R and W based on network conditions"""
        current_time = time.monotonic()
        
        # Only adjust every 5 seconds
        if current_time - self.last_adjustment < 5:
            return
            
        self.response_times.append(latency)
        if len(self.response_times) > 100:
            self.response_times.pop(0)
            
        if not success:
            self.failure_counts += 1
        else:
            self.failure_counts = max(0, self.failure_counts - 1)

        avg_latency = sum(self.response_times) / len(self.response_times)
        
        # If high latency or failures, increase read quorum for better consistency
        if avg_latency > 1.0 or self.failure_counts > 3:
            self.current_r = min(self.current_n - 1, self.current_r + 1)
            self.current_w = max(self.min_w, self.current_w - 1)
        else:
            # If network is healthy, balance R and W
            self.current_r = max(self.min_r, self.current_r - 1)
            self.current_w = min(self.current_n - 1, self.current_w + 1)
            
        # Ensure R + W > N for strong consistency
        if self.current_r + self.current_w <= self.current_n:
            self.current_w = self.current_n - self.current_r + 1
            
        self.last_adjustment = current_time

    def get_read_quorum(self):
        return self.current_r

    def get_write_quorum(self):
        return self.current_w

    def get_total_replicas(self):
        return self.current_n


# pylint: disable=too-many-instance-attributes
class Server:
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """

    protocol_class = KademliaProtocol

    def __init__(self, ksize=20, alpha=3, node_id=None, storage=None):
        """
        Create a server instance.  This will start listening on the given port.

        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            node_id: The id for this node on the network.
            storage: An instance that implements the interface
                     :class:`~kademlia.storage.IStorage`
        """
        self.ksize = ksize
        self.alpha = alpha
        self.storage = storage or ForgetfulStorage()
        self.node = Node(node_id or digest(random.getrandbits(255)))
        self.transport = None
        self.protocol = None
        self.refresh_loop = None
        self.save_state_loop = None
        self.quorum = DynamicQuorum()
        self.port = None  # Add port attribute

    async def listen(self, port, interface='0.0.0.0'):
        """
        Start listening on the given port.

        Provide interface="::" to accept ipv6 address
        """
        self.port = port  # Store the port number
        loop = asyncio.get_event_loop()
        listen = loop.create_datagram_endpoint(self._create_protocol,
                                               local_addr=(interface, port))
        log.info("Node %i listening on %s:%i",
                 self.node.long_id, interface, port)
        self.transport, self.protocol = await listen
        # finally, schedule refreshing table
        self.refresh_table()

    def stop(self):
        if self.transport is not None:
            self.transport.close()

        if self.refresh_loop:
            self.refresh_loop.cancel()

        if self.save_state_loop:
            self.save_state_loop.cancel()

    def _create_protocol(self):
        return self.protocol_class(self.node, self.storage, self.ksize)

    def refresh_table(self, interval=3600):
        log.debug("Refreshing routing table")
        asyncio.ensure_future(self._refresh_table())
        loop = asyncio.get_event_loop()
        self.refresh_loop = loop.call_later(interval, self.refresh_table)

    async def _refresh_table(self):
        """
        Refresh buckets that haven't had any lookups in the last hour
        (per section 2.3 of the paper).
        """
        results = []
        for node_id in self.protocol.get_refresh_ids():
            node = Node(node_id)
            nearest = self.protocol.router.find_neighbors(node, self.alpha)
            spider = NodeSpiderCrawl(self.protocol, node, nearest,
                                     self.ksize, self.alpha)
            results.append(spider.find())

        # do our crawling
        await asyncio.gather(*results)

        # now republish keys older than one hour
        for dkey, value in self.storage.iter_older_than(3600):
            await self.set_digest(dkey, value)

    def bootstrappable_neighbors(self):
        """
        Get a :class:`list` of (ip, port) :class:`tuple` pairs suitable for
        use as an argument to the bootstrap method.

        The server should have been bootstrapped
        already - this is just a utility for getting some neighbors and then
        storing them if this server is going down for a while.  When it comes
        back up, the list of nodes can be used to bootstrap.
        """
        neighbors = self.protocol.router.find_neighbors(self.node)
        return [tuple(n)[-2:] for n in neighbors]

    async def bootstrap(self, addrs):
        """
        Bootstrap the server by connecting to other known nodes in the network.

        Args:
            addrs: A `list` of (ip, port) `tuple` pairs.  Note that only IP
                   addresses are acceptable - hostnames will cause an error.
        """
        log.debug("Attempting to bootstrap node with %i initial contacts",
                  len(addrs))
        cos = list(map(self.bootstrap_node, addrs))
        gathered = await asyncio.gather(*cos)
        nodes = [node for node in gathered if node is not None]
        spider = NodeSpiderCrawl(self.protocol, self.node, nodes,
                                 self.ksize, self.alpha)
        return await spider.find()

    async def bootstrap_node(self, addr):
        result = await self.protocol.ping(addr, self.node.id)
        return Node(result[1], addr[0], addr[1]) if result[0] else None

    async def get(self, key):
        """
        Get a key if the network has it, using dynamic read quorum.
        """
        log.info("Looking up key %s", key)
        dkey = digest(key)
        
        start_time = time.monotonic()
        
        # Try local cache first
        if self.storage.get(dkey) is not None:
            return self.storage.get(dkey)
            
        node = Node(dkey)
        nearest = self.protocol.router.find_neighbors(node)
        if not nearest:
            log.warning("There are no known neighbors to get key %s", key)
            return None
            
        spider = ValueSpiderCrawl(self.protocol, node, nearest,
                               self.ksize, self.alpha)
                               
        result = await spider.find()
        latency = time.monotonic() - start_time
        
        self.quorum.adjust_quorum(latency, result is not None)
        return result

    async def set(self, key, value):
        """
        Set the given string key to the given value in the network with dynamic write quorum.
        """
        if not check_dht_value_type(value):
            raise TypeError(
                "Value must be of type int, float, bool, str, or bytes"
            )
        log.info("setting '%s' = '%s' on network", key, value)
        dkey = digest(key)
        
        start_time = time.monotonic()
        success = await self.set_digest(dkey, value)
        latency = time.monotonic() - start_time
        
        self.quorum.adjust_quorum(latency, success)
        return success

    async def set_digest(self, dkey, value):
        """
        Set the given SHA1 digest key (bytes) to the given value in the
        network.
        """
        node = Node(dkey)

        nearest = self.protocol.router.find_neighbors(node)
        if not nearest:
            log.warning("There are no known neighbors to set key %s",
                        dkey.hex())
            return False

        spider = NodeSpiderCrawl(self.protocol, node, nearest,
                                 self.ksize, self.alpha)
        nodes = await spider.find()
        log.info("setting '%s' on %s", dkey.hex(), list(map(str, nodes)))

        # if this node is close too, then store here as well
        biggest = max([n.distance_to(node) for n in nodes])
        if self.node.distance_to(node) < biggest:
            self.storage[dkey] = value
        results = [self.protocol.call_store(n, dkey, value) for n in nodes]
        # return true only if at least one store call succeeded
        return any(await asyncio.gather(*results))

    def save_state(self, fname):
        """
        Save the state of this node (the alpha/ksize/id/immediate neighbors)
        to a cache file with the given fname.
        """
        log.info("Saving state to %s", fname)
        data = {
            'ksize': self.ksize,
            'alpha': self.alpha,
            'id': self.node.id,
            'neighbors': self.bootstrappable_neighbors()
        }
        if not data['neighbors']:
            log.warning("No known neighbors, so not writing to cache.")
            return
        with open(fname, 'wb') as file:
            pickle.dump(data, file)

    @classmethod
    async def load_state(cls, fname, port, interface='0.0.0.0'):
        """
        Load the state of this node (the alpha/ksize/id/immediate neighbors)
        from a cache file with the given fname and then bootstrap the node
        (using the given port/interface to start listening/bootstrapping).
        """
        log.info("Loading state from %s", fname)
        with open(fname, 'rb') as file:
            data = pickle.load(file)
        svr = cls(data['ksize'], data['alpha'], data['id'])
        await svr.listen(port, interface)
        if data['neighbors']:
            await svr.bootstrap(data['neighbors'])
        return svr

    def save_state_regularly(self, fname, frequency=600):
        """
        Save the state of node with a given regularity to the given
        filename.

        Args:
            fname: File name to save retularly to
            frequency: Frequency in seconds that the state should be saved.
                        By default, 10 minutes.
        """
        self.save_state(fname)
        loop = asyncio.get_event_loop()
        self.save_state_loop = loop.call_later(frequency,
                                               self.save_state_regularly,
                                               fname,
                                               frequency)


def check_dht_value_type(value):
    """
    Checks to see if the type of the value is a valid type for
    placing in the dht.
    """
    typeset = [
        int,
        float,
        bool,
        str,
        bytes
    ]
    return type(value) in typeset  # pylint: disable=unidiomatic-typecheck