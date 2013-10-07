"""
This is the srctree server - it has the following sections:

    * Configuration - This handles the reading of the configuration file.
    * Loader - This takes the output of the configuration reader, and does the
      actual loading of the plugin modules.
    * Plugin Interface - This provides the basic interface which the clients
      can access.
    * Server - This is the actual WSGI server which handles requests and
      delegates to the plugins.
"""

import configparser
import importlib
import mimetypes
import os
import re
import sys
from wsgiref.simple_server import make_server

# Configuration #

class ConfigFile:
    """
    Handles loading the list of plugins, as well as a set of options for each
    individual plugin.
    """
    def __init__(self):
        self.plugins = []
        self.plugin_options = {}

    def to_dict(self, section, configobject):
        "Converts a ConfigParser object to a true dict"
        try:
            return dict(configobject.items(section))
        except configparser.NoSectionError:
            return {}
            

    def check_valid_module_name(self, module):
        """
        Makes sure that the given module name is valid in Python.
        """
        valid = True
        parts = module.split('.')
        for name in parts:
            if not name.isidentifier():
                valid = False

        if not valid:
            raise ValueError("Invalid module name in config file '{}'".format(
                        module))

    def check_valid_path(self, pathname):
        """
        Makes sure that the given path is a valid place to put the plugin.
        """
        if pathname.startswith('/static'):
            raise ValueError("Plugins cannot manage the /static directory")

        valid = True
        parts = module.split('/')
        for directory in parts:
            if not directory:
                valid = False

        if not valid:
            raise ValueError("Invalid resource path in config file '{}'".format(
                        pathname))

        if pathname in self.trees.values():
            raise ValueError("Already loaded a plugin at the path '{}'".format(
                        pathname))

    def load(self, filename):
        """
        Loads a configuration file.

        This populates self.trees with the plugins to be loaded,
        and populates self.plugin_options for the options for each
        individual plugin.
        """
        cp = configparser.ConfigParser()
        with open(filename) as config:
            cp.read_file(config)

        self.plugins = cp.get('Plugins', 'load').split()
        
        for plugin in self.plugins:
            self.plugin_options[plugin] = self.to_dict(plugin, cp)

# Loader #
def make_module_namespace(modulename, configfile):
    """
    Gets all the necessary data to inject into the module for loading.
    """
    namespace = {}
    namespace['module_options'] = configfile.plugin_options[modulename]
    namespace['Endpoint'] = Endpoint
    namespace['Group'] = Group
    namespace['Redirect'] = Redirect
    namespace['NotFound'] = NotFound
    namespace['register'] = register_tree
    namespace['get_icon'] = get_icon
    namespace['static_path'] = os.path.abspath('./static')
    namespace['load_template'] = load_template

    # A somewhat opaque way to convert a dict to an object
    return type('srctree', (object,), namespace)

def load_module(modulename, configfile):
    """
    Does the module loading and injects the proper values.
    """
    namespace = make_module_namespace(modulename, configfile)
    module = importlib.import_module(modulename)
    module.srctree = namespace
    module.load()

# Plugin Interface and Builtin Pages #

def build_toplevel_group(variables):
    "Bulids a listing of all the different plugin groups"
    return Group(*[url for url in sorted(HANDLERS)])

def get_static_content(variables):
    path = '.' + variables['PATH_INFO']
    try:
        with open(path, 'rb') as f:
            data = f.read()
        mimetype = mimetypes.guess_type(path, strict=False)
        return Endpoint(200, data, mimetype[0], utf8=False)
    except (FileNotFoundError, IsADirectoryError):
        return Endpoint(404, 'Not found', 'text/plain')

# A mapping of path -> icon
ICONS = { '/': '/static/generic.png' }

# A mapping of path -> handler
HANDLERS = { '/': build_toplevel_group,
             '/static': get_static_content }
HIDDEN = { '/', '/static' }

