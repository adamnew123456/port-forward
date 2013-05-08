import os
import socket
import socketproto

def assert_eq(a, b):
    print repr(a), "==", repr(b), "..."
    assert a == b

test_socket_recv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

test_socket_recv.bind('/tmp/proxy-sockets-test')
test_socket_recv.listen(1)
client, _ = test_socket_recv.accept()

try:
    # The first message is a bind from :8000 to www.google.com:80. Succeed at this.
    msgtype, params = socketproto.read_message(client)
    assert_eq(msgtype, socketproto.Messages.AddProxy)
    assert_eq(params[0][0], '')
    assert_eq(params[0][1], 8000)
    assert_eq(params[1][0], 'www.google.com')
    assert_eq(params[1][1], 80)

    socketproto.write_message(client, True)
    print "[AddProxy] Success"

    # The second message removes the bind at :8000. Fail at this.
    msgtype, params = socketproto.read_message(client)
    assert_eq(msgtype, socketproto.Messages.DelProxy)
    assert_eq(params[0], '')
    assert_eq(params[1], 8000)

    socketproto.write_message(client, False)
    print "[DelProxy] Success"

    # The third message lists the proxies (say that there is only one)
    msgtype, params = socketproto.read_message(client)
    assert_eq(msgtype, socketproto.Messages.GetProxies)
    assert_eq(params, [])

    socketproto.write_message(client, (socketproto.Messages.GetProxies, [(('', 8000), ('www.google.com', 80))]))
    print "[GetProxies] Success"
finally:
    client.close()
    test_socket_recv.close()
    os.remove('/tmp/proxy-sockets-test')
