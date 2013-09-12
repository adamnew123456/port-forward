# What is this? #

This is a port forwarder, which is designed to forward a port on localhost
to a port somewhere else (either another port on localhost, or a remote port).

# Why write it? #

I didn't want to muck around with doing any sort of system port fowarding
using something like iptables. I needed a quick solution, preferably in userspace,
which turned into this set of programs.

# How do I use it? #

The tool comes in to parts, the server and the tool, both of which have two versions,
which are the transport methods (one uses DBus and the other uses Unix sockets).

## Unix Sockets vs. DBus ##

I originally tried using DBus because it handles all of the marsaling and unmarshaling
of data between the two processes.  his worked, but not for my use case - DBus 
requires creating a session bus, which makes it difficult to run the server as root, and 
then connect to it later using `sudo`.

I wanted an IPC mechanism which could be used without running any other software,
which is why I chose Unix sockets - they have privelige mechanisms built in place
(so a user cannot change settings when the server runs as root) which were more
flexible than that of DBus.

This meant that I had to write my own protocol, but that was fine. In the process, I 
wrote  some tests in the `lib` directory, if you're curious what keeps the protocol 
implementation from failing. It seems stable enough in casual usage.

Just make sure that, whatever IPC you choose, that you use servers and tools
that match.

## The Server ##

The server is what does all the actual handling of sockets. It resides in the `bin` 
directory - just run either `proxy-service-sockets` or `proxy-service-dbus`.

It takes no command line arguments, so all you need to do is run it.

## The Tool ##

The tool is what manages the server. It can be found in the `bin` directory also,
and is called either `proxy-tool-dbus` or `proxy-tool-sockets`.

This tool requires command line arguments. Run the tool with no arguments
to find out what the required arguments are. The command set is the same,
regardless of what IPC you use.

__Note: do not try to forward a UDP socket onto a TCP socket!__

Getting the two protocols to mesh well hasn't gone well - feel free to look
at the code for the `UDPServer` class in `lib/portforward.py` if you have
any ideas.

# Where is the code? #

You'll find it in the `lib` directory.
