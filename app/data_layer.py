"""
Data layer abstraction for gradual migration from Sheets to PostgreSQL.
Allows switching between data sources via environment variable.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import both data access methods
try:
    from app import sheets
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    logging.warning("Sheets module not available")

try:
    from app.services.items import ItemService
    from app.services.chord_charts import ChordChartService
    from app.services.routines import routine_service
    from app.repositories.items import ItemRepository
    from app.database import DatabaseTransaction
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("PostgreSQL services not available")

# Configuration
USE_POSTGRES = os.getenv('USE_POSTGRES', 'False').lower() == 'true'
MIGRATION_MODE = os.getenv('MIGRATION_MODE', 'sheets')  # sheets, postgres, dual

class DataLayer:
    """Unified data access layer supporting both Sheets and PostgreSQL."""
    
    def __init__(self):
        self.mode = MIGRATION_MODE
        logging.info(f"DataLayer initialized in {self.mode} mode")
        
        if self.mode == 'postgres' and not POSTGRES_AVAILABLE:
            logging.error("PostgreSQL mode requested but not available, falling back to sheets")
            self.mode = 'sheets'
        elif self.mode == 'sheets' and not SHEETS_AVAILABLE:
            logging.error("Sheets mode requested but not available, falling back to postgres")
            self.mode = 'postgres'
    
    def _get_db_id_from_item_id(self, item_id: int) -> Optional[int]:
        """Convert ItemID (Column B from sheets) to database primary key (id column)."""
        if self.mode != 'postgres':
            return item_id  # In sheets mode, just pass through
        
        try:
            from sqlalchemy import text
            with DatabaseTransaction() as db:
                result = db.execute(text('SELECT id FROM items WHERE item_id = :item_id'), {'item_id': str(item_id)}).fetchone()
                if result:
                    return result[0]  # Return database primary key
                return None
        except Exception as e:
            logging.error(f"Error converting item_id {item_id} to db_id: {e}")
            return None
    
    # Items API
    def get_all_items(self) -> List[Dict[str, Any]]:
        if self.mode == 'postgres':
            service = ItemService()
            return service.get_all_items()
        else:
            return sheets.get_all_items()
    
    def add_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == 'postgres':
            service = ItemService()
            return service.create_item(item_data)
        else:
            return sheets.add_item(item_data)
    
    def update_item(self, item_id: int, item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.mode == 'postgres':
            service = ItemService()
            return service.update_item(item_id, item_data)
        else:
            return sheets.update_item(item_id, item_data)
    
    def delete_item(self, item_id: int) -> bool:
        if self.mode == 'postgres':
            service = ItemService()
            return service.delete_item(item_id)
        else:
            return sheets.delete_item(item_id)
    
    def update_items_order(self, items: List[Dict[str, Any]]) -> bool:
        if self.mode == 'postgres':
            service = ItemService()
            return service.update_items_order(items)
        else:
            return sheets.update_items_order(items)
    
    # Chord Charts API
    def get_chord_charts_for_item(self, item_id: int) -> List[Dict[str, Any]]:
        if self.mode == 'postgres':
            # Handle comma-separated ItemIDs - search for ItemIDs that contain this ID
            from sqlalchemy import text
            from app.database import DatabaseTransaction
            
            item_id_str = str(item_id)
            charts = []
            
            with DatabaseTransaction() as db:
                # Look for exact match first, then comma-separated matches
                result = db.execute(text('''
                    SELECT chord_id, item_id, title, chord_data, created_at, order_col
                    FROM chord_charts 
                    WHERE item_id = :exact_id 
                       OR item_id LIKE :pattern1 
                       OR item_id LIKE :pattern2 
                       OR item_id LIKE :pattern3
                    ORDER BY order_col
                '''), {
                    'exact_id': item_id_str,
                    'pattern1': f'{item_id_str},%',  # "107, 61"
                    'pattern2': f'%, {item_id_str}',  # "61, 107" 
                    'pattern3': f'%, {item_id_str},%'  # "61, 107, 45"
                }).fetchall()
                
                for row in result:
                    # Parse chord_data JSON from database
                    chord_data = row[3] if row[3] else {}
                    
                    # Return proper frontend format (not Google Sheets columns)
                    chart = {
                        'id': row[0],  # chord_id as number
                        'title': row[2] or '',  # chord name
                        'chordData': chord_data,  # Full SVGuitar data object
                        'order': row[5] if row[5] is not None else 0,  # order_col
                        'createdAt': row[4].isoformat() if row[4] else '',
                        'itemId': row[1]  # Keep for reference but not used in frontend
                    }
                    
                    # Extract section metadata from chord_data if available
                    if isinstance(chord_data, dict):
                        chart['sectionId'] = chord_data.get('sectionId', '')
                        chart['sectionLabel'] = chord_data.get('sectionLabel', '')
                        chart['sectionRepeatCount'] = chord_data.get('sectionRepeatCount', '')
                        chart['hasLineBreakAfter'] = chord_data.get('hasLineBreakAfter', False)
                        chart['tuning'] = chord_data.get('tuning', 'EADGBE')
                        chart['capo'] = chord_data.get('capo', 0)
                    
                    charts.append(chart)
            
            return charts
        else:
            return sheets.get_chord_charts_for_item(item_id)
    
    def add_chord_chart(self, item_id: int, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == 'postgres':
            # Use ItemID as string directly (no conversion needed)
            service = ChordChartService()
            return service.create_chord_chart(str(item_id), chart_data)
        else:
            return sheets.add_chord_chart(item_id, chart_data)
    
    def batch_add_chord_charts(self, item_id: int, chord_charts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.mode == 'postgres':
            # Use ItemID as string directly (no conversion needed)
            service = ChordChartService()
            return service.batch_create(str(item_id), chord_charts_data)
        else:
            return sheets.batch_add_chord_charts(item_id, chord_charts_data)
    
    def update_chord_chart(self, chart_id: int, chart_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.mode == 'postgres':
            service = ChordChartService()
            return service.update_chord_chart(chart_id, chart_data)
        else:
            return sheets.update_chord_chart(chart_id, chart_data)
    
    def delete_chord_chart(self, chart_id: int) -> bool:
        if self.mode == 'postgres':
            service = ChordChartService()
            return service.delete_chord_chart(chart_id)
        else:
            return sheets.delete_chord_chart(chart_id)
    
    def update_chord_charts_order(self, item_id: int, chord_charts: List[Dict[str, Any]]) -> bool:
        if self.mode == 'postgres':
            service = ChordChartService()
            return service.update_order(str(item_id), chord_charts)
        else:
            return sheets.update_chord_charts_order(item_id, chord_charts)
    
    # Routines API
    def get_all_routines(self) -> List[Dict[str, Any]]:
        if self.mode == 'postgres':
            return routine_service.get_all_routines()
        else:
            return sheets.get_all_routines()
    
    def create_routine(self, routine_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == 'postgres':
            return routine_service.create_routine(routine_data)
        else:
            return sheets.add_routine(routine_data)
    
    def update_routine(self, routine_id: int, routine_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.mode == 'postgres':
            return routine_service.update_routine(routine_id, routine_data)
        else:
            return sheets.update_routine(routine_id, routine_data)
    
    def delete_routine(self, routine_id: int) -> bool:
        if self.mode == 'postgres':
            return routine_service.delete_routine(routine_id)
        else:
            return sheets.delete_routine(routine_id)
    
    def get_routine_with_items(self, routine_id: int) -> Optional[Dict[str, Any]]:
        if self.mode == 'postgres':
            return routine_service.get_routine_with_items(routine_id)
        else:
            return sheets.get_routine_with_items(routine_id)
    
    def get_routine_items(self, routine_id: int) -> List[Dict[str, Any]]:
        if self.mode == 'postgres':
            return routine_service.get_routine_items(routine_id)
        else:
            return sheets.get_routine_items(routine_id)
    
    def add_item_to_routine(self, routine_id: int, item_id: int, order: int = None) -> Dict[str, Any]:
        if self.mode == 'postgres':
            return routine_service.add_item_to_routine(routine_id, item_id, order)
        else:
            return sheets.add_item_to_routine(routine_id, item_id, order)
    
    def remove_item_from_routine(self, routine_id: int, item_id: int) -> bool:
        if self.mode == 'postgres':
            return routine_service.remove_item_from_routine(routine_id, item_id)
        else:
            return sheets.remove_item_from_routine(routine_id, item_id)
    
    def update_routine_items_order(self, routine_id: int, items: List[Dict[str, Any]]) -> bool:
        if self.mode == 'postgres':
            return routine_service.update_routine_items_order(routine_id, items)
        else:
            return sheets.update_routine_items_order(routine_id, items)
    
    def mark_item_complete(self, routine_id: int, item_id: int, completed: bool = True) -> bool:
        if self.mode == 'postgres':
            return routine_service.mark_item_complete(routine_id, item_id, completed)
        else:
            return sheets.mark_routine_item_complete(routine_id, item_id, completed)
    
    def reset_routine_progress(self, routine_id: int) -> bool:
        if self.mode == 'postgres':
            return routine_service.reset_routine_progress(routine_id)
        else:
            return sheets.reset_routine_progress(routine_id)
    
    # Active routine management
    def get_active_routine(self) -> Optional[Dict[str, Any]]:
        if self.mode == 'postgres':
            return routine_service.get_active_routine()
        else:
            return sheets.get_active_routine()
    
    def set_active_routine(self, routine_id: int) -> bool:
        if self.mode == 'postgres':
            return routine_service.set_active_routine(routine_id)
        else:
            return sheets.set_active_routine(routine_id)
    
    def clear_active_routine(self) -> bool:
        if self.mode == 'postgres':
            return routine_service.clear_active_routine()
        else:
            return sheets.clear_active_routine()
    
    # Statistics and utilities
    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics about items, chord charts, and routines."""
        if self.mode == 'postgres':
            item_service = ItemService()
            chord_service = ChordChartService()
            
            item_stats = item_service.get_item_stats()
            chord_stats = chord_service.get_chart_stats()
            routine_stats = routine_service.get_stats()
            
            return {
                **item_stats,
                **chord_stats,
                **routine_stats,
                'data_source': 'postgresql'
            }
        else:
            # For Sheets, we'd need to implement similar stats
            items = sheets.get_all_items()
            routines = sheets.get_all_routines()
            return {
                'total_items': len(items),
                'total_routines': len(routines),
                'data_source': 'google_sheets'
            }
    
    def get_mode_info(self) -> Dict[str, Any]:
        """Get current mode and availability information."""
        return {
            "mode": self.mode,
            "postgres_available": POSTGRES_AVAILABLE,
            "sheets_available": SHEETS_AVAILABLE,
            "use_postgres_env": USE_POSTGRES,
            "migration_mode_env": MIGRATION_MODE
        }

# Global instance
data_layer = DataLayer()