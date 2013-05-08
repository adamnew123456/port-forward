"""
The service component for the port redirector.

The service accepts connections through a Unix domain sockets.
"""

import os
import socket
import socketproto
import portforward

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind('/tmp/.proxy-socket')
server.listen(1)

try:
    while True:
        client, _ = server.accept()

        # Go ahead and assume a command, since the client
        # will never send a lone True/False
        msgtype, params = socketproto.read_message(client)

        if msgtype == socketproto.Messages.AddProxy:
            src, dest = params
            try:
                portforward.add_mapping(src, dest)
                socketproto.write_message(client, True)
                print "Done"
            except:
                socketproto.write_message(client, False)
                print "Fail"

        elif msgtype == socketproto.Messages.DelProxy:
            src = params
            try:
                portforward.del_mapping(src)
                socketproto.write_message(client, True)
                print "Done"
            except:
                socketproto.write_message(client, False)
                print "Fail"

        elif msgtype == socketproto.Messages.GetProxies:
            src_to_dest = []
            for src in portforward.src_to_svr:
                svr = portforward.src_to_svr[src]
                dest = portforward.svr_to_dest[svr.fileno()]
                src_to_dest.append(((src[0], src[1]), (dest[1], dest[2])))
            socketproto.write_message(client, (socketproto.Messages.GetProxies, src_to_dest))

        client.close()
        
except KeyboardInterrupt:
    server.close()
    os.remove('/tmp/.proxy-socket')
    portforward.quit()
