#!/usr/bin/env python3
"""
Bulk import all chords from TormodKv collection with robust rate limiting.

Usage:
    python3 import_all_chords.py [--batch-size 50] [--delay 2] [--max-retries 5]
"""

import sys
import os
import json
import time
import argparse
import logging
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from sheets import (
    bulk_import_chords_from_local_file, 
    get_spread, 
    sheet_to_records,
    convert_fret_positions_to_svguitar,
    records_to_sheet,
    invalidate_caches
)
import gspread
from google.auth.exceptions import RefreshError
from requests.exceptions import RequestException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chord_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChordImporter:
    def __init__(self, batch_size=50, delay=2.0, max_retries=5):
        self.batch_size = batch_size
        self.delay = delay
        self.max_retries = max_retries
        self.total_imported = 0
        self.total_skipped = 0
        self.total_failed = 0
        
    def load_chord_data(self, file_path='/home/steven/webdev/guitar/practice/gpr/chords/completeChords.json'):
        """Load chord data from local file."""
        try:
            with open(file_path, 'r') as f:
                chord_data = json.load(f)
            logger.info(f"Loaded {len(chord_data)} chords from {file_path}")
            return chord_data
        except Exception as e:
            logger.error(f"Failed to load chord data: {e}")
            raise
    
    def get_existing_chords(self):
        """Get list of existing chord names to avoid duplicates."""
        try:
            spread = get_spread()
            try:
                sheet = spread.worksheet('CommonChords')
            except gspread.WorksheetNotFound:
                logger.info("CommonChords sheet not found, creating it...")
                sheet = spread.add_worksheet(title='CommonChords', rows=20000, cols=6)
                sheet.update('A1:F1', [['ChordID', 'ItemID', 'Title', 'ChordData', 'CreatedAt', 'Order']])
                return set(), [], 1, 0
            
            records = sheet_to_records(sheet, is_routine_worksheet=False)
            existing_titles = {record.get('C', '').lower() for record in records if record.get('C')}
            next_id = max([int(float(r.get('A', 0))) for r in records if r.get('A')], default=0) + 1
            next_order = len(records)
            
            logger.info(f"Found {len(existing_titles)} existing chords")
            return existing_titles, records, next_id, next_order
            
        except Exception as e:
            logger.error(f"Error getting existing chords: {e}")
            raise
    
    def retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff on rate limits."""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any(phrase in error_str for phrase in [
                    'quota exceeded', 'rate_limit_exceeded', 'too many requests',
                    'service unavailable', 'internal error'
                ])
                
                if is_rate_limit and attempt < self.max_retries - 1:
                    delay = self.delay * (2 ** attempt)
                    logger.warning(f"Rate limit hit, backing off {delay:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    raise
    
    def process_chord_batch(self, chord_batch, chord_data, records, next_id, next_order, existing_titles):
        """Process a batch of chords with error handling."""
        batch_results = {'imported': [], 'skipped': [], 'failed': []}
        
        for chord_name in chord_batch:
            try:
                # Check if already exists
                if chord_name.lower() in existing_titles:
                    batch_results['skipped'].append(f"{chord_name} (already exists)")
                    continue
                
                # Get chord variations
                chord_variations = chord_data[chord_name]
                if not chord_variations or not isinstance(chord_variations, list):
                    batch_results['failed'].append(f"{chord_name} (invalid data format)")
                    continue
                
                first_variation = chord_variations[0]
                positions = first_variation.get('positions', [])
                
                if len(positions) != 6:
                    batch_results['failed'].append(f"{chord_name} (invalid positions array)")
                    continue
                
                # Convert to SVGuitar format
                svguitar_data = convert_fret_positions_to_svguitar(positions)
                
                # Create record
                timestamp = datetime.now().strftime('%Y-%m-%d %I:%M%p PST')
                chord_json = json.dumps(svguitar_data)
                
                new_record = {
                    'A': str(next_id),
                    'B': '',
                    'C': chord_name,
                    'D': chord_json,
                    'E': timestamp,
                    'F': str(next_order)
                }
                
                records.append(new_record)
                existing_titles.add(chord_name.lower())
                batch_results['imported'].append(chord_name)
                
                next_id += 1
                next_order += 1
                
            except Exception as e:
                logger.error(f"Error processing chord {chord_name}: {e}")
                batch_results['failed'].append(f"{chord_name} (processing error)")
                continue
        
        return batch_results, next_id, next_order
    
    def save_batch_to_sheet(self, records):
        """Save records to sheet with retry logic."""
        def save_operation():
            spread = get_spread()
            sheet = spread.worksheet('CommonChords')
            return records_to_sheet(sheet, records, is_routine_worksheet=False)
        
        return self.retry_with_backoff(save_operation)
    
    def import_all_chords(self):
        """Import all chords with batching and rate limiting."""
        try:
            # Load chord data
            chord_data = self.load_chord_data()
            all_chord_names = list(chord_data.keys())
            total_chords = len(all_chord_names)
            
            logger.info(f"Starting import of {total_chords} chords in batches of {self.batch_size}")
            logger.info(f"Rate limiting: {self.delay}s delay between batches, {self.max_retries} max retries")
            
            # Get existing data
            existing_titles, records, next_id, next_order = self.get_existing_chords()
            
            # Process in batches
            start_time = time.time()
            batches_processed = 0
            
            for i in range(0, total_chords, self.batch_size):
                batch_start = time.time()
                chord_batch = all_chord_names[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (total_chords + self.batch_size - 1) // self.batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(chord_batch)} chords)")
                
                # Process batch
                batch_results, next_id, next_order = self.process_chord_batch(
                    chord_batch, chord_data, records, next_id, next_order, existing_titles
                )
                
                # Save to sheet if any imported
                if batch_results['imported']:
                    logger.info(f"Saving batch {batch_num} to sheet...")
                    success = self.retry_with_backoff(self.save_batch_to_sheet, records)
                    
                    if success:
                        self.total_imported += len(batch_results['imported'])
                        logger.info(f"✅ Batch {batch_num} saved successfully")
                    else:
                        logger.error(f"❌ Failed to save batch {batch_num}")
                        self.total_failed += len(batch_results['imported'])
                
                self.total_skipped += len(batch_results['skipped'])
                self.total_failed += len(batch_results['failed'])
                
                batches_processed += 1
                batch_time = time.time() - batch_start
                elapsed_time = time.time() - start_time
                avg_batch_time = elapsed_time / batches_processed
                remaining_batches = total_batches - batches_processed
                eta_seconds = remaining_batches * avg_batch_time
                
                logger.info(f"Batch {batch_num} complete in {batch_time:.1f}s | "
                          f"ETA: {eta_seconds/60:.1f}m | "
                          f"Imported: {self.total_imported}, Skipped: {self.total_skipped}, Failed: {self.total_failed}")
                
                # Rate limiting delay
                if i + self.batch_size < total_chords:  # Don't delay after last batch
                    logger.info(f"Waiting {self.delay}s before next batch...")
                    time.sleep(self.delay)
            
            # Final cleanup
            invalidate_caches()
            total_time = time.time() - start_time
            
            logger.info(f"🎉 Import complete in {total_time/60:.1f} minutes!")
            logger.info(f"📊 Results: {self.total_imported} imported, {self.total_skipped} skipped, {self.total_failed} failed")
            
            return {
                'success': True,
                'imported': self.total_imported,
                'skipped': self.total_skipped,
                'failed': self.total_failed,
                'duration_minutes': total_time / 60
            }
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return {'success': False, 'error': str(e)}

def main():
    parser = argparse.ArgumentParser(description='Import all chords from TormodKv collection')
    parser.add_argument('--batch-size', type=int, default=50, 
                       help='Number of chords to process per batch (default: 50)')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay between batches in seconds (default: 2.0)')
    parser.add_argument('--max-retries', type=int, default=5,
                       help='Maximum retries for rate-limited operations (default: 5)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be imported without actually doing it')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        chord_data = {}
        with open('/home/steven/webdev/guitar/practice/gpr/chords/completeChords.json', 'r') as f:
            chord_data = json.load(f)
        logger.info(f"Would import {len(chord_data)} chords in batches of {args.batch_size}")
        logger.info(f"Estimated time: {(len(chord_data) / args.batch_size) * args.delay / 60:.1f} minutes")
        return
    
    importer = ChordImporter(
        batch_size=args.batch_size,
        delay=args.delay,
        max_retries=args.max_retries
    )
    
    results = importer.import_all_chords()
    
    if results['success']:
        print(f"\n🎸 All chords imported successfully!")
        print(f"📊 Final stats: {results['imported']} imported, {results['skipped']} skipped, {results['failed']} failed")
        print(f"⏱️  Total time: {results['duration_minutes']:.1f} minutes")
    else:
        print(f"\n❌ Import failed: {results['error']}")
        sys.exit(1)

if __name__ == '__main__':
    main()