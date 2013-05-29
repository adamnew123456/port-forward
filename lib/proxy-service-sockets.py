"""
The service component for the port redirector.

The service accepts connections through a Unix domain sockets.
"""

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('[' + __name__ + ']')

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
                logger.debug("Done")
            except socket.error as e:
                socketproto.write_message(client, False)
                logger.debug("Fail\n\t-%s", e)

        elif msgtype == socketproto.Messages.DelProxy:
            src = params
            try:
                portforward.del_mapping(src)
                socketproto.write_message(client, True)
                logger.debug("Done")
            except KeyError:
                socketproto.write_message(client, False)
                logger.debug("Fail")

        elif msgtype == socketproto.Messages.GetProxies:
            src_to_dest = []
            for svr in portforward.src_to_svr.itervalues():
                src = svr._src
                dest = svr._dest
                src_to_dest.append((src, dest))

            socketproto.write_message(client, 
                    (socketproto.Messages.GetProxies, src_to_dest))

        client.close()
        
except KeyboardInterrupt:
    server.close()
    os.remove('/tmp/.proxy-socket')
    portforward.quit()