def get_best_match(url, possible):
    "Gets the best match for a URL out of a list of possible URLs"
    while url not in possible:
        # I don't *think* that the split-join would produce an empty string,
        # but its nice to be safe.
        if not url:
            return '/'
        url = '/'.join(url.split('/')[:-1])
    return url

class Endpoint:
    """
    Actual content that is managed directly by the plugin.

        Endpoint(status # The HTTP status
                 content # The UTF-8 encoded data to send back
                 mimetype # The MIME type of the content to send back
                 headers # The extra headers, if any
                 utf8 # Whether or not to encode from UTF-8 - true by default
                )
    """
    def __init__(self, status, content, mimetype, headers=None, utf8=True):
        self.status = str(status) + " WHATEVER"
        if utf8:
            self.content = content.encode('utf-8')
        else:
            self.content = content
        self.mimetype = mimetype
        self.headers = {
            'Content-Type': mimetype,
            'Content-Length': str(len(content))
        }

        if headers is not None:
            for key, value in headers.items():
                self.headers[key] = value

    def send(self, send_headers):
        "Sends over the headers and returns the body. For the WSGI server."
        headers = list(self.headers.items())
        send_headers(str(self.status), headers)
        return [self.content]

class Redirect(Endpoint):
    """
    Issues a HTTP redirect with a non-empty page.

        Redirect(url: 'The URL to redirect to')
    """
    def __init__(self, url):
        Endpoint.__init__(self,
                          301,
                          'Redirecting',
                          'text/plain',
                          {'Location': url})

class NotFound(Endpoint):
    """
    Issues a HTTP not-found error with a simple error.

        NotFound()
    """
    def __init__(self):
        Endpoint.__init__(self,
                          404,
                          'Not Found',
                          'text/plain')

class Group:
    """
    A collection of URLs which are assembed into a page of links.

        Group(*urls # A list of urls to be managed)
    """
    def __init__(self, *urls):
        self.urls = {}
        for url in urls:
            icon = get_icon(url)
            if url.startswith('!'):
                url = url.lstrip('!')
                self.urls[url] = icon
            else:
                if url not in HIDDEN:
                    self.urls[url] = icon

    def build_html(self):
        "Builds the HTML of the page"
        html_header, html_footer = (
                '<html>'
                '<head>'
                '<title>'
                'srctree'
                '</title>'
                '<body>',

                '</body>'
                '</html>'
        )
        html_body = ''
        for url, icon in self.urls.items():
            html_body += '<a href="{}"><img src="{}" />{}</a><br/>'.format(url, icon, url)
        return html_header + html_body + html_footer

    def send(self, send_headers):
        "Sends over the headers and returns the body. For the WSGI server."
        ep = Endpoint(200, self.build_html(), 'text/html')
        return ep.send(send_headers)

def register_tree(tree, handler, icon=None, hide=False):
    "Registers a new URL tree with a possible icon for that tree"
    if tree in HANDLERS:
        raise ValueError("The tree '{}' is already claimed".format(tree))

    HANDLERS[tree] = handler
    if icon is not None:
        ICONS[tree] = icon

    if hide:
        HIDDEN.add(tree)

def load_template(filename, **variables):
    "Loads a template and fills it in with variables - uses Python str.format syntax"
    with open(filename) as template:
        data = template.read()
    return data.format(**variables)

def get_icon(url):
    "Gets the icon which best matches the given URL"
    return ICONS[get_best_match(url, ICONS)]

def handle_request(variables, start_response):
    "Handles a single request to the server"
    path = variables['PATH_INFO']
    if not path.startswith('/'):
        path = '/' + path
    best_match = get_best_match(path, HANDLERS)

    content = HANDLERS[best_match](variables)
    return content.send(start_response)

try:
    configfile = ConfigFile()
    configfile.load(sys.argv[1])
    
    for plugin in configfile.plugins:
        load_module(plugin, configfile)
except IndexError:
    print('python3 server.py <configfile>', file=sys.stderr)
    sys.exit(1)

httpd = make_server('', 8000, handle_request)
httpd.serve_forever()
