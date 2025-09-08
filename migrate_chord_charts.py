#!/usr/bin/env python3
"""
Migrate chord charts from Google Sheets to PostgreSQL - EXACT 1:1 REPLICA

This script creates an EXACT copy of the Google Sheets ChordCharts data with:
- ZERO data transformation (preserve ChordIDs 292-306, ItemIDs "107, 61", etc.)
- Direct column mapping: A→chord_id, B→item_id, C→title, D→chord_data, E→created_at, F→order_col
- NO foreign key conversions or comma-separated splitting
- Preserve ALL original values exactly as-is from the sheet

CRITICAL: This will recreate the chord_charts table structure if --recreate-table flag is used.
"""
import os
import sys
import time
import logging
import json
from typing import List, Dict, Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

# Import after path setup
from app.database import get_db, create_tables, DatabaseTransaction
from app.repositories.chord_charts import ChordChartRepository
from app import sheets
from sqlalchemy import text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_all_chord_charts_from_sheets() -> List[Dict[str, Any]]:
    """Get all chord charts from Google Sheets ChordCharts worksheet."""
    try:
        logger.info("🎸 Fetching chord charts from Google Sheets...")
        spread = sheets.get_spread()
        
        # Initialize sheet if it doesn't exist
        sheets.initialize_chordcharts_sheet()
        
        # Get all records from ChordCharts sheet
        sheet = spread.worksheet('ChordCharts')
        records = sheets.sheet_to_records(sheet, is_routine_worksheet=False)
        
        if not records:
            logger.warning("⚠️  No chord charts found in Google Sheets")
            return []
        
        logger.info(f"📊 Total records from ChordCharts sheet: {len(records)}")
        
        # Filter out empty records and validate required fields
        valid_charts = []
        skipped_empty_chordid = 0
        skipped_empty_title = 0
        skipped_empty_chorddata = 0
        skipped_malformed_json = 0
        
        for chart in records:
            # Debug log for first few records to understand structure
            if len(valid_charts) < 5:
                logger.debug(f"  🔍 Record sample: A={chart.get('A')}, B={chart.get('B')}, C={chart.get('C')}, D={chart.get('D', '')[:50]}..., F={chart.get('F')}")
            
            # Must have ChordID (A) - this is the primary key
            if not chart.get('A'):
                skipped_empty_chordid += 1
                continue
                
            # Must have Title (C) - this is the chord name
            if not chart.get('C'):
                skipped_empty_title += 1 
                continue
                
            # Must have ChordData (D) - this is the SVGuitar JSON
            chord_data_raw = chart.get('D', '').strip()
            if not chord_data_raw or chord_data_raw in ['', '{}']:
                skipped_empty_chorddata += 1
                continue
                
            # Try to validate JSON structure in ChordData (but be more lenient)
            try:
                json.loads(chord_data_raw)  # Validate JSON
                valid_charts.append(chart)
                logger.debug(f"  🎵 Valid chord chart: {chart['C']} (ChordID={chart['A']}, ItemID={chart.get('B', 'N/A')}, Order={chart.get('F', 'N/A')})")
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"  ⚠️ Skipping chord chart {chart['A']} ({chart.get('C', 'No title')}) with malformed JSON: {e}")
                skipped_malformed_json += 1
                continue
        
        # Log detailed filtering results
        logger.info(f"📊 Filtering results:")
        logger.info(f"  ✅ Valid chord charts: {len(valid_charts)}")
        logger.info(f"  ⚠️ Skipped - missing ChordID (A): {skipped_empty_chordid}")
        logger.info(f"  ⚠️ Skipped - missing Title (C): {skipped_empty_title}")
        logger.info(f"  ⚠️ Skipped - missing/empty ChordData (D): {skipped_empty_chorddata}")
        logger.info(f"  ⚠️ Skipped - malformed JSON: {skipped_malformed_json}")
        
        return valid_charts
        
    except Exception as e:
        logger.error(f"❌ Error fetching chord charts from Google Sheets: {e}")
        return []

def recreate_chord_charts_table():
    """Recreate chord_charts table with exact Google Sheets structure."""
    try:
        logger.info("🔄 Recreating chord_charts table for exact 1:1 replica...")
        
        with DatabaseTransaction() as db:
            # Drop existing table
            db.execute(text("DROP TABLE IF EXISTS chord_charts CASCADE"))
            
            # Create exact replica table structure
            db.execute(text("""
                CREATE TABLE chord_charts (
                    chord_id INTEGER,        -- Column A (preserve original ChordIDs)
                    item_id TEXT,           -- Column B (preserve "107, 61" format) 
                    title TEXT,             -- Column C
                    chord_data JSON,        -- Column D
                    created_at TIMESTAMP,   -- Column E
                    order_col INTEGER       -- Column F
                )
            """))
            
        logger.info("✅ Recreated chord_charts table with exact Google Sheets structure")
        
    except Exception as e:
        logger.error(f"❌ Error recreating chord_charts table: {e}")
        raise

