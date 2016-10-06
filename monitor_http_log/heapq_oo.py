import heapq


class HeapQ(object):

    def __init__(self, iterable=None):
        self._items = list(iterable) if iterable else []
        heapq.heapify(self._items)

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__,
            self._items,
        )

    def add(self, item):
        heapq.heappush(self._items, item)

    def popuntil(self, item):
        """Pop and yield all items lesser than the given item"""
        if not self._items:
            return

        while True:
            try:
                v = heapq.heappop(self._items)
            except IndexError:
                # All the items were < `item` so we've emptied the heap.
                break
            if v < item:
                yield v
            else:
                heapq.heappush(self._items, v)
                break
