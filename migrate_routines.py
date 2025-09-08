#!/usr/bin/env python3
"""
Migrate routines from Google Sheets to PostgreSQL.
This script imports all routines and their routine items.
"""
import os
import sys
import time
import random
from typing import List, Dict, Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

# Import after path setup
from app.database import get_db, create_tables
from app.services.routines import routine_service

# Rate limiting configuration
REQUESTS_PER_MINUTE = 55  # Slightly under Google's 60/min limit for safety
REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # ~1.09 seconds between requests
request_count = 0
last_request_time = 0

def rate_limit_delay():
    """Apply rate limiting delay between API requests."""
    global request_count, last_request_time
    
    current_time = time.time()
    
    # Reset counter every minute
    if current_time - last_request_time >= 60:
        request_count = 0
        last_request_time = current_time
    
    # If we're approaching the limit, add a delay
    if request_count >= REQUESTS_PER_MINUTE - 5:  # Buffer of 5 requests
        sleep_time = 60 - (current_time - last_request_time) + random.uniform(1, 3)
        print(f"  ⏳ Rate limit approached, sleeping for {sleep_time:.1f} seconds...")
        time.sleep(sleep_time)
        request_count = 0
        last_request_time = time.time()
    else:
        # Small delay between requests to avoid bursting
        time.sleep(REQUEST_INTERVAL)
    
    request_count += 1

