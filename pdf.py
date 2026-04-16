#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║    ██╗   ██╗███╗   ██╗██████╗ ███████╗██╗  ██╗                              ║
║    ██║   ██║████╗  ██║██╔══██╗██╔════╝╚██╗██╔╝                              ║
║    ██║   ██║██╔██╗ ██║██████╔╝█████╗   ╚███╔╝                               ║
║    ██║   ██║██║╚██╗██║██╔═══╝ ██╔══╝   ██╔██╗                               ║
║    ╚██████╔╝██║ ╚████║██║     ███████╗██╔╝ ██╗                              ║
║     ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚══════╝╚═╝  ╚═╝                              ║
║                                                                               ║
║    ██████╗ ███████╗ ██████╗  █████╗ ███████╗██╗   ██╗███████╗               ║
║    ██╔══██╗██╔════╝██╔════╝ ██╔══██╗██╔════╝██║   ██║██╔════╝               ║
║    ██████╔╝█████╗  ██║  ███╗███████║███████╗██║   ██║███████╗               ║
║    ██╔═══╝ ██╔══╝  ██║   ██║██╔══██║╚════██║██║   ██║╚════██║               ║
║    ██║     ███████╗╚██████╔╝██║  ██║███████║╚██████╔╝███████║               ║
║    ╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝               ║
║                                                                               ║
║              JUNPEX PEGASUS - SUPER ACADEMIC SEARCH ENGINE                    ║
║               Pencarian Jurnal Ilmiah Seperti Google | Open Source           ║
║                           Zero Failure | Multi-Source                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import subprocess
import time
import requests
import random
import hashlib
import json
import re
import warnings
import urllib3
import threading
import queue
import signal
import pickle
import gzip
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Set, Any
import argparse

# Nonaktifkan warning
warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== INSTALL DEPENDENCIES ====================
def install_dependencies():
    deps = ['requests', 'beautifulsoup4', 'tqdm', 'lxml']
    print("📦 Installing dependencies...")
    for dep in deps:
        try:
            __import__(dep.replace('-', '_'))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "-q", "--no-warn-script-location"])

install_dependencies()

from bs4 import BeautifulSoup
from tqdm import tqdm

# Warna ANSI
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

