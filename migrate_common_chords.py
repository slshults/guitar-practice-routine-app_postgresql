#!/usr/bin/env python3
"""
Migrate CommonChords from Google Sheets to PostgreSQL - EXACT 1:1 REPLICA

This script creates an EXACT copy of the Google Sheets CommonChords data with:
- ZERO data transformation (preserve all 12,708+ records exactly as-is)
- Direct column mapping: A→id, B→type, C→name, D→chord_data, E→created_at, F→order_col, G→unused1, H→unused2
- NO foreign key conversions or data modifications 
- Preserve ALL original values exactly as-is from the sheet

CRITICAL: This will recreate the common_chords table structure if --recreate-table flag is used.
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
from app import sheets
from sqlalchemy import text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_common_chords_from_sheets(limit=None) -> List[Dict[str, Any]]:
    """Get CommonChords from Google Sheets."""
    try:
        logger.info("🎼 Fetching CommonChords from Google Sheets...")
        spread = sheets.get_spread()
        
        # Get CommonChords sheet
        sheet = spread.worksheet('CommonChords')
        records = sheets.sheet_to_records(sheet, is_routine_worksheet=False)
        
        if not records:
            logger.warning("⚠️  No CommonChords found in Google Sheets")
            return []
        
        logger.info(f"📊 Total records from CommonChords sheet: {len(records)}")
        
        # Apply limit for testing
        if limit:
            records = records[:limit]
            logger.info(f"🔬 LIMITED TO FIRST {limit} RECORDS FOR TESTING")
        
        # Filter out empty records and validate required fields
        valid_chords = []
        skipped_empty_id = 0
        skipped_empty_name = 0
        skipped_empty_chorddata = 0
        skipped_malformed_json = 0
        
        for chord in records:
            # Debug log for first few records to understand structure
            if len(valid_chords) < 5:
                logger.debug(f"  🔍 Record sample: A={chord.get('A')}, B={chord.get('B')}, C={chord.get('C')}, D={chord.get('D', '')[:50]}..., F={chord.get('F')}")
            
            # Must have ID (A) - this is the primary key
            if not chord.get('A'):
                skipped_empty_id += 1
                continue
                
            # Must have chord name (C) - this is what we search by
            if not chord.get('C'):
                skipped_empty_name += 1 
                continue
                
            # Must have ChordData (D) - this is the SVGuitar JSON
            chord_data_raw = chord.get('D', '').strip()
            if not chord_data_raw or chord_data_raw in ['', '{}']:
                skipped_empty_chorddata += 1
                continue
                
            # Try to validate JSON structure in ChordData
            try:
                json.loads(chord_data_raw)  # Validate JSON
                valid_chords.append(chord)
                logger.debug(f"  🎵 Valid chord: {chord['C']} (ID={chord['A']}, Type={chord.get('B', 'N/A')}, Order={chord.get('F', 'N/A')})")
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"  ⚠️ Skipping chord {chord['A']} ({chord.get('C', 'No name')}) with malformed JSON: {e}")
                skipped_malformed_json += 1
                continue
        
        # Log detailed filtering results
        logger.info(f"📊 Filtering results:")
        logger.info(f"  ✅ Valid chords: {len(valid_chords)}")
        logger.info(f"  ⚠️ Skipped - missing ID (A): {skipped_empty_id}")
        logger.info(f"  ⚠️ Skipped - missing name (C): {skipped_empty_name}")
        logger.info(f"  ⚠️ Skipped - missing/empty ChordData (D): {skipped_empty_chorddata}")
        logger.info(f"  ⚠️ Skipped - malformed JSON: {skipped_malformed_json}")
        
        return valid_chords
        
    except Exception as e:
        logger.error(f"❌ Error fetching CommonChords from Google Sheets: {e}")
        return []

def recreate_common_chords_table():
    """Recreate common_chords table with exact Google Sheets structure."""
    try:
        logger.info("🔄 Recreating common_chords table for exact 1:1 replica...")
        
        with DatabaseTransaction() as db:
            # Drop existing table
            db.execute(text("DROP TABLE IF EXISTS common_chords CASCADE"))
            
            # Create exact replica table structure  
            db.execute(text("""
                CREATE TABLE common_chords (
                    id INTEGER,             -- Column A (preserve original IDs)
                    type TEXT,              -- Column B (usually "common")
                    name TEXT,              -- Column C (chord name like "E", "Am", etc.)
                    chord_data JSON,        -- Column D (SVGuitar JSON data)
                    created_at TIMESTAMP,   -- Column E
                    order_col INTEGER,      -- Column F
                    unused1 TEXT,           -- Column G (usually empty)
                    unused2 TEXT            -- Column H (usually empty)
                )
            """))
            
        logger.info("✅ Recreated common_chords table with exact Google Sheets structure")
        
    except Exception as e:
        logger.error(f"❌ Error recreating common_chords table: {e}")
        raise

def clear_existing_common_chords():
    """Clear ALL existing CommonChords from PostgreSQL."""
    try:
        logger.info("🗑️ Clearing existing CommonChords from PostgreSQL...")
        
        with DatabaseTransaction() as db:
            # Get count before deletion
            result = db.execute(text("SELECT COUNT(*) FROM common_chords"))
            chord_count = result.scalar() if result else 0
            
            # Clear all chords
            db.execute(text("DELETE FROM common_chords"))
            logger.info(f"  🗑️ Deleted {chord_count} common chords")
        
        logger.info("✅ Cleared all existing CommonChords")
        
    except Exception as e:
        logger.error(f"❌ Error clearing existing CommonChords: {e}")
        raise

def migrate_common_chords_from_sheets(clear_existing=False, recreate_table=False, limit=None):
    """Main migration function to import CommonChords from Google Sheets to PostgreSQL."""
    logger.info("🚀 Starting EXACT 1:1 CommonChords migration from Google Sheets to PostgreSQL...")
    
    # Recreate table structure if requested
    if recreate_table:
        recreate_common_chords_table()
    else:
        # Ensure database tables exist
        create_tables()
    
    # Optionally clear existing chords for clean migration
    if clear_existing:
        clear_existing_common_chords()
    
    # Get CommonChords from Google Sheets
    sheets_chords = get_common_chords_from_sheets(limit=limit)
    
    if not sheets_chords:
        logger.error("❌ No CommonChords to migrate")
        return
    
    # Migration counters
    migrated_count = 0
    error_count = 0
    total_chords = len(sheets_chords)
    
    logger.info(f"\n🚀 Starting migration of {total_chords} CommonChords...")
    
    # Rate limiting - delay between batches
    BATCH_SIZE = 10
    BATCH_DELAY = 1.0  # seconds between batches
    
    with DatabaseTransaction() as db:
        logger.info("📋 Performing DIRECT 1:1 copy with ZERO data transformation...")
        
        for idx, chord_data in enumerate(sheets_chords, 1):
            try:
                # DIRECT copy from Google Sheets columns - NO TRANSFORMATION
                id_raw = chord_data.get('A', '')           # Column A -> id
                type_raw = chord_data.get('B', '')         # Column B -> type
                name = chord_data.get('C', '')             # Column C -> name
                chord_data_json = chord_data.get('D', '{}') # Column D -> chord_data
                created_at_raw = chord_data.get('E', '')   # Column E -> created_at
                order_raw = chord_data.get('F', '')        # Column F -> order_col
                unused1 = chord_data.get('G', '')          # Column G -> unused1
                unused2 = chord_data.get('H', '')          # Column H -> unused2
                
                logger.info(f"\n🎵 Direct copying row {idx}/{total_chords}: ID={id_raw}, Type='{type_raw}', Name='{name}', Order={order_raw}")
                
                # Parse id as integer (but preserve original value)
                try:
                    id_int = int(id_raw) if id_raw else None
                except (ValueError, TypeError):
                    id_int = None
                    logger.warning(f"  ⚠️ Non-numeric id: '{id_raw}'")
                
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
                
                # DIRECT INSERT - exact 1:1 copy with NO transformation
                db.execute(
                    text("""
                        INSERT INTO common_chords (id, type, name, chord_data, created_at, order_col, unused1, unused2)
                        VALUES (:id, :type, :name, :chord_data, NOW(), :order_col, :unused1, :unused2)
                    """),
                    {
                        "id": id_int,
                        "type": type_raw,           # Preserve EXACTLY as-is ("common")
                        "name": name,               # Chord name like "E", "Am", etc.
                        "chord_data": json.dumps(parsed_chord_data),
                        "order_col": order_int,
                        "unused1": unused1,         # Preserve even if empty
                        "unused2": unused2          # Preserve even if empty
                    }
                )
                
                logger.info(f"  ✅ Direct copy complete: ID={id_int}, Type='{type_raw}', Name='{name}'")
                migrated_count += 1
                
                # Rate limiting - pause between batches
                if migrated_count % BATCH_SIZE == 0:
                    logger.info(f"  ⏱️ Rate limiting: processed {migrated_count}/{total_chords}, pausing {BATCH_DELAY}s...")
                    time.sleep(BATCH_DELAY)
                
            except Exception as e:
                logger.error(f"❌ Error copying CommonChord row {idx}: {e}")
                error_count += 1
                continue
    
    logger.info(f"\n🎉 CommonChords migration completed!")
    logger.info(f"  🎵 CommonChords migrated: {migrated_count}")
    logger.info(f"  ❌ CommonChords with errors: {error_count}")
    
    # Verification
    with DatabaseTransaction() as db:
        final_count = db.execute(text("SELECT COUNT(*) FROM common_chords")).scalar()
        logger.info(f"  📊 Total CommonChords in PostgreSQL after migration: {final_count}")
    
    # Verify EXACT replication of Google Sheets data
    logger.info("\n🔍 Verifying EXACT 1:1 replication:")
    with DatabaseTransaction() as db:
        # Sample first few chords to verify structure
        samples = db.execute(
            text("""
                SELECT id, type, name, order_col 
                FROM common_chords 
                ORDER BY id 
                LIMIT 5
            """)
        ).fetchall()
        
        logger.info("  📋 Sample CommonChords (ordered by id):")
        for sample in samples:
            logger.info(f"    🎵 ID={sample[0]}, Type='{sample[1]}', Name='{sample[2]}', Order={sample[3]}")
        
        # Check for major chords
        major_chords = db.execute(
            text("""
                SELECT id, name, type 
                FROM common_chords 
                WHERE name IN ('C', 'D', 'E', 'F', 'G', 'A', 'B')
                ORDER BY name
            """)
        ).fetchall()
        
        if major_chords:
            logger.info(f"  ✅ Found major chords (sample verification):")
            for chord in major_chords:
                logger.info(f"    🎵 {chord[1]} (ID={chord[0]}, Type='{chord[2]}')")
        else:
            logger.warning(f"  ⚠️ No major chords found - migration may have failed")

def main():
    """Main function with command line argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate CommonChords from Google Sheets to PostgreSQL')
    parser.add_argument('--clear', action='store_true', 
                       help='Clear existing CommonChords before migration (DESTRUCTIVE)')
    parser.add_argument('--recreate-table', action='store_true',
                       help='Recreate common_chords table with exact Google Sheets structure (DESTRUCTIVE)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be migrated without making changes')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts (use with --clear or --recreate-table)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of records to migrate (for testing)')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        sheets_chords = get_common_chords_from_sheets(limit=args.limit or 5)
        logger.info(f"Would migrate {len(sheets_chords)} CommonChords from Google Sheets")
        logger.info("Sample CommonChords:")
        for chord in sheets_chords:
            logger.info(f"  - {chord.get('C', 'No name')} (A={chord.get('A')}, B={chord.get('B')}, F={chord.get('F')})")
        return
    
    if args.recreate_table:
        logger.warning("⚠️  --recreate-table flag detected: Will DROP and recreate common_chords table")
        if not args.force:
            response = input("Are you sure you want to recreate the common_chords table? (yes/no): ")
            if response.lower() != "yes":
                logger.info("❌ Migration cancelled")
                sys.exit(1)
        else:
            logger.info("🤖 --force flag provided, skipping confirmation")
    
    if args.clear:
        logger.warning("⚠️  --clear flag detected: Will clear ALL existing CommonChords")
        if not args.force:
            response = input("Are you sure you want to clear all existing CommonChords? (yes/no): ")
            if response.lower() != "yes":
                logger.info("❌ Migration cancelled")
                sys.exit(1)
        else:
            logger.info("🤖 --force flag provided, skipping confirmation")
    
    if args.limit:
        logger.info(f"🔬 TESTING MODE: Limited to {args.limit} records")
    
    try:
        migrate_common_chords_from_sheets(
            clear_existing=args.clear, 
            recreate_table=args.recreate_table,
            limit=args.limit
        )
        logger.info("\n🎉 CommonChords migration completed successfully!")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()