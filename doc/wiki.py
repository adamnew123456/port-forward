import html
import lzma
import re
import subprocess
import sqlite3
import urllib.parse as urlparse

def compress(data):
    "Compresses data using LZMA"
    as_bytes = bytes(data, 'utf-8')
    return lzma.compress(as_bytes)

def decompress(data):
    "Decompresses data using LZMA"
    as_utf8 = str(lzma.decompress(data), 'utf-8')
    return as_utf8

def read_post(variables):
    "Reads post data and decodes it"
    content_length = int(variables['CONTENT_LENGTH'])
    data = variables['wsgi.input'].read(content_length)
    postvars = urlparse.parse_qs(data)

    outputs = {}
    for item in postvars:
        key = str(item, 'utf-8')
        value = str(postvars[item][0], 'utf-8')
        outputs[key] = value
    return outputs

def build_links(contents):
    "Assemble the contents into HTML using WikiWords"
    # This is sort of strange, and requires the code to iterate through
    # each individual match, replacing the contents with links while preserving
    # the rest of the data
    output = []
    match = WIKIWORD.search(contents)
    while match is not None:
        start, end = match.span()
        output.append(contents[:start])
        output.append('[{link}]({link})'.format(
                        link=match.group()))
        contents = contents[end:]
        match = WIKIWORD.search(contents)
    output.append(contents)
    return ''.join(output)

def process_markdown(contents):
    "Filters the contents through Markdown"
    proc = subprocess.Popen(['markdown'], stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE)
    proc.stdin.write(bytes(contents, 'utf-8'))
    proc.stdin.flush()
    proc.stdin.close()
    proc.wait()
    return str(proc.stdout.read(), 'utf-8')

# Make sure that a particular piece of text is a valid Wiki link
WIKIWORD = re.compile('[A-Z][a-z0-9]+([A-Z][a-z0-9]+)+')
class WikiApp:
    def __init__(self):
        self.db = None
        self.curs = None

    def open_database(self):
        "Opens the Sqlite database used as a data store"
        database_path = srctree.module_options.get('database', '$/wiki/pages.db')
        database_path = database_path.replace('$', srctree.static_path)
        self.db = sqlite3.connect(database_path)
        self.curs = self.db.cursor()
        self.curs.execute('CREATE TABLE IF NOT EXISTS '
                          'pages '
                          '(title VARCHAR PRIMARY KEY, content BLOB)')

    def list_wiki_pages(self):
        "Gets a list of Wiki pages"
        self.curs.execute('SELECT title FROM pages')
        return set(map(lambda x: x[0], self.curs))

    def read_wiki_page(self, title):
        "Gets the UTF-8 encoded text of a Wiki page, or None"
        self.curs.execute('SELECT content FROM pages WHERE title = ?',
                          (title,))
        try:
            (data,) = next(self.curs)
            return decompress(data)
        except StopIteration:
            return None

    def write_wiki_page(self, title, content):
        "Writes the content of a Wiki page"
        if not WIKIWORD.search(title):
            # Don't write any invalid titles, since they are not actually
            # capable of being linked.
            return

        if title in self.list_wiki_pages():
            self.delete_wiki_page(title)

        data = compress(content)
        self.curs.execute('INSERT INTO pages VALUES (?, ?)', 
                          (title, data))
        self.db.commit()

    def delete_wiki_page(self, title):
        "Deletes a Wiki page"
        self.curs.execute('DELETE FROM pages WHERE title = ?', (title,))
        self.db.commit()

    def do_submit_page(self, variables):
        "This actually takes the POSTed data from /wiki/submit"
        if variables['PATH_INFO'] != '/wiki/submit':
            return srctree.NotFound()

        post_data = read_post(variables)
        self.write_wiki_page(post_data['title'], post_data['content'])
        return srctree.Redirect('/wiki')

    def get_page(self, variables):
        "Gets the content of the Wiki page via /wiki/page"
        path = variables['PATH_INFO'].replace('/wiki/page/', '')
        title = WIKIWORD.match(path)
        if title is None:
            return srctree.NotFound()

        title = title.group()
        contents = self.read_wiki_page(title)
        if contents is None:
            # Going to a nonexistant page goes to an editing page instead
            # of creating a stub.
            template = srctree.load_template(
                    srctree.static_path + '/wiki/edit.html',
                    title=title,
                    contents='')
            return srctree.Endpoint(200, template, 'text/html')

        escaped_contents = html.escape(contents)
        linked_contents = build_links(escaped_contents)
        rendered_contents = process_markdown(linked_contents)
        template = srctree.load_template(
                srctree.static_path + '/wiki/view.html',
                title=title,
                contents=rendered_contents)
    
        return srctree.Endpoint(200, template, 'text/html')

    def edit_page(self, variables):
        "Opens up an editing page"
        path = variables['PATH_INFO'].replace('/wiki/edit/', '')
        title = WIKIWORD.match(path)
        if title is None:
            template = srctree.load_template(
                    srctree.static_path + '/wiki/edit.html',
                    title='EnterAWikiTitleHere',
                    contents='')
            return srctree.Endpoint(200, template, 'text/html')

        title = title.group()
        contents = self.read_wiki_page(title) or ''

        template = srctree.load_template(
                srctree.static_path + '/wiki/edit.html',
                title=title,
                contents=contents)
        return srctree.Endpoint(200, template, 'text/html')

    def delete_page(self, variables):
        "Deletes a page and redirects to the main page"
        path = variables['PATH_INFO'].replace('/wiki/delete/', '')
        title = WIKIWORD.match(path)
        if title is None:
            return srctree.NotFound()
        
        title = title.group()
        self.delete_wiki_page(title)
        return srctree.Redirect('/wiki')

    def index_page(self, variables):
        "Builds an index page, with an editor at the bottom"
        urls = ['!/wiki/edit/']
        
        for title in self.list_wiki_pages():
            urls.append('/wiki/page/' + title)
        return srctree.Group(*urls)

def load():
    wiki = WikiApp()
    wiki.open_database()
    srctree.register('/wiki', wiki.index_page)
    srctree.register('/wiki/submit', wiki.do_submit_page, hide=True)
    srctree.register('/wiki/page', wiki.get_page, hide=True)
    srctree.register('/wiki/edit', wiki.edit_page)
    srctree.register('/wiki/delete', wiki.delete_page, hide=True)