def safe_sheets_request(func, *args, max_retries=3, **kwargs):
    """Execute a Google Sheets request with rate limiting and retry logic."""
    for attempt in range(max_retries):
        try:
            rate_limit_delay()
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'quota exceeded' in error_str or '429' in error_str:
                if attempt < max_retries - 1:
                    backoff_time = (2 ** attempt) * 60 + random.uniform(5, 15)  # Exponential backoff
                    print(f"  ⏳ Rate limit hit, backing off for {backoff_time:.1f} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(backoff_time)
                    continue
                else:
                    print(f"  ❌ Rate limit exceeded after {max_retries} attempts")
                    raise
            else:
                # Non-rate-limit error, re-raise immediately
                raise
    
    return None

def get_sheets_routines() -> List[Dict[str, Any]]:
    """Get routines from Google Sheets API."""
    try:
        # Import sheets module to access Google Sheets data
        from app.sheets import get_spread, sheet_to_records
        
        print("📊 Fetching routines from Google Sheets...")
        
        # Get spreadsheet and Routines worksheet  
        spread = get_spread()
        routines_worksheet = spread.worksheet('Routines')
        
        # Read all routines as structured records
        # Routines index sheet is NOT a routine worksheet - it contains routine metadata
        routines_records = sheet_to_records(routines_worksheet, is_routine_worksheet=False)
        
        if not routines_records:
            print("❌ No routines found in Google Sheets")
            return []
        
        # Filter out empty records and validate required fields
        routines = []
        for routine_data in routines_records:
            if routine_data.get('A') and routine_data.get('B'):  # Must have ID and name
                routines.append(routine_data)
                print(f"  📋 Found routine: {routine_data['B']} (ID: {routine_data['A']})")
        
        print(f"✅ Found {len(routines)} routines in Google Sheets")
        return routines
        
    except Exception as e:
        print(f"❌ Error fetching routines from Google Sheets: {e}")
        return []

def get_sheets_routine_items(routine_id: str) -> List[Dict[str, Any]]:
    """Get routine items for a specific routine from Google Sheets with rate limiting."""
    try:
        from app.sheets import get_spread, sheet_to_records
        
        # Each routine has its own sheet named by its ID
        sheet_name = str(routine_id)
        
        print(f"  📋 Fetching items for routine {routine_id} from sheet '{sheet_name}'...")
        
        # Get spreadsheet with rate limiting
        spread = safe_sheets_request(get_spread)
        if not spread:
            print(f"    ❌ Failed to get spreadsheet for routine {routine_id}")
            return []
        
        # Get worksheet with rate limiting and error handling
        def get_worksheet():
            return spread.worksheet(sheet_name)
        
        try:
            routine_worksheet = safe_sheets_request(get_worksheet)
            if not routine_worksheet:
                print(f"    ⚠️  Sheet '{sheet_name}' not found for routine {routine_id}")
                return []
        except Exception as e:
            if 'not found' in str(e).lower():
                print(f"    ⚠️  Sheet '{sheet_name}' not found for routine {routine_id}")
            else:
                print(f"    ❌ Error accessing sheet '{sheet_name}': {e}")
            return []
        
        # Read routine items as structured records with rate limiting
        def get_records():
            return sheet_to_records(routine_worksheet)
        
        routine_items_records = safe_sheets_request(get_records)
        if not routine_items_records:
            print(f"    ⚠️  No items found for routine {routine_id}")
            return []
        
        # Filter out empty records and validate required fields
        routine_items = []
        for routine_item_data in routine_items_records:
            item_id = routine_item_data.get('B', '').strip()
            if item_id and item_id.isdigit():  # Must have valid numeric Item ID
                routine_items.append(routine_item_data)
        
        print(f"    ✅ Found {len(routine_items)} items for routine {routine_id}")
        return routine_items
        
    except Exception as e:
        print(f"    ❌ Error fetching items for routine {routine_id}: {e}")
        return []

def clear_existing_routines():
    """Clear existing routines from PostgreSQL (for clean migration)."""
    try:
        print("🗑️ Clearing existing routines from PostgreSQL...")
        
        from app.database import DatabaseTransaction
        from app.repositories.routines import RoutineRepository, ActiveRoutineRepository
        
        with DatabaseTransaction() as db:
            routine_repo = RoutineRepository(db)
            active_repo = ActiveRoutineRepository(db)
            
            # Clear active routine first
            active_repo.clear_active_routine()
            
            # Get all routines and delete them
            existing_routines = routine_repo.get_all()
            for routine in existing_routines:
                routine_repo.delete(routine.id)
                print(f"  🗑️ Deleted routine: {routine.name} (ID: {routine.id})")
        
        print("✅ Cleared all existing routines")
        
    except Exception as e:
        print(f"❌ Error clearing existing routines: {e}")
        raise

def migrate_routines(clear_existing=False):
    """Main migration function."""
    print("🚀 Starting routine migration from Google Sheets to PostgreSQL...")
    
    # Ensure database tables exist
    create_tables()
    
    # Optionally clear existing routines for clean migration
    if clear_existing:
        clear_existing_routines()
    
    # Get all routines from Google Sheets
    sheets_routines = get_sheets_routines()
    
    if not sheets_routines:
        print("❌ No routines to migrate")
        return
    
    # Import database transaction management
    from app.database import DatabaseTransaction
    from app.repositories.routines import RoutineRepository, ActiveRoutineRepository
    
    # Migrate each routine with progress tracking
    migrated_count = 0
    items_migrated_count = 0
    skipped_count = 0
    error_count = 0
    total_routines = len(sheets_routines)
    
    print(f"\n🚀 Starting migration of {total_routines} routines...")
    
    for idx, routine_data in enumerate(sheets_routines, 1):
        try:
            routine_id = routine_data['A']
            routine_name = routine_data['B']
            
            print(f"\n📋 Migrating routine {idx}/{total_routines}: {routine_name} (Sheets ID: {routine_id})")
            
            # Check if routine already exists in PostgreSQL by name (to avoid duplicates)
            existing_routines = routine_service.get_all_routines()
            if any(r.get('name', '').lower() == routine_name.lower() for r in existing_routines):
                print(f"  ⚠️  Routine '{routine_name}' already exists in PostgreSQL, skipping...")
                skipped_count += 1
                continue
            
            # Use single transaction for entire routine migration
            with DatabaseTransaction() as db:
                routine_repo = RoutineRepository(db)
                
                # Create routine
                routine = routine_repo.create_from_sheets_format(routine_data)
                print(f"  ✅ Created routine: {routine.name}")
                migrated_count += 1
                
                # Get routine items from Google Sheets
                routine_items = get_sheets_routine_items(routine_id)
                
                # Add each item to the routine within the same transaction
                for item_data in routine_items:
                    try:
                        item_id = int(item_data['B'])
                        order = int(item_data['C']) if item_data['C'] else None
                        completed = item_data['D'].upper() == 'TRUE' if item_data['D'] else False
                        
                        # Add item to routine
                        routine_item = routine_repo.add_item_to_routine(
                            routine_id=routine.id,
                            item_id=item_id,
                            order=order
                        )
                        
                        # Set completion status if specified
                        if item_data['D']:
                            routine_repo.mark_item_complete(
                                routine_id=routine.id,
                                item_id=item_id,
                                completed=completed
                            )
                        
                        items_migrated_count += 1
                        print(f"    ✅ Added item {item_id} to routine (order: {order}, completed: {completed})")
                        
                    except Exception as e:
                        print(f"    ❌ Error adding item {item_data['B']} to routine {routine_id}: {e}")
                        continue
            
            # Add small delay to avoid overwhelming the database
            time.sleep(0.1)
            
        except Exception as e:
            print(f"❌ Error migrating routine {routine_data.get('A', 'unknown')}: {e}")
            error_count += 1
            continue
    
    print(f"\n🎉 Migration completed!")
    print(f"  📋 Routines migrated: {migrated_count}")
    print(f"  📝 Routine items migrated: {items_migrated_count}")
    print(f"  ⏭️  Routines skipped (already exist): {skipped_count}")
    print(f"  ❌ Routines with errors: {error_count}")
    
    # Get final stats
    stats = routine_service.get_stats()
    print(f"  📊 Total routines in PostgreSQL: {stats['total_routines']}")
    
    # Expected vs actual summary
    expected_with_items = 46  # Based on manual verification: 52 - 6 empty sheets
    print(f"\n📈 Expected routines with items: {expected_with_items}")
    print(f"📈 Actual routines migrated: {migrated_count}")
    if migrated_count < expected_with_items:
        missing = expected_with_items - migrated_count - skipped_count
        if missing > 0:
            print(f"⚠️  Missing {missing} routines - may need to investigate errors or rate limiting")

if __name__ == "__main__":
    import sys
    
    # Check for --clear and --force flags
    clear_existing = "--clear" in sys.argv
    force_mode = "--force" in sys.argv
    
    if clear_existing:
        print("⚠️  --clear flag detected: Will clear existing routines before migration")
        if not force_mode:
            response = input("Are you sure you want to clear all existing routines? (yes/no): ")
            if response.lower() != "yes":
                print("❌ Migration cancelled")
                sys.exit(1)
        else:
            print("🤖 --force flag provided, skipping confirmation")
    
    migrate_routines(clear_existing=clear_existing)