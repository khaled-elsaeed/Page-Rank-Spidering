import sqlite3
import urllib.error
import ssl
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
from bs4 import BeautifulSoup

# Ignore SSL certificate errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def create_tables(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS Pages
        (id INTEGER PRIMARY KEY, url TEXT UNIQUE, html TEXT,
         error INTEGER, old_rank REAL, new_rank REAL)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS Links
        (from_id INTEGER, to_id INTEGER, UNIQUE(from_id, to_id))''')

    cur.execute('''CREATE TABLE IF NOT EXISTS Webs (url TEXT UNIQUE)''')

def check_crawl_in_progress(cur):
    cur.execute('SELECT id, url FROM Pages WHERE html IS NULL AND error IS NULL ORDER BY RANDOM() LIMIT 1')
    row = cur.fetchone()
    if row is not None:
        print("Restarting existing crawl. Remove spider.sqlite to start a fresh crawl.")
        return True
    return False

def initialize_crawl(cur, conn):
    starturl = input('Enter web url or enter: ')
    if len(starturl) < 1: starturl = 'http://www.dr-chuck.com/'
    if starturl.endswith('/'): starturl = starturl[:-1]
    web = starturl
    if starturl.endswith(('.htm', '.html')):
        pos = starturl.rfind('/')
        web = starturl[:pos]

    if len(web) > 1:
        cur.execute('INSERT OR IGNORE INTO Webs (url) VALUES (?)', (web,))
        cur.execute('INSERT OR IGNORE INTO Pages (url, html, new_rank) VALUES (?, NULL, 1.0)', (starturl,))
        conn.commit()

def get_current_webs(cur):
    cur.execute('''SELECT url FROM Webs''')
    webs = [str(row[0]) for row in cur]
    return webs

def retrieve_html_page(cur):
    cur.execute('SELECT id, url FROM Pages WHERE html IS NULL AND error IS NULL ORDER BY RANDOM() LIMIT 1')
    row = cur.fetchone()
    if row is not None:
        return row[0], row[1]
    return None, None

def update_retrieved_page(cur, conn, url, html):
    cur.execute('INSERT OR IGNORE INTO Pages (url, html, new_rank) VALUES (?, NULL, 1.0)', (url,))
    cur.execute('UPDATE Pages SET html=? WHERE url=?', (memoryview(html), url))
    conn.commit()

def crawl_page(cur, conn, fromid, url, webs):
    cur.execute('DELETE FROM Links WHERE from_id=?', (fromid,))

    try:
        document = urlopen(url, context=ctx)
        html = document.read()

        if document.getcode() != 200:
            print("Error on page:", document.getcode())
            cur.execute('UPDATE Pages SET error=? WHERE url=?', (document.getcode(), url))

        if 'text/html' != document.info().get_content_type():
            print("Ignore non text/html page")
            cur.execute('DELETE FROM Pages WHERE url=?', (url,))
            conn.commit()
            return

        print('('+str(len(html))+')', end=' ')

        soup = BeautifulSoup(html, "html.parser")
    except KeyboardInterrupt:
        print('\nProgram interrupted by user...')
        raise KeyboardInterrupt
    except:
        print("Unable to retrieve or parse page")
        cur.execute('UPDATE Pages SET error=-1 WHERE url=?', (url,))
        conn.commit()
        return

    update_retrieved_page(cur, conn, url, html)

    # Retrieve all anchor tags
    tags = soup('a')
    count = 0
    for tag in tags:
        href = tag.get('href', None)
        if href is None: continue
        
        # Resolve relative references like href="/contact"
        up = urlparse(href)
        if len(up.scheme) < 1:
            href = urljoin(url, href)
        ipos = href.find('#')
        if ipos > 1: href = href[:ipos]
        if href.endswith(('.png', '.jpg', '.gif')): continue
        if href.endswith('/'): href = href[:-1]
        if len(href) < 1: continue

        # Check if the URL is in any of the webs
        found = any(href.startswith(web) for web in webs)
        if not found: continue

        # Add the link to the database
        cur.execute('INSERT OR IGNORE INTO Pages (url, html, new_rank) VALUES (?, NULL, 1.0)', (href,))
        count += 1
        conn.commit()

        cur.execute('SELECT id FROM Pages WHERE url=? LIMIT 1', (href,))
        try:
            row = cur.fetchone()
            toid = row[0]
        except:
            print('Could not retrieve id')
            continue

        cur.execute('INSERT OR IGNORE INTO Links (from_id, to_id) VALUES (?, ?)', (fromid, toid))

    print(count)

def main():
    conn = sqlite3.connect('spider.sqlite')
    cur = conn.cursor()

    create_tables(cur)

    if check_crawl_in_progress(cur):
        cur.close()
        return

    initialize_crawl(cur, conn)
    webs = get_current_webs(cur)
    print(webs)

    many = 0
    while True:
        if many < 1:
            sval = input('How many pages:')
            if len(sval) < 1: break
            many = int(sval)
        many = many - 1

        fromid, url = retrieve_html_page(cur)
        if fromid is None or url is None:
            print('No unretrieved HTML pages found')
            many = 0
            break

        print(fromid, url, end=' ')
        crawl_page(cur, conn, fromid, url, webs)

    cur.close()

if __name__ == "__main__":
    main()
