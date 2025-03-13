import time
from itertools import takewhile
import operator
from collections import OrderedDict
from abc import abstractmethod, ABC


class IStorage(ABC):
    '''
    Local storage for a particular node
    '''

    @abstractmethod
    def __setitem__(self, key, value):
        '''
        Set a key to the given value
        '''

    @abstractmethod
    def __getitem_(self, key):
        '''
        Get the given key, raise error if key does not exist
        '''

    @abstractmethod
    def get(self, key, default=None):
        '''
        Get the given key, return default if key does not exist 
        '''

    @abstractmethod
    def __iter__(self):
        '''
        Get the iterator for this storage
        '''



class ForgetfulStorage(IStorage):

    def __init__(self, ttl=604800):
        self.data = OrderedDict()
        self.ttl = ttl


    def __setitem__(self, key, value):
        if key in self.data:
            del self.data[key]

        self.data[key] = (time.monotonic(), value)

    def __getitem_(self, key):
        return self.data[key][1]
    
    def get(self, key, default):
        if key in self.data:
            return self[key]
        return default
    
    def __repr__(self):
        return repr(self.data)
    

        