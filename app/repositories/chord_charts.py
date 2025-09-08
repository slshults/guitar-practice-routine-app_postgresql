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
    
    def get_for_item(self, item_id: str) -> List[ChordChart]:
        """Get all chord charts for an item, ordered by order column."""
        return self.db.query(ChordChart).filter(
            ChordChart.item_id == item_id
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
                # Handle both direct format and Sheets format
                if 'title' in chart_data and 'chord_data' in chart_data:
                    # Direct format
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
        """Convert SQLAlchemy ChordChart to Sheets API format."""
        return {
            'A': str(chart.chord_id),     # ChordID
            'B': str(chart.item_id),      # ItemID
            'C': chart.title or '',       # Title
            'D': chart.chord_data or {},  # ChordData (JSON)
            'E': chart.created_at.isoformat() if chart.created_at else '',  # CreatedAt
            'F': str(chart.order_col)     # Order
        }
    
    def _from_sheets_format(self, sheets_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Sheets API format to SQLAlchemy format."""
        return {
            'title': sheets_data.get('C', ''),
            'chord_data': sheets_data.get('D', {}),
            'order_col': int(sheets_data.get('F', 0)) if sheets_data.get('F') else 0
        }