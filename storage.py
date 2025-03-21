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

        