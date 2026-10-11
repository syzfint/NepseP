import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

import os
import logging
from dotenv import load_dotenv
import json
import time
from datetime import timedelta,datetime
import uuid
load_dotenv()


import logging
# logging.basicConfig(level=logging.DEBUG)

class DbService:
    _instance = None
    _initialized = False


    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DbService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.TARGET_TIMEZONE = "Asia/Kathmandu"

        if not self._initialized:
            self.connection_pool = self.create_connection_pool()
            if self.connection_pool:
                self.recycle_interval = timedelta(minutes=30)
                self.last_recycle = datetime.now()
                

                self.warmup_pool()
                # self.set_database_timezone()
                self.set_kathmandu_timezone()
                self.create_extensions()
                self.create_tables()  # creates embeddings table
                self.create_events_table()
                self.create_summary_table()
                self.create_trending_table()
                self.create_nepse_companies_table()
                self.create_nepse_sectors_table()
                self.create_news_impact_table()
                self.create_nrb_macroeconomic_table()
                self.create_scraper_last_run_table()
                DbService._initialized = True
    
    def create_connection_pool(self):
        max_retries = 10
        attempt = 0
        logging.debug("Initializing DB pool for host: %s", os.getenv("DB_HOST"))
        while attempt < max_retries:
            try:
                connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=5,
                    maxconn=35,
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT"),
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    sslmode='require', 
                    connect_timeout=45,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=10
                )
                if connection_pool:
                    logging.info("Database connection pool created successfully")
                    conn = connection_pool.getconn()
                    with conn.cursor() as cur:
                        cur.execute("SHOW transaction_isolation;")
                        logging.info(f"Transaction isolation: {cur.fetchone()[0]}")
                    logging.info(f"Autocommit: {'on' if conn.autocommit else 'off'}")
    
                    logging.debug(f"Initial status: {conn.status}")
                    conn.rollback()
                    logging.debug(f"After rollback: {conn.status}")
                    conn.reset()
                    logging.debug(f"After reset: {conn.status}")
                    if conn.status != psycopg2.extensions.STATUS_READY:
                        logging.warning(f"Reset failed to set STATUS_READY: {conn.status}")
                    connection_pool.putconn(conn)
                    return connection_pool
            except psycopg2.OperationalError as e:
                logging.error(f"Database connection failed (Attempt {attempt+1}/{max_retries}): {e}")
                attempt += 1
                wait_time = 2 ** attempt
                logging.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        raise Exception("Failed to establish database connection")
    
    def set_database_timezone(self):
        """
        Sets the default timezone of the entire database to Asia/Kathmandu.
        Requires superuser or database owner privileges.
        """
        def query_func(cur):
            # Set the database timezone
            cur.execute(
            "ALTER DATABASE %s SET timezone TO %s;",
            (os.getenv("DB_NAME"), self.TARGET_TIMEZONE)
             )
            
            # Verify the change
            cur.execute("SELECT current_setting('timezone');")
            current_tz = cur.fetchone()[0]
            if current_tz != self.TARGET_TIMEZONE:
                logging.error(f"Failed to set database timezone! Current: {current_tz}")
                raise psycopg2.OperationalError(
                    f"Database timezone not set to {self.TARGET_TIMEZONE}"
                )
            logging.info(f"Database timezone successfully set to {self.TARGET_TIMEZONE}")
            return None

        try:
            self.execute_with_retry(query_func)
        except psycopg2.Error as e:
            logging.warning(
                f"Could not set database-level timezone (may require superuser privileges): {e}"
            )
            logging.info(
                "Falling back to session-level timezone setting for Asia/Kathmandu"
            )
            # Ensure session-level timezone is set as a fallback
            self.set_kathmandu_timezone()

    @contextmanager
    def connection(self):
        start_time = time.time()
        conn = None
        try:
            conn = self.get_connection_from_pool()
            if conn is None:
                raise Exception("Failed to acquire connection")
            yield conn
            conn.commit()
        except Exception as e:
            if conn and not conn.closed:
                conn.rollback()
            raise
        finally:
            if conn and not conn.closed:
                duration = time.time() - start_time
                if duration > 30:
                    logging.warning(f"Connection held for {duration:.2f} seconds")
                self.return_connection_to_pool(conn)

    def should_retry(self, error):
        """Determine if an error is retryable based on its type or SQLSTATE code."""
        if isinstance(error, psycopg2.InterfaceError):
            return True
        if isinstance(error, psycopg2.DatabaseError) and error.pgcode:
            # Retry on connection-related or transient errors
            retryable_codes = ['08000', '08003', '08006', '57P01', '57P02', '57P03', '53300']
            return any(error.pgcode.startswith(code) for code in retryable_codes)
        return False


    def execute_with_retry(self, query_func, max_retries=5, initial_delay=1):
        last_exception = None
        
        for attempt in range(max_retries):
            with self.connection() as conn:
                try:
                    with conn.cursor() as cur:
                        result = query_func(cur)
                        conn.commit()
                        return result
                        
                except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                    last_exception = e
                    conn.rollback()
                    
                    if attempt < max_retries - 1 and self.should_retry(e):
                        delay = initial_delay * (2 ** attempt)
                        logging.warning(f"Retryable error (attempt {attempt+1}/{max_retries}): {str(e)}")
                        time.sleep(min(delay, 10))  # Cap max delay at 10 seconds
                        continue
                        
                    raise  # Re-raise if not retryable or final attempt
                    
                except Exception as e:
                    conn.rollback()
                    logging.error(f"Non-retryable error: {str(e)}")
                    raise
                    
        raise Exception(f"Failed after {max_retries} attempts") from last_exception


    def close_pool(self):
         if self.connection_pool:
            self.connection_pool.closeall()
            logging.info("Connection pool closed.")
    def warmup_pool(self):
        """Pre-establish connections to avoid initial delays"""
        connections = []
        try:
            for _ in range(self.connection_pool.minconn):
                conn = self.connection_pool.getconn()
                connections.append(conn)
        finally:
            for conn in connections:
                self.connection_pool.putconn(conn)

   
    def monitor_pool(self):
        status = self.get_pool_status()
        logging.info(f"Connection pool status: {status}")
        if status['in_use'] > 0.8 * status['maxconn']:
            logging.warning("Connection pool approaching exhaustion")


    def get_connection_from_pool(self):
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            conn = None
            try:
                # Recycle connections if overdue
                if datetime.now() - self.last_recycle > self.recycle_interval:
                    self._recycle_connections()
                    self.last_recycle = datetime.now()

                conn = self.connection_pool.getconn()
                used = len(self.connection_pool._used)
                logging.debug(f"Acquired connection, used: {used}/{self.connection_pool.maxconn}")
                
                # Validate connection
                if conn.closed or conn.status != psycopg2.extensions.STATUS_READY:
                    raise psycopg2.InterfaceError("Connection is closed or not ready")
                
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    if cur.fetchone()[0] != 1:
                        raise psycopg2.OperationalError("Connection validation failed")
                
                return conn
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                logging.warning(f"Connection failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                if "SSL SYSCALL error" in str(e):
                    logging.warning(f"SSL error detected, retrying (attempt {attempt+1}/{max_retries}): {str(e)}")
                else:
                    logging.warning(f"Connection failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                if conn:
                    conn.close()
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 10)
                    continue
                raise
            finally:
                if conn and conn.closed:
                    logging.debug("Connection closed during acquisition")

    def _recycle_connections(self):
        """Close all connections and reopen fresh ones"""
        if len(self.connection_pool._used) > 0.8 * self.connection_pool.maxconn:
            logging.info("Skipping recycle due to high load")
            return
        self.close_pool()
        self.connection_pool = self.create_connection_pool()


    def get_pool_status(self):
        """Return information about the connection pool status."""
        if not self.connection_pool:
            return {"status": "no pool"}
        
        return {
            "minconn": self.connection_pool.minconn,
            "maxconn": self.connection_pool.maxconn,
            "current_connections": len(self.connection_pool._used) + len(self.connection_pool._pool),
            "available": len(self.connection_pool._pool),
            "in_use": len(self.connection_pool._used)
        }

    def check_pool_health(self):
        """Check if the pool is healthy by testing a connection."""
        conn = None
        try:
            conn = self.get_connection_from_pool()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception as e:
            logging.error(f"Pool health check failed: {e}")
            return False
        finally:
            if conn:
                self.return_connection_to_pool(conn)

    
    def return_connection_to_pool(self, conn):
        if conn is None or conn.closed:
            return
        try:
            logging.debug(f"Connection status before reset: {conn.status}")
            logging.debug(f"STATUS_READY: {psycopg2.extensions.STATUS_READY}, STATUS_BEGIN: {psycopg2.extensions.STATUS_BEGIN}, STATUS_IN_TRANSACTION: {psycopg2.extensions.STATUS_IN_TRANSACTION}")
            
            # Reset connection state
            try:
                conn.rollback()
                logging.debug(f"After rollback: {conn.status}")
                with conn.cursor() as cur:
                    cur.execute("RESET ALL;")  # Neon-compatible session reset
                logging.debug(f"After RESET ALL: {conn.status}")
                conn.reset()
                logging.debug(f"After reset: {conn.status}")
            except Exception as reset_e:
                logging.warning(f"Failed to reset connection: {str(reset_e)}")
            
            # Test connection health
            original_autocommit = conn.autocommit
            logging.debug(f"Original autocommit: {original_autocommit}")
            conn.autocommit = True
            logging.debug(f"Autocommit set to True: {conn.status}")
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result[0] != 1:
                        raise psycopg2.OperationalError("Connection test failed")
                logging.debug(f"After health check: {conn.status}")
            finally:
                conn.autocommit = original_autocommit
                logging.debug(f"Restored autocommit: {conn.status}")
            
            logging.debug(f"Connection status after reset: {conn.status}")
            
            expected_ready = psycopg2.extensions.STATUS_READY  # Should be 0
            logging.debug(f"Expected STATUS_READY: {expected_ready}")
            if conn.status != expected_ready:
                logging.error(f"Connection not in READY state: {conn.status}, closing it")
                conn.close()
                raise psycopg2.OperationalError(f"Connection not in READY state after reset: {conn.status} (expected {expected_ready})")
            
            self.connection_pool.putconn(conn)
            used = len(self.connection_pool._used)
            logging.debug(f"Returned connection, used: {used}/{self.connection_pool.maxconn}")
        except Exception as e:
            logging.error(f"Error returning connection to pool: {str(e)}")
            try:
                if not conn.closed:
                    conn.close()
            except Exception:
                pass

            


            
    def set_kathmandu_timezone(self):
        def query_func(cur):
            cur.execute("SET TIME ZONE 'Asia/Kathmandu';")
            cur.execute("SHOW TIMEZONE;")
            current_tz = cur.fetchone()[0]
            if current_tz != 'Asia/Kathmandu':
                logging.warning(f"Failed to set timezone! Current: {current_tz}")
            return None

        self.execute_with_retry(query_func)

    def create_extensions(self):
        def query_func(cur):
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            return None

        self.execute_with_retry(query_func)

    def create_tables(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    file_name TEXT,
                    url TEXT UNIQUE,
                    title TEXT,
                    category TEXT,
                    author TEXT,
                    published_date TEXT,
                    published_time TEXT,
                    content TEXT,
                    combined_embedding VECTOR(768),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
                );
            """)
            return None
        self.execute_with_retry(query_func)

    

    def create_summary_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS article_summaries (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    url TEXT UNIQUE,
                    summary TEXT,
                    impact_score NUMERIC,
                    relevance_score NUMERIC,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu'),
                    event_id UUID REFERENCES events(id)
                );
            """)
            return None
        self.execute_with_retry(query_func)

    def fetch_embeddings(self):
        def query_func(cur):
            cur.execute("SELECT * FROM embeddings")
            rows = cur.fetchall()
            data = []
            for row in rows:
                item = {
                    "id": row[0], "file_name": row[1], "url": row[2], "title": row[3],
                    "category": row[4], "author": row[5], "published_date": row[6],
                    "published_time": row[7], "content": row[8], "combined_embedding": row[9],
                    "created_at": row[10],
                }
                data.append(item)
            return data

        return self.execute_with_retry(query_func)

    def add_embedding(self, data):
        def query_func(cur):
            cur.execute("""
                INSERT INTO embeddings (
                    file_name, url, title, category, author, published_date, published_time,
                    content, combined_embedding
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """, data)
            return None  

        self.execute_with_retry(query_func)

    def check_if_embeddings_exist(self, url):
        def query_func(cur):
            cur.execute("SET statement_timeout TO 3000")  # 3-second timeout

            cur.execute("SET statement_timeout TO 5000")  # 5-second timeout
            cur.execute("SELECT 1 FROM embeddings WHERE url = %s LIMIT 1;", (url,))
            return cur.fetchone() is not None

        try:
            return self.execute_with_retry(query_func)
        except psycopg2.errors.QueryCanceled:
            logging.warning("Embedding check query timed out")
            return False

   
    def add_article_summary(self, event_id=None, url=None, summary="", impact_score=0.0, relevance_score=0.0):
        def query_func(cur):
            if event_id:
                query = """
                    INSERT INTO article_summaries 
                        (event_id, url, summary, impact_score, relevance_score)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """
                params = (event_id, url, summary, impact_score, relevance_score)
            else:
                query = """
                    INSERT INTO article_summaries 
                        (url, summary, impact_score, relevance_score)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """
                params = (url, summary, impact_score, relevance_score)
            cur.execute(query, params)
            return cur.fetchone()[0]

        return self.execute_with_retry(query_func)
            
    def create_events_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    url TEXT UNIQUE,
                    title TEXT,
                    published_date TEXT,
                    content TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
                );
            """)
            return None

        self.execute_with_retry(query_func)

    def add_event(self, title, url, published_date, content):
        def query_func(cur):
            cur.execute("""
                INSERT INTO events (title, url, published_date, content)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (title, url, published_date, content))
            return cur.fetchone()[0]

        return self.execute_with_retry(query_func)

    def check_if_event_exists(self, url):
        def query_func(cur):
            cur.execute("SELECT 1 FROM events WHERE url = %s LIMIT 1;", (url,))
            return cur.fetchone() is not None

        return self.execute_with_retry(query_func)


    def get_articles_last_hour(self):
        def query_func(cur):
            # cur.execute("SET TIME ZONE 'Asia/Kathmandu';")
            cur.execute("""
                SELECT 
                    url, 
                    summary, 
                    impact_score, 
                    relevance_score,
                    created_at
                FROM article_summaries
                WHERE 
                    (created_at) > (NOW() AT TIME ZONE 'Asia/Kathmandu' - INTERVAL '1 hour')
                    AND relevance_score >= 0.45 
                    AND impact_score >= 0.3
                ORDER BY created_at DESC;

                    """,
                )
            rows = cur.fetchall()
            return [
                {
                    "url": row[0],
                    "summary": row[1],
                    "impact_score": float(row[2]),
                    "relevance_score": float(row[3]),
                    "local_time": row[4]
                }
                for row in rows
            ]

        return self.execute_with_retry(query_func)
    
    def create_trending_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trending_topics (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    topics JSON,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
                );
                CREATE INDEX IF NOT EXISTS trending_topics_created_at_idx 
                    ON trending_topics (created_at);
            """)
            return None

        self.execute_with_retry(query_func)

    def add_trending_topics(self, topics):
        if not topics:
            logging.warning("Attempted to add empty trending topics")
            return False

        def query_func(cur):
            try:
                topics_json = json.dumps(topics, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                logging.error(f"Failed to serialize topics: {e}")
                return False
            cur.execute("""
                INSERT INTO trending_topics (topics)
                VALUES (%s)
                RETURNING id;
            """, (topics_json,))
            inserted_id = cur.fetchone()[0]
            logging.info(f"Successfully stored trending topics with ID: {inserted_id}")
            return True

        return self.execute_with_retry(query_func)

    

    def get_trending_topics(self):
        def query_func(cur):
            cur.execute("""
                SELECT topics FROM trending_topics
                ORDER BY created_at DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            if row:
                if isinstance(row[0], list):
                    return row[0]
                else:
                    topics_data = (
                        row[0]
                        .replace('""', '"')
                        .replace('\\""', '"')
                        .replace(" ", " ")
                    )
                    return json.loads(topics_data)
            logging.warning("No trending topics found in the database.")
            return []

        return self.execute_with_retry(query_func)
    
    def get_trending_topics_with_timestamp(self):
        def query_func(cur):
            cur.execute("""
                SELECT topics, created_at AT TIME ZONE 'Asia/Kathmandu'
                FROM trending_topics
                ORDER BY created_at DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            if row:
                topics_data = row[0]
                if isinstance(topics_data, str):
                    topics_data = topics_data.replace('""', '"').replace('\\""', '"').replace(" ", " ")
                    topics = json.loads(topics_data)
                else:
                    topics = topics_data
                return {"topics": topics, "created_at": row[1]}
            logging.warning("No trending topics found in the database.")
            return None
        return self.execute_with_retry(query_func)

##to create nepse table and its operations
    def create_nepse_companies_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nepse_companies (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    company_id INTEGER,
                    company_name TEXT NOT NULL,
                    symbol TEXT NOT NULL UNIQUE,
                    security_name TEXT,
                    status TEXT,
                    company_email TEXT,
                    website TEXT,
                    sector_name TEXT,
                    regulatory_body TEXT,
                    instrument_type TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu'),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
                );
                CREATE INDEX IF NOT EXISTS nepse_companies_symbol_idx ON nepse_companies(symbol);
                CREATE INDEX IF NOT EXISTS nepse_companies_sector_idx ON nepse_companies(sector_name);
            """)
            return None
        self.execute_with_retry(query_func)

    def check_nepse_company_exists(self, symbol):
        def query_func(cur):
            cur.execute("SELECT 1 FROM nepse_companies WHERE symbol = %s LIMIT 1;", (symbol,))
            return cur.fetchone() is not None

        return self.execute_with_retry(query_func)

    def upsert_nepse_company(self, company_data):
        def query_func(cur):
            query = """
                INSERT INTO nepse_companies (
                    company_id, company_name, symbol, security_name, status, 
                    company_email, website, sector_name, regulatory_body, instrument_type
                ) VALUES (
                    %(company_id)s, %(company_name)s, %(symbol)s, 
                    %(security_name)s, %(status)s, %(company_email)s, %(website)s, 
                    %(sector_name)s, %(regulatory_body)s, %(instrument_type)s
                )
                ON CONFLICT (symbol) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    security_name = EXCLUDED.security_name,
                    status = EXCLUDED.status,
                    company_email = EXCLUDED.company_email,
                    website = EXCLUDED.website,
                    sector_name = EXCLUDED.sector_name,
                    regulatory_body = EXCLUDED.regulatory_body,
                    instrument_type = EXCLUDED.instrument_type,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING symbol;
            """
            db_data = {
                "company_id": company_data.get("id"),
                "company_name": company_data.get("companyName"),
                "symbol": company_data.get("symbol"),
                "security_name": company_data.get("securityName"),
                "status": company_data.get("status"),
                "company_email": company_data.get("companyEmail"),
                "website": company_data.get("website"),
                "sector_name": company_data.get("sectorName"),
                "regulatory_body": company_data.get("regulatoryBody"),
                "instrument_type": company_data.get("instrumentType"),
            }
            cur.execute(query, db_data)
            return cur.fetchone()[0]

        return self.execute_with_retry(query_func)




    def create_nepse_sectors_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nepse_sectors (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    sector_name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
                );
                CREATE INDEX IF NOT EXISTS nepse_sectors_name_idx ON nepse_sectors(sector_name);
            """)
            return None

        self.execute_with_retry(query_func)

    def insert_nepse_sector(self, sector_name):
        def query_func(cur):
            cur.execute("""
                INSERT INTO nepse_sectors (sector_name)
                VALUES (%s)
                ON CONFLICT (sector_name) DO NOTHING
                RETURNING sector_name;
            """, (sector_name,))
            row = cur.fetchone()
            return row[0] if row else None

        return self.execute_with_retry(query_func)
        
    def check_nepse_sector_exists(self, sector_name):
        def query_func(cur):
            cur.execute("SELECT 1 FROM nepse_sectors WHERE sector_name = %s LIMIT 1;", (sector_name,))
            return cur.fetchone() is not None

        return self.execute_with_retry(query_func)
        
    
    
    def get_sector_id_by_name(self, sector_name):
        def query_func(cur):
            cur.execute("SELECT id FROM nepse_sectors WHERE sector_name = %s;", (sector_name,))
            row = cur.fetchone()
            return row[0] if row else None

        return self.execute_with_retry(query_func)
        
    
    def get_company_id_by_name_or_symbol(self, identifier):
        def query_func(cur):
            cur.execute("""
                SELECT id FROM nepse_companies
                WHERE symbol = %s OR company_name = %s
                LIMIT 1;
            """, (identifier, identifier))
            row = cur.fetchone()
            return row[0] if row else None

        return self.execute_with_retry(query_func)
    
    def get_event_id_by_url_or_title(self, url, content):
        def query_func(cur):
            cur.execute("SELECT id FROM events WHERE url = %s LIMIT 1;", (url,))
            row = cur.fetchone()
            return row[0] if row else None

        return self.execute_with_retry(query_func)
        
    def get_event_id_by_url(self, url):
        def query_func(cur):
            cur.execute("SELECT id FROM events WHERE url = %s LIMIT 1;", (url,))
            row = cur.fetchone()
            return row[0] if row else None

        return self.execute_with_retry(query_func)

    def add_dummy_summary(self, url):
        return self.add_article_summary(url, "[ICRA Report] No summary generated", 0.0, 0.0)
    
    def create_news_impact_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news_impact (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    event_id UUID REFERENCES events(id),
                    article_summary_id UUID REFERENCES article_summaries(id),
                    sector_ids UUID[],
                    company_ids UUID[],
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
                );
            """)
            return None

        self.execute_with_retry(query_func)

    def validate_sector_ids(self, sector_ids):
        if not sector_ids:
            return True

        def query_func(cur):
            cur.execute("""
                SELECT id FROM nepse_sectors    
                WHERE id = ANY(%s::uuid[]);
            """, (sector_ids,))
            existing_ids = set(row[0] for row in cur.fetchall())
            invalid_ids = set(sector_ids) - existing_ids
            if invalid_ids:
                logging.error(f"Invalid sector IDs: {invalid_ids}")
                return False
            return True

        return self.execute_with_retry(query_func)
        
    def get_all_nepse_companies(self):
        def query_func(cur):
            cur.execute("SELECT company_name, symbol FROM nepse_companies;")
            return cur.fetchall()

        return self.execute_with_retry(query_func)

    def get_all_sector_names(self):
        query = "SELECT sector_name FROM nepse_sectors;"
       
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                return [row[0] for row in rows]
    
    def validate_company_ids(self, company_ids):
        if not company_ids:
            return True

        try:
            company_ids = [str(uuid.UUID(str(id))) for id in company_ids]
        except ValueError:
            return False

        def query_func(cur):
            cur.execute("""
                SELECT COUNT(*) = %s AS all_valid
                FROM nepse_companies
                WHERE id::text = ANY(%s::text[]);
            """, (len(company_ids), company_ids))
            return cur.fetchone()[0]

        return self.execute_with_retry(query_func)


    def add_news_impact(self, event_id, article_summary_id, sector_ids=None, company_ids=None):
        sector_ids = sector_ids or []
        company_ids = company_ids or []

        if not self.validate_sector_ids(sector_ids):
            raise ValueError("One or more sector IDs are invalid")
        if not self.validate_company_ids(company_ids):
            raise ValueError("One or more company IDs are invalid")

        def query_func(cur):
            cur.execute("""
                INSERT INTO news_impact (
                    event_id, article_summary_id, sector_ids, company_ids
                ) VALUES (%s, %s, %s::uuid[], %s::uuid[])
                RETURNING id;
            """, (event_id, article_summary_id, sector_ids, company_ids))
            return cur.fetchone()[0]

        return self.execute_with_retry(query_func)


    def create_nrb_macroeconomic_table(self):
        def query_func(cur):
            cur.execute("""
            CREATE TABLE IF NOT EXISTS nrb_macroeconomic_reports (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                title TEXT NOT NULL,
                url TEXT UNIQUE,
                pdf_url TEXT,
                published_date TEXT,
                content TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu'),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Kathmandu')
            );
            CREATE INDEX IF NOT EXISTS nrb_macroeconomic_published_date_idx 
                ON nrb_macroeconomic_reports(published_date);
        """)
            return None

        self.execute_with_retry(query_func)

    def check_nrb_report_exists(self, url):
        def query_func(cur):
            cur.execute("SELECT 1 FROM nrb_macroeconomic_reports WHERE url = %s LIMIT 1;", (url,))
            return cur.fetchone() is not None

        return self.execute_with_retry(query_func)

    
    def upsert_nrb_report(self, title, url, pdf_url, published_date, content):
        def query_func(cur):
            cur.execute("""
                INSERT INTO nrb_macroeconomic_reports (
                    title, url, pdf_url, published_date, content
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    pdf_url = EXCLUDED.pdf_url,
                    published_date = EXCLUDED.published_date,
                    content = EXCLUDED.content,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, (title, url, pdf_url, published_date, content))
            return cur.fetchone()[0]

        return self.execute_with_retry(query_func)


    def add_to_watchlist(self, user_id, company_id):
        def query_func(cur):
            cur.execute("""
                INSERT INTO user_watchlists (user_id, company_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, company_id) DO NOTHING
                RETURNING id;
            """, (user_id, company_id))
            return cur.fetchone()[0] if cur.rowcount > 0 else None
        return self.execute_with_retry(query_func)

    def get_watchlist(self, user_id):
        def query_func(cur):
            cur.execute("""
                SELECT c.symbol, c.company_name 
                FROM user_watchlists w
                JOIN nepse_companies c ON w.company_id = c.id
                WHERE w.user_id = %s
                ORDER BY w.created_at DESC;
            """, (user_id,))
            return [{"symbol": row[0], "name": row[1]} for row in cur.fetchall()]
        return self.execute_with_retry(query_func)

    def store_insight(self, watchlist_id, summary, companies):
        def query_func(cur):
            cur.execute("""
                INSERT INTO watchlist_insights (watchlist_id, summary, companies)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (watchlist_id, summary, json.dumps(companies)))
            return cur.fetchone()[0]
        return self.execute_with_retry(query_func)
    


    #methods to check the lastScraper run for the nepse scraper\
    def create_scraper_last_run_table(self):
        def query_func(cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scraper_last_run (
                    scraper_name TEXT PRIMARY KEY,
                    last_run_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
            """)
            return None
        self.execute_with_retry(query_func)

    def get_last_run(self, scraper_name: str):
        def query_func(cur):
            cur.execute("SELECT last_run_at FROM scraper_last_run WHERE scraper_name = %s;", (scraper_name,))
            row = cur.fetchone()
            return row[0] if row else None
        return self.execute_with_retry(query_func)

    def set_last_run(self, scraper_name: str, timestamp):
        def query_func(cur):
            cur.execute("""
                INSERT INTO scraper_last_run (scraper_name, last_run_at)
                VALUES (%s, %s)
                ON CONFLICT (scraper_name)
                DO UPDATE SET last_run_at = EXCLUDED.last_run_at;
            """, (scraper_name, timestamp))
        return self.execute_with_retry(query_func)
