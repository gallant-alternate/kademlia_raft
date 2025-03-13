import heapq
import time
import operator
import asyncio

from itertools import chain
from collections import OrderedDict
from utils import shared_prefix, bytes_to_bit_string


class KBucket:
    def __init__(self, rangeLower, rangeUpper, ksize, replacementNodeFactor=5):
        self.range = (rangeLower, rangeUpper)
        self.ksize = ksize
        self.nodes = OrderedDict()
        self.replacement_nodes = OrderedDict()
        self.touch_last_updated()
        self.max_replacement_nodes = self.ksize * replacementNodeFactor

    def touch_last_updated(self):
        self.last_updated = time.monotonic()

    def split(self):
        pass