import struct

class Messages:
    """
    All messages that can be sent down the socket.
    """
    AddProxy, DelProxy, GetProxies, Quit, Success, Failure = list(range(2, 8))

def read_host_port_proto(socket):
    """
    Reads a single host-port-proto triple off the socket.
    """
    unpacking_recv = lambda sz, fmt: struct.unpack(fmt, socket.recv(sz))[0]
    host_sz = unpacking_recv(4, "@I")
    host = socket.recv(host_sz).decode('utf-8')
    port = unpacking_recv(4, "@I")
    proto = unpacking_recv(4, "@I")
    return (host, port, proto)

def read_message(socket):
    """
    Reads a message packet off the socket, returning the tuple
    (MessageType, Params) or a boolean if it is a success/fail message.
    """
    msg_type = struct.unpack("@B", socket.recv(1))[0]

    if msg_type == Messages.AddProxy:
        src = read_host_port_proto(socket)
        dest = read_host_port_proto(socket)
        return (Messages.AddProxy, (src, dest))
    elif msg_type == Messages.DelProxy:
        src = read_host_port_proto(socket)
        return (Messages.DelProxy, src)
    elif msg_type == Messages.GetProxies:
        num_proxies = struct.unpack("@I", socket.recv(4))[0]
        proxies = []
        for x in range(num_proxies):
            src = read_host_port_proto(socket)
            dest = read_host_port_proto(socket)
            proxies.append((src, dest))
        return (Messages.GetProxies, proxies)
    elif msg_type == Messages.Quit:
        return (Messages.Quit, [])
    elif msg_type in (1, 0):
        return bool(msg_type)
    else:
        raise ValueError("{} is not a valid message!".format(msg_type))

def write_host_port_proto(socket, host, port, proto):
    """
    Writes a single host-port-proto triple to the socket.
    """ 
    packing_send = lambda val, fmt: socket.send(struct.pack(fmt, val))
    packing_send(len(host), "@I")
    socket.send(bytes(host, 'utf-8'))
    packing_send(port, "@I")
    packing_send(proto, "@I")

def write_message(socket, msg):
    """
    Writes a single message to the socket.
    """

    if type(msg) == bool and msg in (True, False):
        socket.send(struct.pack("@B", msg))
        return

    msgtype, params = msg
    socket.send(struct.pack("@B", msgtype))
    if msgtype == Messages.AddProxy:
        write_host_port_proto(socket, params[0][0], params[0][1], params[0][2])
        write_host_port_proto(socket, params[1][0], params[1][1], params[1][2])
    elif msgtype == Messages.DelProxy:
        write_host_port_proto(socket, params[0], params[1], params[2])
    elif msgtype == Messages.GetProxies:
        socket.send(struct.pack("@I", len(params)))
        for param in params:
            write_host_port_proto(socket, param[0][0], param[0][1], param[0][2])
            write_host_port_proto(socket, param[1][0], param[1][1], param[1][2])
    elif msgtype == Messages.Quit:
        pass
    else:
        raise ValueError("{} is not a valid message!".format(msg_type))
