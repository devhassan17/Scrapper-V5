from flask import Flask, render_template, request, redirect, url_for
import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
from threading import Thread

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sitemap_urls
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS business_links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  sitemap_url_id INTEGER,
                  business_name TEXT,
                  business_url TEXT,
                  FOREIGN KEY(sitemap_url_id) REFERENCES sitemap_urls(id))''')
    conn.commit()
    conn.close()

init_db()

def fetch_sitemap_urls(sitemap_url):
    try:
        response = requests.get(sitemap_url)
        root = ET.fromstring(response.content)
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [url.text for url in root.findall('ns:url/ns:loc', namespace)]
        return urls
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return []

def scrape_business_links(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        business_links = []
        
        # Look for business links - this selector might need adjustment
        for link in soup.select('a[href*="/bedrijf/"]'):
            business_name = link.text.strip()
            business_url = urljoin(url, link['href'])
            business_links.append((business_name, business_url))
        
        return business_links
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

def store_data_in_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    
    # Clear existing data
    c.execute("DELETE FROM business_links")
    c.execute("DELETE FROM sitemap_urls")
    conn.commit()
    
    sitemap_url = "https://stadsgids.nl/plaats-sitemap.xml"
    sitemap_urls = fetch_sitemap_urls(sitemap_url)
    
    for url in sitemap_urls:
        # Insert sitemap URL
        c.execute("INSERT INTO sitemap_urls (url) VALUES (?)", (url,))
        sitemap_url_id = c.lastrowid
        
        # Scrape business links
        business_links = scrape_business_links(url)
        
        # Insert business links
        for name, business_url in business_links:
            c.execute("INSERT INTO business_links (sitemap_url_id, business_name, business_url) VALUES (?, ?, ?)",
                     (sitemap_url_id, name, business_url))
        
        conn.commit()
    
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch', methods=['POST'])
def fetch_urls():
    # Run the scraping in a separate thread to avoid timeout
    thread = Thread(target=store_data_in_db)
    thread.start()
    return redirect(url_for('show_data'))

@app.route('/data')
def show_data():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    
    # Get all business links with their associated sitemap URL
    c.execute('''SELECT s.url, b.business_name, b.business_url 
                 FROM business_links b
                 JOIN sitemap_urls s ON b.sitemap_url_id = s.id
                 ORDER BY s.url, b.business_name''')
    business_links = c.fetchall()
    
    conn.close()
    
    return render_template('data.html', business_links=business_links)

if __name__ == '__main__':
    app.run(debug=True)