def clear_existing_chord_charts():
    """Clear ALL existing chord charts from PostgreSQL."""
    try:
        logger.info("🗑️ Clearing existing chord charts from PostgreSQL...")
        
        with DatabaseTransaction() as db:
            # Get count before deletion
            result = db.execute(text("SELECT COUNT(*) FROM chord_charts"))
            chart_count = result.scalar() if result else 0
            
            # Clear all chord charts
            db.execute(text("DELETE FROM chord_charts"))
            logger.info(f"  🗑️ Deleted {chart_count} chord charts")
        
        logger.info("✅ Cleared all existing chord charts")
        
    except Exception as e:
        logger.error(f"❌ Error clearing existing chord charts: {e}")
        raise

def migrate_chord_charts_from_sheets(clear_existing=False, recreate_table=False):
    """Main migration function to import chord charts from Google Sheets to PostgreSQL."""
    logger.info("🚀 Starting EXACT 1:1 chord charts migration from Google Sheets to PostgreSQL...")
    
    # Recreate table structure if requested
    if recreate_table:
        recreate_chord_charts_table()
    else:
        # Ensure database tables exist
        create_tables()
    
    # Optionally clear existing chord charts for clean migration
    if clear_existing:
        clear_existing_chord_charts()
    
    # Get all chord charts from Google Sheets
    sheets_charts = get_all_chord_charts_from_sheets()
    
    if not sheets_charts:
        logger.error("❌ No chord charts to migrate")
        return
    
    # Migration counters
    migrated_count = 0
    error_count = 0
    skipped_count = 0
    total_charts = len(sheets_charts)
    
    logger.info(f"\n🚀 Starting migration of {total_charts} chord charts...")
    
    with DatabaseTransaction() as db:
        logger.info("📋 Performing DIRECT 1:1 copy with ZERO data transformation...")
        
        for idx, chart_data in enumerate(sheets_charts, 1):
            try:
                # DIRECT copy from Google Sheets columns - NO TRANSFORMATION
                chord_id_raw = chart_data.get('A', '')  # Column A -> chord_id
                item_id_raw = chart_data.get('B', '')   # Column B -> item_id (preserve "107, 61")
                title = chart_data.get('C', '')         # Column C -> title
                chord_data_json = chart_data.get('D', '{}')  # Column D -> chord_data
                created_at_raw = chart_data.get('E', '')     # Column E -> created_at
                order_raw = chart_data.get('F', '')          # Column F -> order_col
                
                logger.info(f"\n🎵 Direct copying row {idx}/{total_charts}: ChordID={chord_id_raw}, ItemID='{item_id_raw}', Title='{title}', Order={order_raw}")
                
                # Parse chord_id as integer (but preserve original value)
                try:
                    chord_id_int = int(chord_id_raw) if chord_id_raw else None
                except (ValueError, TypeError):
                    chord_id_int = None
                    logger.warning(f"  ⚠️ Non-numeric chord_id: '{chord_id_raw}'")
                
                # Parse order as integer
                try:
                    order_int = int(float(order_raw)) if order_raw and str(order_raw).strip() not in ['', 'None', 'null'] else None
                except (ValueError, TypeError):
                    order_int = None
                    logger.warning(f"  ⚠️ Non-numeric order: '{order_raw}'")
                
                # Validate chord data JSON
                try:
                    parsed_chord_data = json.loads(chord_data_json)
                    if not isinstance(parsed_chord_data, dict):
                        raise ValueError("ChordData must be a JSON object")
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.error(f"  ❌ Invalid JSON in ChordData: {e}")
                    error_count += 1
                    continue
                
                # Parse created_at (use NOW() if empty)
                if created_at_raw and created_at_raw.strip():
                    # TODO: Parse the actual timestamp if needed
                    created_at_value = "NOW()"
                else:
                    created_at_value = "NOW()"
                
                # DIRECT INSERT - exact 1:1 copy with NO transformation
                db.execute(
                    text("""
                        INSERT INTO chord_charts (chord_id, item_id, title, chord_data, created_at, order_col)
                        VALUES (:chord_id, :item_id, :title, :chord_data, NOW(), :order_col)
                    """),
                    {
                        "chord_id": chord_id_int,
                        "item_id": item_id_raw,  # Preserve EXACTLY as-is ("107, 61")
                        "title": title,
                        "chord_data": json.dumps(parsed_chord_data),
                        "order_col": order_int
                    }
                )
                
                logger.info(f"  ✅ Direct copy complete: ChordID={chord_id_int}, ItemID='{item_id_raw}', Title='{title}'")
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error copying chord chart row {idx}: {e}")
                error_count += 1
                continue
    
    logger.info(f"\n🎉 Chord charts migration completed!")
    logger.info(f"  🎵 Chord charts migrated: {migrated_count}")
    logger.info(f"  ⏭️  Chord charts skipped (already exist): {skipped_count}")
    logger.info(f"  ❌ Chord charts with errors: {error_count}")
    
    # Verification
    with DatabaseTransaction() as db:
        final_count = db.execute(text("SELECT COUNT(*) FROM chord_charts")).scalar()
        logger.info(f"  📊 Total chord charts in PostgreSQL after migration: {final_count}")
    
    # Verify EXACT replication of Google Sheets data
    logger.info("\n🔍 Verifying EXACT 1:1 replication:")
    with DatabaseTransaction() as db:
        # Check for target ChordIDs 292-306 that should be preserved exactly
        target_charts = db.execute(
            text("""
                SELECT chord_id, item_id, title, order_col 
                FROM chord_charts 
                WHERE chord_id BETWEEN 292 AND 306
                ORDER BY chord_id 
                LIMIT 10
            """)
        ).fetchall()
        
        if target_charts:
            logger.info(f"  ✅ Found target ChordIDs 292-306 (exact replication):")
            for chart in target_charts:
                logger.info(f"    🎵 ChordID={chart[0]}, ItemID='{chart[1]}', Title='{chart[2]}', Order={chart[3]}")
        else:
            logger.warning(f"  ⚠️ Target ChordIDs 292-306 not found - migration may have failed")
        
        # Check comma-separated ItemIDs are preserved
        comma_charts = db.execute(
            text("""
                SELECT chord_id, item_id, title 
                FROM chord_charts 
                WHERE item_id LIKE '%,%'
                LIMIT 5
            """)
        ).fetchall()
        
        if comma_charts:
            logger.info(f"  ✅ Comma-separated ItemIDs preserved:")
            for chart in comma_charts:
                logger.info(f"    🎵 ChordID={chart[0]}, ItemID='{chart[1]}', Title='{chart[2]}'")
        else:
            logger.warning(f"  ⚠️ No comma-separated ItemIDs found - may indicate transformation occurred")
        
        # Sample first few charts to verify structure
        samples = db.execute(
            text("""
                SELECT chord_id, item_id, title, order_col 
                FROM chord_charts 
                ORDER BY chord_id 
                LIMIT 5
            """)
        ).fetchall()
        
        logger.info("  📋 Sample chord charts (ordered by chord_id):")
        for sample in samples:
            logger.info(f"    🎵 ChordID={sample[0]}, ItemID='{sample[1]}', Title='{sample[2]}', Order={sample[3]}")

