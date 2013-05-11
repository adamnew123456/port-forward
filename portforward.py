import logging
import select
import socket
import threading

logger = logging.getLogger('[' + __name__ + ']')

class Protocol:
    "Various useful constants and maps related to TCP and UDP"
    (TCP, UDP) = (socket.SOCK_STREAM, socket.SOCK_DGRAM)
    ToString = {
         socket.SOCK_STREAM: 'TCP',
         socket.SOCK_DGRAM: 'UDP',
    }
    FromString = {
        'TCP': socket.SOCK_STREAM,
        'UDP': socket.SOCK_DGRAM
    }

class Address:
    "Constants to address information in portspec tuples"
    (HOST, PORT, PROTOCOL) = range(3)
    HOST_AND_PORT = -1

def format_address((host, port, proto)):
    "Formats a portspec address into a string"
    return "{}:{} ({})".format(host, port, Protocol.ToString[proto])

def make_server(proto, src, dest):
    if proto == Protocol.TCP:
        return TCPServer(src, dest)
    else:
        logging.error("The UDP -> * implementation is really flaky right now. Best not to use it.")
        raise NotImplementedError()

class UDPServer:
    "A wrapper for the functions of the UDP server socket"
    def __init__(self, src, dest):
        self._src = src
        self._dest = dest
        self._server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._bridge = None

    def __str__(self):
        return "{} -> {}".format(format_address(self._src), format_address(self._dest))

    def setup(self):
        "Binds the socket and registers it"
        self._server.setblocking(0)
        self._server.bind(self._src[:Address.HOST_AND_PORT])
        poll.register(self._server, select.EPOLLIN)

        src_to_svr[self._src] = self
        fd_to_svr[self._server.fileno()] = self

        logger.debug("UDP: Created Server %s", self)

    def destroy(self):
        "Stops listening on this server socket"
        logger.debug("UDP: Destroying %s", self)
        del src_to_svr[self._src]
        del fd_to_svr[self._server.fileno()]
        
        if self._bridge:
            self._bridge.close()

        poll.unregister(self._server)
        self._server.close()

    def connect(self):
        """
        UDP makes this exercise a little strange, because UDP is connectionless 
        and the only 'connection' actually occurs when a packet is being sent to 
        this socket.

        So, the UDP server has to keep around a socket which will be open or 
        closed depending upon whether or not it is needed. It is closed when 
        the socket recieves a datagram of length 0; even though this is a 
        valid datagram, it seems sensible enough to use  an empty packet as 
        a terminating mark.
        """
        if self._bridge is None or self._bridge not in fd_to_pair:
            #
            # Apparently the easiest way to do two-way UDP communication
            # is to bind both sockets and connect them to each other.
            #
            logger.debug("UDP: Binding a bridge socket for %s", self)
            self._bridge = socket.socket(socket.AF_INET, self._dest[Address.PROTOCOL])
            self._bridge.bind(('', 0))
            self._bridge.connect(self._dest[:Address.HOST_AND_PORT])
            addr = self._bridge.getsockname()
        
            logger.debug("UDP: Bound a bridge socket on (%s, %i)", *addr)
            self._server.connect(addr)
    
            logger.debug("UDP: Registering the bridge socket %i", self._bridge.fileno())
            fd_to_pair[self._bridge.fileno()] = (self._bridge, self._server)
            poll.register(self._bridge, select.EPOLLIN)

        do_send(self._bridge, self._server)

