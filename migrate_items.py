#!/usr/bin/env python3
"""
Migrate items from Google Sheets to PostgreSQL - CLEAN VERSION
This script fixes the corrupted Items table by clearing it and re-importing from Sheets.

CRITICAL: This will clear ALL existing items and chord charts from the database.
Make sure to backup if needed.
"""
import os
import sys
import time
import logging
from typing import List, Dict, Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

# Import after path setup
from app.database import get_db, create_tables, DatabaseTransaction
from app.repositories.items import ItemRepository
from app.repositories.chord_charts import ChordChartRepository
from app import sheets
from sqlalchemy import text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_sheets_items() -> List[Dict[str, Any]]:
    """Get all items from Google Sheets."""
    try:
        logger.info("📊 Fetching items from Google Sheets...")
        items = sheets.get_all_items()
        
        if not items:
            logger.error("❌ No items found in Google Sheets")
            return []
        
        # Filter out empty records and validate required fields
        valid_items = []
        for item in items:
            if item.get('A') and item.get('C'):  # Must have ID and title
                valid_items.append(item)
                logger.debug(f"  📋 Found item: {item['C']} (A={item['A']}, B={item.get('B', 'N/A')})")
        
        logger.info(f"✅ Found {len(valid_items)} valid items in Google Sheets")
        return valid_items
        
    except Exception as e:
        logger.error(f"❌ Error fetching items from Google Sheets: {e}")
        return []

def clear_existing_items_and_chords():
    """Clear ALL existing items and chord charts from PostgreSQL."""
    try:
        logger.info("🗑️ Clearing existing items and chord charts from PostgreSQL...")
        
        with DatabaseTransaction() as db:
            # Clear chord charts first (due to foreign key)
            chord_repo = ChordChartRepository(db)
            chart_count = db.execute(text("SELECT COUNT(*) FROM chord_charts")).scalar()
            db.execute(text("DELETE FROM chord_charts"))
            logger.info(f"  🗑️ Deleted {chart_count} chord charts")
            
            # Clear items
            item_repo = ItemRepository(db)  
            item_count = db.execute(text("SELECT COUNT(*) FROM items")).scalar()
            db.execute(text("DELETE FROM items"))
            logger.info(f"  🗑️ Deleted {item_count} items")
            
            # Reset auto-increment sequences to start fresh
            db.execute(text("ALTER SEQUENCE items_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE chord_charts_id_seq RESTART WITH 1")) 
        
        logger.info("✅ Cleared all existing items and chord charts")
        
    except Exception as e:
        logger.error(f"❌ Error clearing existing data: {e}")
        raise

def migrate_items_from_sheets(clear_existing=False):
    """Main migration function to import items from Google Sheets to PostgreSQL."""
    logger.info("🚀 Starting items migration from Google Sheets to PostgreSQL...")
    
    # Ensure database tables exist
    create_tables()
    
    # Optionally clear existing items for clean migration
    if clear_existing:
        clear_existing_items_and_chords()
    
    # Get all items from Google Sheets
    sheets_items = get_sheets_items()
    
    if not sheets_items:
        logger.error("❌ No items to migrate")
        return
    
    # Migrate each item
    migrated_count = 0
    error_count = 0
    skipped_count = 0
    total_items = len(sheets_items)
    
    logger.info(f"\n🚀 Starting migration of {total_items} items...")
    
    with DatabaseTransaction() as db:
        item_repo = ItemRepository(db)
        
        for idx, item_data in enumerate(sheets_items, 1):
            try:
                # Extract data from Sheets format
                sheets_id = item_data.get('A', '')
                item_id = item_data.get('B', '')
                title = item_data.get('C', '')
                
                logger.info(f"\n📋 Migrating item {idx}/{total_items}: {title} (Sheets A={sheets_id}, B={item_id})")
                
                # Check if item already exists by title to avoid duplicates
                existing_items = item_repo.search_by_title(title)
                if existing_items:
                    logger.warning(f"  ⚠️  Item '{title}' already exists in PostgreSQL, skipping...")
                    skipped_count += 1
                    continue
                
                # Create item from sheets format
                # CRITICAL: Make sure we preserve the ItemID from Column B as item_id
                item = item_repo.create_from_sheets_format(item_data)
                
                logger.info(f"  ✅ Created item: {item.title} (DB ID: {item.id}, ItemID: {item.item_id})")
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error migrating item {item_data.get('A', 'unknown')}: {e}")
                error_count += 1
                continue
    
    logger.info(f"\n🎉 Items migration completed!")
    logger.info(f"  📋 Items migrated: {migrated_count}")
    logger.info(f"  ⏭️  Items skipped (already exist): {skipped_count}")
    logger.info(f"  ❌ Items with errors: {error_count}")
    
    # Verification
    with DatabaseTransaction() as db:
        item_repo = ItemRepository(db)
        final_count = item_repo.count()
        logger.info(f"  📊 Total items in PostgreSQL after migration: {final_count}")
    
    # Verify specific problematic items
    logger.info("\n🔍 Verifying specific items that were corrupted:")
    with DatabaseTransaction() as db:
        item_repo = ItemRepository(db)
        
        # Look for "Remember to stretch" 
        remember_items = item_repo.search_by_title("Remember to stretch")
        if remember_items:
            item = remember_items[0]
            logger.info(f"  ✅ 'Remember to stretch' found: DB ID {item.id}, ItemID '{item.item_id}'")
        else:
            logger.error(f"  ❌ 'Remember to stretch' NOT found after migration")
        
        # Look for "Romeo and Juliet"
        romeo_items = item_repo.search_by_title("Romeo and Juliet")  
        if romeo_items:
            item = romeo_items[0]
            logger.info(f"  ✅ 'Romeo and Juliet' found: DB ID {item.id}, ItemID '{item.item_id}'")
        else:
            logger.error(f"  ❌ 'Romeo and Juliet' NOT found after migration")

def main():
    """Main function with command line argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate items from Google Sheets to PostgreSQL')
    parser.add_argument('--clear', action='store_true', 
                       help='Clear existing items and chord charts before migration (DESTRUCTIVE)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be migrated without making changes')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts (use with --clear)')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        sheets_items = get_sheets_items()
        logger.info(f"Would migrate {len(sheets_items)} items from Google Sheets")
        logger.info("Sample items:")
        for item in sheets_items[:5]:
            logger.info(f"  - {item.get('C', 'No title')} (A={item.get('A')}, B={item.get('B')})")
        return
    
    if args.clear:
        logger.warning("⚠️  --clear flag detected: Will clear ALL existing items and chord charts")
        if not args.force:
            response = input("Are you sure you want to clear all existing items and chord charts? (yes/no): ")
            if response.lower() != "yes":
                logger.info("❌ Migration cancelled")
                sys.exit(1)
        else:
            logger.info("🤖 --force flag provided, skipping confirmation")
    
    try:
        migrate_items_from_sheets(clear_existing=args.clear)
        logger.info("\n🎉 Migration completed successfully!")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()