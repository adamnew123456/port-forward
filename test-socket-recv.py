import socket
import socketproto
import time

def assert_eq(a, b):
    print repr(a), "==", repr(b), "..."
    assert a == b

test_socket_send = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
test_socket_send.connect('/tmp/proxy-sockets-test')

try:
    socketproto.write_message(test_socket_send, (socketproto.Messages.AddProxy, (('', 8000), ('www.google.com', 80))))
    msg = socketproto.read_message(test_socket_send)
    assert type(msg) is bool
    assert_eq(msg, True)
    print "[AddProxy] Success"

    socketproto.write_message(test_socket_send, (socketproto.Messages.DelProxy, ('', 8000)))
    msg = socketproto.read_message(test_socket_send)
    assert type(msg) is bool
    assert_eq(msg,  False)
    print "[DelProxy] Success"

    socketproto.write_message(test_socket_send, (socketproto.Messages.GetProxies, []))
    msgtype, param = socketproto.read_message(test_socket_send)
    assert_eq(msgtype, socketproto.Messages.GetProxies)
    assert_eq(param, [(('', 8000), ('www.google.com', 80))])
    print "[GetProxies] Success"
finally:
    test_socket_send.close()
