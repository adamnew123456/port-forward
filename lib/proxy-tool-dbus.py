#!/usr/bin/python2
"""Usage: port-tool <add|del|list|help> ...

Note that all <src> and <dest> are in terms of a portspec, which looks like:
  <proto>:<host>:<port>
Example:
    TCP:www.google.com:80 or
    UDP:www.streamcast.example.com:1776

add <src> <dest>: Adds a mapping between the source and destionation given
del <src>: Removes the mapping which is associated with the source given.
list: Gets all of the mappings on the system.
help: Prints this screen
"""

import dbus
import sys

def portspec(arg):
    proto, host, port = arg.split(":")
    return (host, int(port), proto)

try:
    if sys.argv[1] not in ('add', 'del', 'list'):
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == 'add':
        src = portspec(sys.argv[2])
        dest = portspec(sys.argv[3])
    elif sys.argv[1] == 'del':
        src = portspec(sys.argv[2])
except (IndexError, ValueError):
    print(__doc__)
    sys.exit(1)

BUS = "org.new123456.Proxy"
OBJ = "/org/new123456/Proxy"

bus = dbus.SessionBus()
obj = bus.get_object(BUS, OBJ)
proxy = dbus.Interface(obj, BUS)

if sys.argv[1] == 'add':
    if not proxy.AddMapping(src, dest):
        print('[Unable to map port - is it taken already?]')
        sys.exit(1)
elif sys.argv[1] == 'del':
    if not proxy.RemoveMapping(src):
        print('[Unable to unmap port - does it have a proxy?]')
        sys.exit(1)
elif sys.argv[1] == 'list':
    for (srchost, srcport, srcproto, desthost, destport, destproto) in proxy.ReadMappings():
        print('{}:{} ({}) -> {}:{} ({})'.format(srchost, srcport, srcproto, desthost, destport, destproto))