class TCPServer:
    "A wrapper for the functions of the TCP server socket"
    def __init__(self, src, dest):
        self._src = src
        self._dest = dest
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __str__(self):
        return "{} -> {}".format(format_address(self._src), format_address(self._dest))

    def setup(self):
        "Bind the socket, start listening, and register the socket"
        self._socket.setblocking(0)
        self._socket.bind(self._src[:Address.HOST_AND_PORT])
        self._socket.listen(5)
        poll.register(self._socket, select.EPOLLIN)

        src_to_svr[self._src] = self
        fd_to_svr[self._socket.fileno()] = self

        logger.debug("TCP: Created Server %s", self)

    def destroy(self):
        "Stops listening on this server socket"
        logger.debug("TCP: Destroying %s", self)
        del src_to_svr[self._src]
        del fd_to_svr[self._socket.fileno()]

        poll.unregister(self._socket)
        self._socket.close()

    def connect(self):
        "Sets up a child socket"
        logger.debug("TCP: Accepting Connection On %s", self)

        bridge = socket.socket(socket.AF_INET, self._dest[Address.PROTOCOL])
        inbound, _ = self._socket.accept()
        dest_host, dest_port, dest_proto = self._dest
        
        try:
            logger.debug("TCP: Connecting Bridge To %s",
                         format_address(self._dest))
            bridge.connect((dest_host, dest_port))
        except socket.error as err:
            logger.error("TCP: Unable To Connect To %s Because '%s'",
                         format_address(self._dest),
                         err)
            return

        logger.debug("TCP: Pairing Inbound %i and Bridge %i",
                     inbound.fileno(), bridge.fileno())

        fd_to_pair[bridge.fileno()] = (bridge, inbound)
        fd_to_pair[inbound.fileno()] = (inbound, bridge)

        logger.debug("TCP: Registering Inbound %i And Bridge %i With epoll",
                     inbound.fileno(), bridge.fileno())
        poll.register(bridge.fileno(), select.EPOLLIN)
        poll.register(inbound.fileno(), select.EPOLLIN)

mapping_mod_lock = threading.Lock()

# Map: (src_host, src_port) -> server
# Useful for removing connections
src_to_svr = {}

# Map: server_fd -> server
# Useful for handling server connections
fd_to_svr = {}

# Map: socket_fd -> (writer_socket, reader_socket)
# Useful for doing transfers of data
fd_to_pair = {}

poll = select.epoll()

def do_send(reader, writer):
    """
    Handles sending from a reader socket to a writer socket, as well as closing
    dead sockets.
    """
    logger.debug("Sending A Message From %i -> %i", reader.fileno(), writer.fileno())

    try:
        logger.debug("Reading Message From %i", reader.fileno())
        data = writer.recv(4096)
        logger.debug("Read Message Of Length %i", len(data))
    except socket.error as err:
        # A dead socket - set the read data to empty to get it closed
        data = ""
        logger.debug("Writer Encoutered Error '%s' While Sending Data", err)

    if data:
        try:
            logger.debug("Writing Message To %i", writer.fileno())
            reader.send(data)
        except socket.error as err:
            logger.debug("Reader Encoutered Error '%s' While Getting Data", err)
    else:
        writer_fd = writer.fileno()
        if writer_fd in fd_to_pair:
            del fd_to_pair[writer_fd]
            logger.debug("Closing Writer %i", writer_fd)
            writer.close()

        reader_fd = reader.fileno()
        if reader_fd in fd_to_pair:
            del fd_to_pair[reader_fd]
            logger.debug("Closing Reader %i", reader_fd)
            reader.close()

def add_mapping((src_host, src_port, src_proto), (dest_host, dest_port, dest_proto)):
    """
    Adds a mapping from a source host and port to a destination host
    and port.
    """
    logger.debug("Added %s:%i (%s) -> %s:%i (%s) ...",
        src_host, src_port, Protocol.ToString[src_proto],
        dest_host, dest_port, Protocol.ToString[dest_proto])
    
    with mapping_mod_lock:
        server = make_server(src_proto, (src_host, src_port, src_proto), (dest_host, dest_port, dest_proto))
        server.setup()

def del_mapping((src_host, src_port, src_proto)):
    """
    Removes a mapping currently on a source host and port.

    Note that this prevents incoming connections, but all existing connections
    are kept alive. This means that there is effectively no way to remove a UDP socket.
    """
    logger.debug("Removed %s:%i (%s) ...", src_host, src_port, Protocol.ToString[src_proto])
    with mapping_mod_lock:
        server = src_to_svr[(src_host, src_port, src_proto)]
        server.destroy()

done = False
def quit():
    global done
    done = True
    
def start():
    """
    Runs a single iteration of the port forwarder, checking for new connections
    and handling reads and writes.
    """

    while not done:
        for fd, event in poll.poll(timeout=1):
            if fd in fd_to_svr:
                fd_to_svr[fd].connect()
            else:
                try:
                    writer, reader = fd_to_pair[fd]
                except KeyError:
                    # Deal with epoll's empty sends (they are apparently kill messages delivered by epoll)
                    continue

                do_send(reader, writer)

    for server in fd_to_svr.values():
        server.destroy()

    for fd in fd_to_pair:
        writer, _ = fd_to_pair[fd]
        writer.close()

thread = threading.Thread(target=start)
thread.start()
