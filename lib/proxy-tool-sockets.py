#!/usr/bin/python2
"""Usage: port-tool <add|del|list|help> ...

Note that all <src> and <dest> are in terms of a portspec, which looks like:
  <proto>:<host>:<port>
Example:
    TCP:www.google.com:80
or
    UDP:www.streaming.example.com:9100

add <src> <dest>: Adds a mapping between the source and destionation given.
del <src>: Removes the mapping which is associated with the source given.
list: Gets all of the mappings on the system.
help: Prints this screen
"""

import socket
import socketproto
import sys

def portspec(arg):
    proto, host, port = arg.split(":")
    return (host, int(port), {
            'TCP': socket.SOCK_STREAM,
            'UDP': socket.SOCK_DGRAM,
    }[proto])

try:
    if sys.argv[1] not in ('add', 'del', 'list'):
        print __doc__
        sys.exit(1)

    if sys.argv[1] == 'add':
        src = portspec(sys.argv[2])
        dest = portspec(sys.argv[3])
    elif sys.argv[1] == 'del':
        src = portspec(sys.argv[2])
except IndexError:
    print __doc__
    sys.exit(1)

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect("/tmp/.proxy-socket")

if sys.argv[1] == 'add':
    socketproto.write_message(client, (socketproto.Messages.AddProxy, (src, dest)))
    if socketproto.read_message(client) is not True:
        print '[Unable to map port - is it taken already?]'
        sys.exit(1)

elif sys.argv[1] == 'del':
    socketproto.write_message(client, (socketproto.Messages.DelProxy, src))
    if socketproto.read_message(client) is not True:
        print '[Unable to unmap port - does it have a proxy?]'
        sys.exit(1)

elif sys.argv[1] == 'list':
    socketproto.write_message(client, (socketproto.Messages.GetProxies, []))
    msg, proxies = socketproto.read_message(client)
    if msg != socketproto.Messages.GetProxies:
        print '[Protocol error]'

    tostring = {
        socket.SOCK_STREAM: 'TCP',
        socket.SOCK_DGRAM: 'UDP',
    }

    for ((srchost, srcport, srcproto), (desthost, destport, destproto)) in proxies:
        print '{}:{} ({}) -> {}:{} ({})'.format(srchost, srcport, tostring[srcproto], desthost, destport, tostring[destproto])
