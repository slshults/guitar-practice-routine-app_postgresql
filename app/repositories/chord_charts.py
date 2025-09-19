from typing import List, Optional, Dict, Any
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload
from app.models import ChordChart, Item
from app.repositories.base import BaseRepository
import json
import logging

class ChordChartRepository(BaseRepository):
    def __init__(self, db_session=None):
        super().__init__(ChordChart, db_session)
    
    def get_by_id(self, id: int) -> Optional[ChordChart]:
        """Override to use chord_id instead of id."""
        return self.db.query(ChordChart).filter(ChordChart.chord_id == id).first()
    
    def delete(self, id: int) -> bool:
        """Override to use chord_id instead of id."""
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False
    
    def get_for_item(self, item_id: str) -> List[ChordChart]:
        """Get all chord charts for an item, ordered by order column."""
        # Handle comma-separated ItemIDs - search for ItemIDs that contain this ID
        from sqlalchemy import or_, and_
        item_id_str = str(item_id)

        return self.db.query(ChordChart).filter(
            or_(
                ChordChart.item_id == item_id_str,                    # Exact match: "92"
                ChordChart.item_id.like(f'{item_id_str},%'),         # Starts with: "92, 100"
                ChordChart.item_id.like(f'%, {item_id_str}'),        # Ends with: "100, 92"
                ChordChart.item_id.like(f'%, {item_id_str},%')       # Middle: "100, 92, 45"
            )
        ).order_by(ChordChart.order_col).all()
    
    def get_for_item_sheets_format(self, item_id: str) -> List[Dict[str, Any]]:
        """Get chord charts in Google Sheets format for API compatibility."""
        charts = self.get_for_item(item_id)
        return [self._to_sheets_format(chart) for chart in charts]
    
    def batch_create(self, item_id: str, chord_charts_data: List[Dict[str, Any]]) -> List[ChordChart]:
        """Create multiple chord charts in a single transaction."""
        created_charts = []
        try:
            for i, chart_data in enumerate(chord_charts_data):
                # Handle three formats: Frontend format, Direct format, and Sheets format
                if 'title' in chart_data and 'fingers' in chart_data:
                    # Frontend format (same as sheets version expected)
                    # Extract the title and build chord_data from SVGuitar properties
                    chord_data_obj = {
                        'fingers': chart_data.get('fingers', []),
                        'barres': chart_data.get('barres', []),
                        'tuning': chart_data.get('tuning', 'EADGBE'),
                        'capo': chart_data.get('capo', 0),
                        'startingFret': chart_data.get('startingFret', 1),
                        'numFrets': chart_data.get('numFrets', 5),
                        'numStrings': chart_data.get('numStrings', 6),
                        'openStrings': chart_data.get('openStrings', []),
                        'mutedStrings': chart_data.get('mutedStrings', []),
                        'sectionId': chart_data.get('sectionId'),
                        'sectionLabel': chart_data.get('sectionLabel'),
                        'sectionRepeatCount': chart_data.get('sectionRepeatCount'),
                        'hasLineBreakAfter': chart_data.get('hasLineBreakAfter', False)
                    }
                    chart = ChordChart(
                        item_id=item_id,
                        title=chart_data.get('title', f'Chord {i+1}'),
                        chord_data=chord_data_obj,
                        order_col=chart_data.get('order', i)
                    )
                elif 'title' in chart_data and 'chord_data' in chart_data:
                    # Direct format (nested chord_data)
                    chart = ChordChart(
                        item_id=item_id,
                        title=chart_data.get('title', f'Chord {i+1}'),
                        chord_data=chart_data.get('chord_data', {}),
                        order_col=chart_data.get('order', i)
                    )
                else:
                    # Sheets format (from migration)
                    chart = ChordChart(
                        item_id=item_id,
                        title=chart_data.get('C', f'Chord {i+1}'),
                        chord_data=chart_data.get('D', {}),
                        order_col=int(chart_data.get('F', i)) if chart_data.get('F') else i
                    )
                
                self.db.add(chart)
                created_charts.append(chart)
            
            self.db.commit()
            
            # Refresh all created charts
            for chart in created_charts:
                self.db.refresh(chart)
                
            return created_charts
            
        except Exception as e:
            self.db.rollback()
            logging.error(f"Error in batch_create_chord_charts: {str(e)}")
            raise
    
    def update_order(self, item_id: str, chord_charts: List[Dict[str, Any]]) -> bool:
        """Update chord chart ordering for an item."""
        try:
            order_map = {chart['id']: i for i, chart in enumerate(chord_charts)}
            
            for chart_id, new_order in order_map.items():
                self.db.query(ChordChart).filter(
                    and_(ChordChart.chord_id == chart_id, ChordChart.item_id == item_id)
                ).update({ChordChart.order_col: new_order})
                
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
    
    def update_from_sheets_format(self, chart_id: int, sheets_data: Dict[str, Any]) -> Optional[ChordChart]:
        """Update chord chart using Sheets format data."""
        chart_data = self._from_sheets_format(sheets_data)
        return self.update(chart_id, **chart_data)
    
    def get_sections_for_item(self, item_id: str) -> Dict[str, List[ChordChart]]:
        """Get chord charts grouped by section for an item."""
        charts = self.get_for_item(item_id)
        sections = {}
        
        for chart in charts:
            section_id = chart.section_id or 'default'
            if section_id not in sections:
                sections[section_id] = []
            sections[section_id].append(chart)
            
        return sections
    
    def batch_delete(self, chord_ids: List[int]) -> int:
        """Delete multiple chord charts and return count of deleted charts."""
        count = self.db.query(ChordChart).filter(ChordChart.chord_id.in_(chord_ids)).count()
        self.db.query(ChordChart).filter(ChordChart.chord_id.in_(chord_ids)).delete()
        self.db.commit()
        return count
    
    def delete_all_for_item(self, item_id: str) -> int:
        """Delete all chord charts for an item."""
        count = self.db.query(ChordChart).filter(ChordChart.item_id == item_id).count()
        self.db.query(ChordChart).filter(ChordChart.item_id == item_id).delete()
        self.db.commit()
        return count
    
    def get_by_section(self, item_id: str, section_id: str) -> List[ChordChart]:
        """Get chord charts for a specific section within an item."""
        charts = self.get_for_item(item_id)
        return [chart for chart in charts if chart.section_id == section_id]
    
    # Format conversion helpers
    def _to_sheets_format(self, chart: ChordChart) -> Dict[str, Any]:
        """Convert SQLAlchemy ChordChart to frontend API format (flattened)."""
        # Start with base chart info
        result = {
            'id': str(chart.chord_id),     # Frontend uses 'id'
            'itemId': chart.item_id,       # Frontend uses 'itemId'
            'title': chart.title or '',    # Title
            'order': chart.order_col,      # Frontend uses 'order'
            'createdAt': chart.created_at.isoformat() if chart.created_at else '',
        }
        
        # Flatten chord_data properties to top level (matching frontend expectations)
        chord_data = chart.chord_data or {}

        # Clean finger data - remove None values from finger arrays
        raw_fingers = chord_data.get('fingers', [])
        clean_fingers = []
        for finger in raw_fingers:
            if isinstance(finger, list) and len(finger) >= 2:
                # Filter out None values and keep only valid numbers
                clean_finger = [x for x in finger if x is not None]
                if len(clean_finger) >= 2:  # Must have at least string and fret
                    clean_fingers.append(clean_finger)
            else:
                clean_fingers.append(finger)  # Keep non-list items as-is

        result.update({
            'fingers': clean_fingers,
            'barres': chord_data.get('barres', []),
            'tuning': chord_data.get('tuning', 'EADGBE'),
            'capo': chord_data.get('capo', 0),
            'startingFret': chord_data.get('startingFret', 1),
            'numFrets': chord_data.get('numFrets', 5),
            'numStrings': chord_data.get('numStrings', 6),
            'openStrings': chord_data.get('openStrings', []),
            'mutedStrings': chord_data.get('mutedStrings', []),
            'sectionId': chord_data.get('sectionId'),
            'sectionLabel': chord_data.get('sectionLabel'),
            'sectionRepeatCount': chord_data.get('sectionRepeatCount'),
            'hasLineBreakAfter': chord_data.get('hasLineBreakAfter', False)
        })
        
        return result
    
    def _from_sheets_format(self, sheets_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Sheets API format to SQLAlchemy format."""
        return {
            'title': sheets_data.get('C', ''),
            'chord_data': sheets_data.get('D', {}),
            'order_col': int(sheets_data.get('F', 0)) if sheets_data.get('F') else 0
        }