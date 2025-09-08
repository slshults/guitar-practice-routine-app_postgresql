from typing import List, Optional, Dict, Any
from sqlalchemy import func, and_
from app.models import Item, ChordChart
from app.repositories.base import BaseRepository

class ItemRepository(BaseRepository):
    def __init__(self, db_session=None):
        super().__init__(Item, db_session)
    
    def get_all_ordered(self) -> List[Item]:
        """Get all items ordered by order column, then title."""
        return self.db.query(Item).order_by(Item.order, Item.title).all()
    
    def get_lightweight(self) -> List[Dict[str, Any]]:
        """Get minimal item data for list views (mimics Sheets format)."""
        items = self.db.query(Item.id, Item.title).order_by(Item.order, Item.title).all()
        return [{'A': str(item.id), 'C': item.title} for item in items]
    
    def get_sheets_format(self) -> List[Dict[str, Any]]:
        """Get all items in Google Sheets format for API compatibility."""
        items = self.get_all_ordered()
        return [self._to_sheets_format(item) for item in items]
    
    def create_from_sheets_format(self, sheets_data: Dict[str, Any]) -> Item:
        """Create item from Google Sheets format data."""
        item_data = self._from_sheets_format(sheets_data)
        return self.create(**item_data)
    
    def update_from_sheets_format(self, item_id: int, sheets_data: Dict[str, Any]) -> Optional[Item]:
        """Update item using Google Sheets format data."""
        item_data = self._from_sheets_format(sheets_data)
        return self.update(item_id, **item_data)
    
    def update_order(self, items: List[Dict[str, Any]]) -> bool:
        """Batch update item ordering."""
        try:
            for item_data in items:
                item_id = int(item_data['A'])
                new_order = int(item_data.get('G', 0)) if item_data.get('G') else 0
                self.db.query(Item).filter(Item.id == item_id).update({
                    Item.order: new_order
                })
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
    
    def search_by_title(self, search_term: str) -> List[Item]:
        """Search items by title (case-insensitive)."""
        return self.db.query(Item).filter(
            Item.title.ilike(f'%{search_term}%')
        ).order_by(Item.title).all()
    
    def get_by_tuning(self, tuning: str) -> List[Item]:
        """Get items filtered by tuning."""
        return self.db.query(Item).filter(Item.tuning == tuning).order_by(Item.title).all()
    
    def get_with_chord_charts(self, item_id: int) -> Optional[Item]:
        """Get item with chord charts eagerly loaded."""
        return self.db.query(Item).filter(Item.id == item_id).first()
    
    # Format conversion helpers
    def _to_sheets_format(self, item: Item) -> Dict[str, Any]:
        """Convert SQLAlchemy Item to Sheets API format."""
        return {
            'A': str(item.id),
            'B': item.item_id or '',
            'C': item.title or '',
            'D': item.notes or '',
            'E': item.duration or '',
            'F': item.description or '',
            'G': str(item.order),
            'H': item.tuning or '',
            'I': item.songbook or ''
        }
    
    def _from_sheets_format(self, sheets_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Sheets API format to SQLAlchemy format."""
        return {
            'item_id': sheets_data.get('B', ''),
            'title': sheets_data.get('C', ''),
            'notes': sheets_data.get('D', ''),
            'duration': sheets_data.get('E', ''),
            'description': sheets_data.get('F', ''),
            'order': int(sheets_data.get('G', 0)) if sheets_data.get('G') else 0,
            'tuning': sheets_data.get('H', ''),
            'songbook': sheets_data.get('I', '')
        }