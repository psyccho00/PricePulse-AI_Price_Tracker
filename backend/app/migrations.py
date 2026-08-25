import os
import sqlite3
import logging

logger = logging.getLogger("migration_service")

def run_migrations():
    """
    Checks the existing SQLite database schema against SQLAlchemy models,
    and applies ALTER TABLE commands to add any missing columns.
    """
    database_url = os.getenv("DATABASE_URL", "sqlite:///./price_tracker.db")
    if not database_url.startswith("sqlite"):
        logger.info("Non-SQLite database URL detected. Skipping auto-migration check.")
        return
        
    db_path = database_url.replace("sqlite:///", "")
    # Support relative paths correctly by resolving to absolute paths
    db_path = os.path.abspath(db_path)
    
    if not os.path.exists(db_path):
        logger.info("Database file does not exist yet. Initial schema will be set by SQLAlchemy.")
        return
        
    logger.info(f"Introspecting SQLite database schema for migration: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Migrate product_links table
        cursor.execute("PRAGMA table_info(product_links)")
        product_link_cols = [row[1] for row in cursor.fetchall()]
        
        if product_link_cols:
            if "in_stock" not in product_link_cols:
                logger.info("Column 'in_stock' is missing from 'product_links'. Adding now...")
                cursor.execute("ALTER TABLE product_links ADD COLUMN in_stock BOOLEAN DEFAULT 1")
                conn.commit()
                logger.info("[OK] Added column 'in_stock' to 'product_links'.")
                
            if "currency" not in product_link_cols:
                logger.info("Column 'currency' is missing from 'product_links'. Adding now...")
                cursor.execute("ALTER TABLE product_links ADD COLUMN currency VARCHAR DEFAULT 'INR'")
                conn.commit()
                logger.info("[OK] Added column 'currency' to 'product_links'.")
                
            if "is_active" not in product_link_cols:
                logger.info("Column 'is_active' is missing from 'product_links'. Adding now...")
                cursor.execute("ALTER TABLE product_links ADD COLUMN is_active BOOLEAN DEFAULT 1")
                conn.commit()
                logger.info("[OK] Added column 'is_active' to 'product_links'.")

            if "image_url" not in product_link_cols:
                logger.info("Column 'image_url' is missing from 'product_links'. Adding now...")
                cursor.execute("ALTER TABLE product_links ADD COLUMN image_url VARCHAR")
                conn.commit()
                logger.info("[OK] Added column 'image_url' to 'product_links'.")

        # 2. Migrate alerts table
        cursor.execute("PRAGMA table_info(alerts)")
        alert_cols = [row[1] for row in cursor.fetchall()]
        
        if alert_cols:
            if "phone" not in alert_cols:
                logger.info("Column 'phone' is missing from 'alerts'. Adding now...")
                cursor.execute("ALTER TABLE alerts ADD COLUMN phone VARCHAR")
                conn.commit()
                logger.info("[OK] Added column 'phone' to 'alerts'.")
                
            if "is_active" not in alert_cols:
                logger.info("Column 'is_active' is missing from 'alerts'. Adding now...")
                cursor.execute("ALTER TABLE alerts ADD COLUMN is_active BOOLEAN DEFAULT 1")
                conn.commit()
                logger.info("[OK] Added column 'is_active' to 'alerts'.")

            if "alert_type" not in alert_cols:
                logger.info("Column 'alert_type' is missing from 'alerts'. Adding now...")
                cursor.execute("ALTER TABLE alerts ADD COLUMN alert_type VARCHAR DEFAULT 'target_price'")
                conn.commit()
                logger.info("[OK] Added column 'alert_type' to 'alerts'.")

            if "alert_condition_value" not in alert_cols:
                logger.info("Column 'alert_condition_value' is missing from 'alerts'. Adding now...")
                cursor.execute("ALTER TABLE alerts ADD COLUMN alert_condition_value FLOAT")
                conn.commit()
                logger.info("[OK] Added column 'alert_condition_value' to 'alerts'.")

        # 3. Migrate products table
        cursor.execute("PRAGMA table_info(products)")
        product_cols = [row[1] for row in cursor.fetchall()]
        
        if product_cols:
            if "category" not in product_cols:
                logger.info("Column 'category' is missing from 'products'. Adding now...")
                cursor.execute("ALTER TABLE products ADD COLUMN category VARCHAR")
                conn.commit()
                logger.info("[OK] Added column 'category' to 'products'.")

            if "image_url" not in product_cols:
                logger.info("Column 'image_url' is missing from 'products'. Adding now...")
                cursor.execute("ALTER TABLE products ADD COLUMN image_url VARCHAR")
                conn.commit()
                logger.info("[OK] Added column 'image_url' to 'products'.")

            if "user_id" not in product_cols:
                logger.info("Column 'user_id' is missing from 'products'. Adding now...")
                cursor.execute("ALTER TABLE products ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
                conn.commit()
                logger.info("[OK] Added column 'user_id' to 'products'.")

        # 4. Migrate users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        users_table_exists = cursor.fetchone()
        if not users_table_exists:
            logger.info("Table 'users' is missing. Creating now...")
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR NOT NULL,
                    email VARCHAR NOT NULL UNIQUE,
                    hashed_password VARCHAR NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    reset_token VARCHAR
                )
            """)
            conn.commit()
            logger.info("[OK] Created 'users' table.")

        # 5. Create Performance Optimization Indexes
        logger.info("Verifying database performance indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_links_product_id ON product_links(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_link_id ON price_history(product_link_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_scraped_at ON price_history(scraped_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_product_id ON alerts(product_id)")
        conn.commit()
        logger.info("[OK] Database indexes verified/created.")

        # Verify tables list
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Active database tables: {tables}")
        
    except Exception as e:
        logger.error(f"Error during schema migration: {e}")
    finally:
        conn.close()