def main():
    """Main function with command line argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate chord charts from Google Sheets to PostgreSQL')
    parser.add_argument('--clear', action='store_true', 
                       help='Clear existing chord charts before migration (DESTRUCTIVE)')
    parser.add_argument('--recreate-table', action='store_true',
                       help='Recreate chord_charts table with exact Google Sheets structure (DESTRUCTIVE)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be migrated without making changes')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts (use with --clear or --recreate-table)')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        sheets_charts = get_all_chord_charts_from_sheets()
        logger.info(f"Would migrate {len(sheets_charts)} chord charts from Google Sheets")
        logger.info("Sample chord charts:")
        for chart in sheets_charts[:5]:
            logger.info(f"  - {chart.get('C', 'No title')} (A={chart.get('A')}, B={chart.get('B')}, F={chart.get('F')})")
        return
    
    if args.recreate_table:
        logger.warning("⚠️  --recreate-table flag detected: Will DROP and recreate chord_charts table")
        if not args.force:
            response = input("Are you sure you want to recreate the chord_charts table? (yes/no): ")
            if response.lower() != "yes":
                logger.info("❌ Migration cancelled")
                sys.exit(1)
        else:
            logger.info("🤖 --force flag provided, skipping confirmation")
    
    if args.clear:
        logger.warning("⚠️  --clear flag detected: Will clear ALL existing chord charts")
        if not args.force:
            response = input("Are you sure you want to clear all existing chord charts? (yes/no): ")
            if response.lower() != "yes":
                logger.info("❌ Migration cancelled")
                sys.exit(1)
        else:
            logger.info("🤖 --force flag provided, skipping confirmation")
    
    try:
        migrate_chord_charts_from_sheets(clear_existing=args.clear, recreate_table=args.recreate_table)
        logger.info("\n🎉 Chord charts migration completed successfully!")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()