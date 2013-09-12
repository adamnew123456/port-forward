"""
A wrapper around both epoll and select.

This allows for the superior performance of epoll without making this tool
Linux specific
"""

import select
import sys

if sys.platform == 'linux':
    class Poller:
        def __init__(self):
            self.poller = select.epoll()

        def register(self, fd):
            self.poller.register(fd, select.EPOLLIN)
        
        def unregister(self, fd):
            self.poller.unregister(fd)

        def poll(self, timeout):
            return [ fd_event[0] for fd_event in self.poller.poll(timeout=timeout) ]
else:
    class Poller:
        def __init__(self):
            self.watchers = []

        def register(self, fd):
            self.watchers.append(fd)

        def unregister(self, fd):
            self.watchers.remove(fd)

        def poll(self, timeout):
            (readers, _, _) = select.select(self.watchers, [], [], timeout)
            return readers
