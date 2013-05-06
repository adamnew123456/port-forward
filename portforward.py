import select
import socket
import threading

mapping_mod_lock = threading.Lock()

# Map: (src_host, src_port) -> server
src_to_svr = {}

# Map: server_fd -> (socket, dest_host, dest_port)
svr_to_dest = {}

# Map: socket_fd -> (writer_socket, reader_socket)
fd_to_pair = {}

poll = select.epoll()

def do_connect(server_fd):
    """
    Accept a connection to one of the proxy sockets.

    Creates an entry in fd mapping and connects the incoming
    connection and a bridge to epoll.
    """
    (server, dest_host, dest_port) = svr_to_dest[server_fd]
    
    inbound, _ = server.accept()
    bridge = socket.socket()
    
    try:
        bridge.connect((dest_host, dest_port))
    except socket.error:
        print "[Unable To Connect To {}:{}]".format(dest_host, dest_port)
        return 

    fd_to_pair[bridge.fileno()] = (bridge, inbound)
    fd_to_pair[inbound.fileno()] = (inbound, bridge)

    poll.register(bridge.fileno(), select.EPOLLIN)
    poll.register(inbound.fileno(), select.EPOLLIN)

def add_mapping((src_host, src_port), (dest_host, dest_port)):
    """
    Adds a mapping from a source host and port to a destination host
    and port.
    """
    print "+ {}:{} -> {}:{} ...".format(src_host, src_port, dest_host, dest_port),
    with mapping_mod_lock:
        server = socket.socket()
        server.setblocking(0)

        server.bind((src_host, src_port))
        server.listen(5)

        poll.register(server, select.EPOLLIN)

        src_to_svr[(src_host, src_port)] = server
        svr_to_dest[server.fileno()] = (server, dest_host, dest_port)

def del_mapping((src_host, src_port)):
    """
    Removes a mapping currently on a source host and port.

    Note that this prevents incoming connections, but all existing connections
    are kept alive.
    """
    print "- {}:{} ...".format(src_host, src_port), 
    with mapping_mod_lock:
        server = src_to_svr[(src_host, src_port)]

        del svr_to_dest[server.fileno()]
        del src_to_svr[(src_host, src_port)]

        poll.unregister(server)
        server.close()

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
            if fd in svr_to_dest:
                do_connect(fd)
            else:
                try:
                    writer, reader = fd_to_pair[fd]
                except KeyError:
                    # Deal with epoll's empty sends (they are apparently kill messages)
                    continue

                try:
                    data = writer.recv(4096)
                except socket.error:
                    # A dead socket - set the read data to empty to get it closed
                    data = ""

                if data:
                    reader.send(data)
                else:
                    writer_fd = writer.fileno()
                    reader_fd = reader.fileno()

                    writer.close()
                    reader.close()

                    del fd_to_pair[writer_fd]
                    del fd_to_pair[reader_fd]

                    poll.unregister(writer_fd)
                    poll.unregister(reader_fd)

thread = threading.Thread(target=start)
thread.start()
