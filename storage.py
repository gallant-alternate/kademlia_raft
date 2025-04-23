import time
from itertools import takewhile
import operator
from collections import OrderedDict
from abc import abstractmethod, ABC


class IStorage(ABC):
    """
    Local storage for a particular node
    """

    @abstractmethod
    def __setitem__(self, key, value):
        """
        Set a key to the given value
        """

    @abstractmethod
    def __getitem__(self, key):
        """
        Get the given key, raise error if key does not exist
        """

    @abstractmethod
    def get(self, key, default=None):
        """
        Get the given key, return default if key does not exist 
        """

    @abstractmethod
    def __iter__(self):
        """
        Get the iterator for this storage
        """



class ForgetfulStorage(IStorage):

    def __init__(self, ttl=604800):
        self.data = OrderedDict()
        self.ttl = ttl

    def cull(self):
        for _, _ in self.iter_older_than(self.ttl):
            self.data.popitem(last=False)

    def __setitem__(self, key, value):
        if key in self.data:
            del self.data[key]

        self.data[key] = (time.monotonic(), value)

    def __getitem__(self, key):
        return self.data[key][1]
    
    def get(self, key, default=None):
        if key in self.data:
            return self[key]
        return default
    
    def __repr__(self):
        return repr(self.data)
    
    def iter_older_than(self, seconds_old):
        min_birthday = time.monotonic() - seconds_old
        zipped = self._triple_iter()
        matches = takewhile(lambda r: min_birthday >= r[1], zipped)
        return list(map(operator.itemgetter(0, 2), matches))
    
    def _triple_iter(self):
        ikeys = self.data.keys()
        ibirthday = map(operator.itemgetter(0), self.data.values())
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ibirthday, ivalues)
    
    def __iter__(self):
        self.cull()
        ikeys = self.data.keys()
        ivalues = map(operator.itemgetter(1), self.data.values())
        return zip(ikeys, ivalues)


class ARCStorage(IStorage):
    def __init__(self, capacity=1000):
        # T1: Recent entries
        # T2: Frequent entries
        # B1: Ghost entries for recent
        # B2: Ghost entries for frequent
        self.capacity = capacity
        self.p = 0  # Target size for T1
        self.T1 = OrderedDict()
        self.T2 = OrderedDict()
        self.B1 = OrderedDict()
        self.B2 = OrderedDict()

    def __setitem__(self, key, value):
        if key in self.T1 or key in self.T2:
            # Cache hit in T1 or T2
            if key in self.T1:
                self.T1.pop(key)
                self.T2[key] = (time.monotonic(), value)
            else:
                self.T2.move_to_end(key)
                self.T2[key] = (time.monotonic(), value)
        else:
            # Cache miss
            if len(self.T1) + len(self.T2) >= self.capacity:
                self._replace(key)
            
            if key in self.B1:
                self.p = min(self.capacity, self.p + max(len(self.B2) // len(self.B1), 1))
                self._move_to_t2(key)
                self.B1.pop(key)
            elif key in self.B2:
                self.p = max(0, self.p - max(len(self.B1) // len(self.B2), 1))
                self._move_to_t2(key)
                self.B2.pop(key)
            else:
                if len(self.T1) + len(self.B1) == self.capacity:
                    if len(self.T1) < self.capacity:
                        self.B1.popitem(last=False)
                        self._replace(key)
                elif len(self.T1) + len(self.B1) < self.capacity:
                    if len(self.T1) + len(self.T2) + len(self.B1) + len(self.B2) >= self.capacity:
                        if len(self.T1) + len(self.T2) + len(self.B1) + len(self.B2) == 2 * self.capacity:
                            self.B2.popitem(last=False)
                self.T1[key] = (time.monotonic(), value)

    def _replace(self, key):
        if len(self.T1) >= 1 and (len(self.T1) > self.p or (key in self.B2 and len(self.T1) == self.p)):
            old_key, old_value = self.T1.popitem(last=False)
            self.B1[old_key] = old_value
        else:
            old_key, old_value = self.T2.popitem(last=False)
            self.B2[old_key] = old_value

    def _move_to_t2(self, key):
        if len(self.T2) >= self.capacity - self.p:
            self.T2.popitem(last=False)
        self.T2[key] = (time.monotonic(), None)

    def __getitem__(self, key):
        if key in self.T1:
            value = self.T1.pop(key)
            self.T2[key] = value
            return value[1]
        elif key in self.T2:
            self.T2.move_to_end(key)
            return self.T2[key][1]
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        return iter(list(self.T1.items()) + list(self.T2.items()))

    def iter_older_than(self, seconds_old):
        """
        Return all (key, value) pairs older than seconds_old
        """
        min_birthday = time.monotonic() - seconds_old
        
        # Check T1 cache
        for key, (timestamp, value) in list(self.T1.items()):
            if timestamp <= min_birthday:
                yield key, value
                
        # Check T2 cache
        for key, (timestamp, value) in list(self.T2.items()):
            if timestamp <= min_birthday:
                yield key, value