# ==================== SIMPLE DATABASE WITH SQLITE ====================
class SearchDatabase:
    """Database untuk menyimpan indeks pencarian"""
    
    def __init__(self, db_path="junpex_search.db"):
        self.db_path = db_path
        
        # Pastikan folder tempat database ada
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        self._init_db()
    
    def _init_db(self):
        """Inisialisasi database SQLite"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Tabel untuk jurnal
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS journals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    authors TEXT,
                    abstract TEXT,
                    year INTEGER,
                    journal TEXT,
                    doi TEXT,
                    source TEXT,
                    country TEXT,
                    download_path TEXT,
                    content_hash TEXT,
                    search_keywords TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabel untuk statistik pencarian
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT,
                    results_count INTEGER,
                    search_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            print(Colors.GREEN + "✅ Database initialized successfully" + Colors.END)
            
        except Exception as e:
            print(Colors.YELLOW + f"⚠️ Database warning: {e} (using memory only)" + Colors.END)
            self.conn = None
    
    def add_journal(self, journal_data):
        """Tambahkan jurnal ke database"""
        if not self.conn:
            return None
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO journals 
                (url, title, authors, abstract, year, journal, doi, source, country, download_path, content_hash, search_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                journal_data.get('url'),
                journal_data.get('title'),
                json.dumps(journal_data.get('authors', [])),
                journal_data.get('abstract', ''),
                journal_data.get('year'),
                journal_data.get('journal', ''),
                journal_data.get('doi', ''),
                journal_data.get('source', ''),
                journal_data.get('country', ''),
                journal_data.get('download_path', ''),
                journal_data.get('content_hash', ''),
                journal_data.get('search_keywords', '')
            ))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            return None
    
    def search_journals(self, query, year_from=None, year_to=None, limit=100):
        """Cari jurnal berdasarkan query"""
        if not self.conn:
            return []
        
        words = query.lower().split()
        
        # Build query
        sql = '''
            SELECT DISTINCT j.* FROM journals j
            WHERE 1=1
        '''
        params = []
        
        # Full text search
        if words:
            conditions = []
            for word in words:
                conditions.append("(j.title LIKE ? OR j.abstract LIKE ? OR j.search_keywords LIKE ?)")
                params.extend([f'%{word}%', f'%{word}%', f'%{word}%'])
            sql += " AND " + " AND ".join(conditions)
        
        # Filter tahun
        if year_from:
            sql += " AND j.year >= ?"
            params.append(year_from)
        if year_to:
            sql += " AND j.year <= ?"
            params.append(year_to)
        
        sql += " ORDER BY j.year DESC LIMIT ?"
        params.append(limit)
        
        try:
            self.cursor.execute(sql, params)
            return self.cursor.fetchall()
        except:
            return []
    
    def save_search_stats(self, query, results_count, search_time):
        """Simpan statistik pencarian"""
        if not self.conn:
            return
        try:
            self.cursor.execute('''
                INSERT INTO search_stats (query, results_count, search_time)
                VALUES (?, ?, ?)
            ''', (query, results_count, search_time))
            self.conn.commit()
        except:
            pass
    
    def close(self):
        if self.conn:
            self.conn.close()

# ==================== GOOGLE-LIKE SEARCH ENGINE ====================
class JunpexSearchEngine:
    """Search engine seperti Google untuk jurnal akademik"""
    
    # Academic search sources
    ACADEMIC_SOURCES = [
        # Major publishers
        {'name': 'ScienceDirect', 'domain': 'sciencedirect.com', 'base_url': 'https://www.sciencedirect.com/search?qs={}', 'type': 'publisher'},
        {'name': 'Springer', 'domain': 'springer.com', 'base_url': 'https://link.springer.com/search?query={}', 'type': 'publisher'},
        {'name': 'Taylor & Francis', 'domain': 'tandfonline.com', 'base_url': 'https://www.tandfonline.com/action/doSearch?AllField={}', 'type': 'publisher'},
        {'name': 'Wiley', 'domain': 'onlinelibrary.wiley.com', 'base_url': 'https://onlinelibrary.wiley.com/action/doSearch?AllField={}', 'type': 'publisher'},
        {'name': 'MDPI', 'domain': 'mdpi.com', 'base_url': 'https://www.mdpi.com/search?q={}', 'type': 'publisher'},
        {'name': 'Frontiers', 'domain': 'frontiersin.org', 'base_url': 'https://www.frontiersin.org/search?q={}', 'type': 'publisher'},
        
        # Academic aggregators
        {'name': 'Semantic Scholar', 'domain': 'semanticscholar.org', 'base_url': 'https://www.semanticscholar.org/search?q={}', 'type': 'aggregator'},
        {'name': 'Crossref', 'domain': 'crossref.org', 'base_url': 'https://search.crossref.org/?q={}', 'type': 'aggregator'},
        {'name': 'CORE', 'domain': 'core.ac.uk', 'base_url': 'https://core.ac.uk/search?q={}', 'type': 'aggregator'},
        {'name': 'BASE', 'domain': 'base-search.net', 'base_url': 'https://www.base-search.net/Search/Results?q={}', 'type': 'aggregator'},
        
        # Open Access
        {'name': 'DOAJ', 'domain': 'doaj.org', 'base_url': 'https://doaj.org/search?q={}', 'type': 'oa'},
        {'name': 'arXiv', 'domain': 'arxiv.org', 'base_url': 'https://arxiv.org/search/?query={}', 'type': 'preprint'},
        {'name': 'PubMed Central', 'domain': 'ncbi.nlm.nih.gov', 'base_url': 'https://www.ncbi.nlm.nih.gov/pmc/?term={}', 'type': 'medical'},
        
        # Social academic
        {'name': 'ResearchGate', 'domain': 'researchgate.net', 'base_url': 'https://www.researchgate.net/search/publication?q={}', 'type': 'social'},
        
        # Indonesian universities
        {'name': 'UI Repository', 'domain': 'lib.ui.ac.id', 'base_url': 'https://lib.ui.ac.id/search?q={}', 'type': 'univ', 'country': 'Indonesia'},
        {'name': 'ITB Repository', 'domain': 'digilib.itb.ac.id', 'base_url': 'https://digilib.itb.ac.id/search?q={}', 'type': 'univ', 'country': 'Indonesia'},
        {'name': 'UGM Repository', 'domain': 'etd.repository.ugm.ac.id', 'base_url': 'https://etd.repository.ugm.ac.id/search?q={}', 'type': 'univ', 'country': 'Indonesia'},
        {'name': 'ITS Repository', 'domain': 'digilib.its.ac.id', 'base_url': 'https://digilib.its.ac.id/search?q={}', 'type': 'univ', 'country': 'Indonesia'},
        {'name': 'UB Repository', 'domain': 'repository.ub.ac.id', 'base_url': 'https://repository.ub.ac.id/search?q={}', 'type': 'univ', 'country': 'Indonesia'},
        
        # International universities
        {'name': 'MIT DSpace', 'domain': 'dspace.mit.edu', 'base_url': 'https://dspace.mit.edu/search?q={}', 'type': 'univ', 'country': 'USA'},
        {'name': 'Stanford', 'domain': 'stacks.stanford.edu', 'base_url': 'https://stacks.stanford.edu/search?q={}', 'type': 'univ', 'country': 'USA'},
        {'name': 'Harvard DASH', 'domain': 'dash.harvard.edu', 'base_url': 'https://dash.harvard.edu/search?q={}', 'type': 'univ', 'country': 'USA'},
        {'name': 'Cambridge', 'domain': 'repository.cam.ac.uk', 'base_url': 'https://www.repository.cam.ac.uk/search?q={}', 'type': 'univ', 'country': 'UK'},
        {'name': 'Oxford ORA', 'domain': 'ora.ox.ac.uk', 'base_url': 'https://ora.ox.ac.uk/search?q={}', 'type': 'univ', 'country': 'UK'},
        {'name': 'NUS ScholarBank', 'domain': 'scholarbank.nus.edu.sg', 'base_url': 'https://scholarbank.nus.edu.sg/search?q={}', 'type': 'univ', 'country': 'Singapore'},
        {'name': 'Tokyo Univ', 'domain': 'repository.dl.itc.u-tokyo.ac.jp', 'base_url': 'https://repository.dl.itc.u-tokyo.ac.jp/search?q={}', 'type': 'univ', 'country': 'Japan'},
        {'name': 'Seoul National', 'domain': 's-space.snu.ac.kr', 'base_url': 'https://s-space.snu.ac.kr/search?q={}', 'type': 'univ', 'country': 'Korea'},
    ]
    
    def __init__(self, output_dir="junpex_journals", max_workers=100):
        self.output_dir = output_dir
        self.max_workers = min(max_workers, 100)
        
        # Buat folder output
        os.makedirs(output_dir, exist_ok=True)
        
        # Database
        db_path = os.path.join(output_dir, "junpex_search.db")
        self.db = SearchDatabase(db_path)
        
        # Queue system
        self.search_queue = queue.Queue()
        self.download_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # Cache
        self.url_cache = set()
        self.content_hash_cache = set()
        self.cache_file = os.path.join(output_dir, "Cache", "url_cache.pkl")
        self.hash_file = os.path.join(output_dir, "Cache", "hash_cache.pkl")
        
        # Stats
        self.stats = {
            'searches': 0,
            'results_found': 0,
            'downloaded': 0,
            'failed': 0,
            'by_source': defaultdict(int),
            'by_year': defaultdict(int),
            'by_country': defaultdict(int)
        }
        
        # Threading
        self.running = True
        self.lock = threading.Lock()
        
        # Session pool
        self.session_pool = queue.Queue()
        self._init_session_pool(50)
        
        # Create folders
        self._create_folders()
        
        # Load cache
        self._load_cache()
    
    def _init_session_pool(self, size):
        """Initialize session pool"""
        for _ in range(size):
            session = requests.Session()
            session.verify = False
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            })
            self.session_pool.put(session)
    
    def _get_session(self):
        try:
            return self.session_pool.get(timeout=5)
        except:
            return requests.Session()
    
    def _return_session(self, session):
        try:
            self.session_pool.put_nowait(session)
        except:
            pass
    
    def _create_folders(self):
        """Create folder structure"""
        folders = [
            self.output_dir,
            os.path.join(self.output_dir, "PDF"),
            os.path.join(self.output_dir, "PDF", "By_Year"),
            os.path.join(self.output_dir, "PDF", "By_Country"),
            os.path.join(self.output_dir, "PDF", "By_Source"),
            os.path.join(self.output_dir, "Cache"),
            os.path.join(self.output_dir, "Logs"),
        ]
        for f in folders:
            os.makedirs(f, exist_ok=True)
    
    def _load_cache(self):
        """Load cache from files"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    self.url_cache = pickle.load(f)
                print(Colors.GREEN + f"📦 Loaded {len(self.url_cache)} URLs from cache" + Colors.END)
            except:
                pass
        
        if os.path.exists(self.hash_file):
            try:
                with open(self.hash_file, 'rb') as f:
                    self.content_hash_cache = pickle.load(f)
                print(Colors.GREEN + f"📦 Loaded {len(self.content_hash_cache)} content hashes from cache" + Colors.END)
            except:
                pass
    
    def _save_cache(self):
        """Save cache to files"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.url_cache, f)
            with open(self.hash_file, 'wb') as f:
                pickle.dump(self.content_hash_cache, f)
        except:
            pass
    
    def extract_pdf_links_from_html(self, html, base_url, source_info, query):
        """Extract PDF links from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except:
            soup = BeautifulSoup(html, 'html.parser')
        
        pdf_links = []
        
        # Patterns for PDF detection
        pdf_patterns = ['.pdf', '/pdf/', 'download', 'fulltext', 'article-pdf', 'epdf']
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            text = link.text.lower()
            full_url = urljoin(base_url, link['href'])
            
            is_pdf = any(p in href for p in pdf_patterns) or 'pdf' in text
            
            if is_pdf and full_url.startswith(('http://', 'https://')):
                # Try to extract year from URL or context
                year = None
                year_match = re.search(r'(19|20)\d{2}', full_url)
                if year_match:
                    year = int(year_match.group())
                
                pdf_links.append({
                    'url': full_url,
                    'title': link.text.strip()[:200] or "Untitled",
                    'source': source_info['name'],
                    'source_type': source_info.get('type', 'unknown'),
                    'country': source_info.get('country', 'International'),
                    'year': year,
                    'query': query
                })
                
                if len(pdf_links) >= 3:
                    break
        
        return pdf_links
    
    def search_worker(self, query, year_filter=None):
        """Worker untuk melakukan pencarian"""
        results = []
        session = self._get_session()
        
        # Pilih sumber
        sources_to_search = self.ACADEMIC_SOURCES[:20]
        
        for source in sources_to_search:
            if not self.running:
                break
            
            try:
                search_url = source['base_url'].format(quote(query))
                
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                resp = session.get(search_url, headers=headers, timeout=15, verify=False)
                
                if resp.status_code == 200:
                    links = self.extract_pdf_links_from_html(resp.text, search_url, source, query)
                    
                    for link in links:
                        # Cek duplikasi URL
                        if link['url'] in self.url_cache:
                            continue
                        
                        self.url_cache.add(link['url'])
                        results.append(link)
                        
                        with self.lock:
                            self.stats['results_found'] += 1
                            self.stats['by_source'][source['name']] += 1
                            if link['year']:
                                self.stats['by_year'][link['year']] += 1
                            self.stats['by_country'][link.get('country', 'Unknown')] += 1
                
                time.sleep(0.5)  # Delay
                
            except Exception as e:
                continue
        
        self._return_session(session)
        return results
    
    def search(self, query, year_from=None, year_to=None, max_results=100):
        """Fungsi utama pencarian seperti Google"""
        print(Colors.CYAN + Colors.BOLD + "\n" + "=" * 80)
        print(Colors.YELLOW + Colors.BOLD + f"🔍 MENCARI: {query}")
        print(Colors.CYAN + Colors.BOLD + "=" * 80)
        
        start_time = time.time()
        
        print(Colors.GREEN + "📡 Mengakses 20+ sumber jurnal...")
        
        # Lakukan pencarian paralel
        all_results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.search_worker, query, None)]
            
            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)
                print(Colors.DIM + f"   Ditemukan {len(results)} PDF..." + Colors.END)
        
        # Filter berdasarkan tahun
        if year_from or year_to:
            filtered = []
            for r in all_results:
                year = r.get('year')
                if year:
                    if year_from and year < year_from:
                        continue
                    if year_to and year > year_to:
                        continue
                filtered.append(r)
            all_results = filtered
        
        # Batasi hasil
        all_results = all_results[:max_results * 2]
        
        search_time = time.time() - start_time
        
        # Simpan statistik
        self.db.save_search_stats(query, len(all_results), search_time)
        
        print(Colors.GREEN + f"\n✅ DITEMUKAN: {len(all_results)} PDF dalam {search_time:.1f} detik")
        
        if not all_results:
            print(Colors.YELLOW + "⚠️ Tidak ditemukan hasil. Coba dengan kata kunci lain.")
            return []
        
        # Tampilkan hasil
        print(Colors.CYAN + "\n📋 HASIL PENCARIAN:")
        print(Colors.CYAN + "-" * 80)
        
        for i, result in enumerate(all_results[:20], 1):
            title = result['title'][:70] + "..." if len(result['title']) > 70 else result['title']
            year_str = f"({result['year']})" if result.get('year') else ""
            print(Colors.GREEN + f"{i:3}. " + Colors.WHITE + f"{title}")
            print(Colors.DIM + f"     📄 Sumber: {result['source']} {year_str} | Negara: {result.get('country', 'N/A')}" + Colors.END)
            print()
        
        return all_results
    
    def download_worker(self):
        """Worker untuk mendownload PDF"""
        session = self._get_session()
        
        while self.running:
            try:
                pdf_info = self.download_queue.get(timeout=2)
            except queue.Empty:
                continue
            
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                resp = session.get(pdf_info['url'], headers=headers, timeout=20, verify=False, stream=True)
                
                if resp.status_code == 200:
                    content = b''
                    for chunk in resp.iter_content(chunk_size=16384):
                        content += chunk
                        if len(content) > 50 * 1024 * 1024:  # Max 50MB
                            break
                    
                    # Validasi PDF
                    if content[:4] == b'%PDF' and len(content) > 10000:
                        content_hash = hashlib.md5(content).hexdigest()
                        
                        if content_hash in self.content_hash_cache:
                            self.download_queue.task_done()
                            continue
                        
                        self.content_hash_cache.add(content_hash)
                        
                        # Buat nama file
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_title = re.sub(r'[^\w\s-]', '', pdf_info['title'])[:60]
                        safe_title = re.sub(r'[-\s]+', '_', safe_title)
                        
                        # Tentukan folder
                        if pdf_info.get('year'):
                            year_dir = os.path.join(self.output_dir, "PDF", "By_Year", str(pdf_info['year']))
                        else:
                            year_dir = os.path.join(self.output_dir, "PDF", "General")
                        
                        os.makedirs(year_dir, exist_ok=True)
                        
                        filename = f"{timestamp}_{safe_title}.pdf"
                        filepath = os.path.join(year_dir, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        
                        # Simpan ke database
                        journal_data = {
                            'url': pdf_info['url'],
                            'title': pdf_info['title'],
                            'year': pdf_info.get('year'),
                            'source': pdf_info['source'],
                            'country': pdf_info.get('country'),
                            'download_path': filepath,
                            'content_hash': content_hash,
                            'search_keywords': pdf_info.get('query', '')
                        }
                        self.db.add_journal(journal_data)
                        
                        with self.lock:
                            self.stats['downloaded'] += 1
                        
                        self.result_queue.put({
                            'success': True,
                            'file': filename,
                            'title': pdf_info['title']
                        })
                    else:
                        raise Exception("Not a valid PDF")
                
            except Exception as e:
                with self.lock:
                    self.stats['failed'] += 1
            
            finally:
                try:
                    self.download_queue.task_done()
                except:
                    pass
        
        self._return_session(session)
    
    def download_results(self, results, max_download=30):
        """Download hasil pencarian"""
        if not results:
            print(Colors.YELLOW + "⚠️ Tidak ada hasil untuk didownload")
            return
        
        max_download = min(max_download, len(results))
        
        print(Colors.CYAN + Colors.BOLD + "\n" + "=" * 80)
        print(Colors.YELLOW + Colors.BOLD + f"⬇️ DOWNLOAD {max_download} PDF")
        print(Colors.CYAN + Colors.BOLD + "=" * 80)
        
        # Reset stats
        self.stats['downloaded'] = 0
        self.stats['failed'] = 0
        
        # Masukkan ke queue
        for result in results[:max_download]:
            self.download_queue.put(result)
        
        # Start download workers
        workers = []
        num_workers = min(self.max_workers, 10)
        for _ in range(num_workers):
            t = threading.Thread(target=self.download_worker, daemon=True)
            t.start()
            workers.append(t)
        
        # Progress bar
        pbar = tqdm(total=max_download, desc="Downloading", unit="file")
        
        start_time = time.time()
        while self.stats['downloaded'] + self.stats['failed'] < max_download:
            time.sleep(0.5)
            pbar.n = self.stats['downloaded']
            pbar.set_postfix({
                "Success": self.stats['downloaded'],
                "Failed": self.stats['failed']
            })
            pbar.refresh()
            
            if time.time() - start_time > 300:  # Timeout 5 menit
                break
        
        pbar.close()
        
        elapsed = time.time() - start_time
        
        print(Colors.GREEN + f"\n✅ DOWNLOAD SELESAI!")
        print(Colors.GREEN + f"   ✅ Berhasil: {self.stats['downloaded']} file")
        print(Colors.RED + f"   ❌ Gagal: {self.stats['failed']} file")
        print(Colors.CYAN + f"   ⏱️  Waktu: {elapsed:.1f} detik")
        print(Colors.CYAN + f"   📁 Folder: {os.path.abspath(self.output_dir)}/PDF/")
    
    def interactive_mode(self):
        """Mode interaktif seperti search engine"""
        print(Colors.CYAN + Colors.BOLD + "\n" + "=" * 80)
        print(Colors.YELLOW + Colors.BOLD + "🌟 JUNPEX PEGASUS - SUPER ACADEMIC SEARCH ENGINE 🌟")
        print(Colors.CYAN + Colors.BOLD + "=" * 80)
        print(Colors.GREEN + """
╔══════════════════════════════════════════════════════════════╗
║  FITUR:                                                      ║
║  • Cari jurnal ilmiah dari SELURUH DUNIA                    ║
║  • Filter berdasarkan TAHUN publikasi                       ║
║  • Download PDF otomatis                                    ║
║  • Anti-duplikat otomatis                                   ║
║  • Bisa untuk SEMUA topik (tidak terbatas)                  ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        while True:
            print(Colors.CYAN + "\n" + "=" * 80)
            print(Colors.YELLOW + "🔍 MASUKKAN PENCARIAN (atau ketik 'exit' untuk keluar):")
            print(Colors.DIM + "   Contoh: 'machine learning 2023' atau 'self compacting concrete'" + Colors.END)
            
            query = input(Colors.GREEN + ">>> " + Colors.WHITE).strip()
            
            if query.lower() in ['exit', 'quit', 'q']:
                print(Colors.YELLOW + "\n👋 Terima kasih menggunakan JUNPEX PEGASUS!")
                break
            
            if not query:
                continue
            
            # Filter tahun
            print(Colors.CYAN + "\n📅 FILTER TAHUN (opsional):")
            print(Colors.DIM + "   Format: 2020-2024 atau 2020 atau tekan Enter untuk semua" + Colors.END)
            year_filter = input(Colors.GREEN + ">>> " + Colors.WHITE).strip()
            
            year_from = None
            year_to = None
            
            if year_filter:
                if '-' in year_filter:
                    parts = year_filter.split('-')
                    year_from = int(parts[0]) if parts[0] else None
                    year_to = int(parts[1]) if len(parts) > 1 and parts[1] else None
                else:
                    year_from = year_to = int(year_filter)
            
            # Jumlah hasil
            print(Colors.CYAN + "\n📊 JUMLAH HASIL YANG DICARI (default 50):")
            max_results = input(Colors.GREEN + ">>> " + Colors.WHITE).strip()
            max_results = int(max_results) if max_results else 50
            
            # Lakukan pencarian
            results = self.search(query, year_from, year_to, max_results)
            
            if results:
                print(Colors.CYAN + "\n⬇️ DOWNLOAD PDF? (y/n):")
                download_choice = input(Colors.GREEN + ">>> " + Colors.WHITE).strip().lower()
                
                if download_choice == 'y':
                    max_download = input(Colors.GREEN + "Jumlah max download (default 20): " + Colors.WHITE).strip()
                    max_download = int(max_download) if max_download else 20
                    self.download_results(results, max_download)
    
    def close(self):
        """Cleanup"""
        self.running = False
        self._save_cache()
        self.db.close()

# ==================== MAIN ====================
def main():
    parser = argparse.ArgumentParser(description='JUNPEX PEGASUS - Super Academic Search Engine')
    parser.add_argument('--query', '-q', type=str, help='Query pencarian langsung')
    parser.add_argument('--year-from', type=int, help='Tahun awal')
    parser.add_argument('--year-to', type=int, help='Tahun akhir')
    parser.add_argument('--max-results', '-m', type=int, default=50, help='Max hasil (default: 50)')
    parser.add_argument('--download', '-d', type=int, default=0, help='Jumlah download (0 = tidak download)')
    parser.add_argument('--output', '-o', type=str, default='junpex_journals', help='Folder output')
    parser.add_argument('--workers', '-w', type=int, default=50, help='Jumlah thread')
    
    args = parser.parse_args()
    
    # Inisialisasi search engine
    engine = JunpexSearchEngine(output_dir=args.output, max_workers=args.workers)
    
    try:
        if args.query:
            # Mode command line
            print(Colors.CYAN + Colors.BOLD + "\n" + "=" * 80)
            print(Colors.YELLOW + Colors.BOLD + f"🔍 JUNPEX PEGASUS - Mencari: {args.query}")
            print(Colors.CYAN + Colors.BOLD + "=" * 80)
            
            results = engine.search(args.query, args.year_from, args.year_to, args.max_results)
            
            if results and args.download > 0:
                engine.download_results(results, args.download)
        else:
            # Mode interaktif
            engine.interactive_mode()
    finally:
        engine.close()

# Import sqlite3 only when needed
import sqlite3

if __name__ == "__main__":
    main()