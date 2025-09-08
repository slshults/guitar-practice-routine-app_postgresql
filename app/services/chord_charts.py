from typing import List, Dict, Any, Optional
from app.services.base import BaseService
from app.repositories.chord_charts import ChordChartRepository
from app.repositories.items import ItemRepository
from app.models import ChordChart
import logging

class ChordChartService(BaseService):
    def get_for_item(self, item_id: str) -> List[Dict[str, Any]]:
        """Get chord charts for an item in Sheets format."""
        def _get_charts():
            repo = ChordChartRepository(self.db)
            return repo.get_for_item_sheets_format(item_id)
        
        return self._execute_with_transaction(_get_charts)
    
    def create_chord_chart(self, item_id: str, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single chord chart."""
        def _create_chart():
            repo = ChordChartRepository(self.db)
            charts = repo.batch_create(item_id, [chart_data])
            return repo._to_sheets_format(charts[0]) if charts else {}
        
        return self._execute_with_transaction(_create_chart)
    
    def batch_create(self, item_id: str, chord_charts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple chord charts in a single transaction."""
        def _batch_create():
            repo = ChordChartRepository(self.db)
            charts = repo.batch_create(item_id, chord_charts_data)
            return [repo._to_sheets_format(chart) for chart in charts]
        
        return self._execute_with_transaction(_batch_create)
    
    def update_chord_chart(self, chart_id: int, chart_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a chord chart with Sheets format data."""
        def _update_chart():
            repo = ChordChartRepository(self.db)
            chart = repo.update_from_sheets_format(chart_id, chart_data)
            return repo._to_sheets_format(chart) if chart else None
        
        return self._execute_with_transaction(_update_chart)
    
    def delete_chord_chart(self, chart_id: int) -> bool:
        """Delete a single chord chart."""
        def _delete_chart():
            repo = ChordChartRepository(self.db)
            return repo.delete(chart_id)
        
        return self._execute_with_transaction(_delete_chart)
    
    def update_order(self, item_id: str, chord_charts: List[Dict[str, Any]]) -> bool:
        """Update chord chart ordering for an item."""
        def _update_order():
            repo = ChordChartRepository(self.db)
            return repo.update_order(item_id, chord_charts)
        
        return self._execute_with_transaction(_update_order)
    
    def get_sections_for_item(self, item_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get chord charts grouped by section for an item."""
        def _get_sections():
            repo = ChordChartRepository(self.db)
            sections = repo.get_sections_for_item(item_id)
            
            # Convert to Sheets format
            result = {}
            for section_id, charts in sections.items():
                result[section_id] = [repo._to_sheets_format(chart) for chart in charts]
            
            return result
        
        return self._execute_with_transaction(_get_sections)
    
    def delete_all_for_item(self, item_id: str) -> int:
        """Delete all chord charts for an item."""
        def _delete_all():
            repo = ChordChartRepository(self.db)
            return repo.delete_all_for_item(item_id)
        
        return self._execute_with_transaction(_delete_all)
    
    def get_chart_stats(self) -> Dict[str, Any]:
        """Get statistics about chord charts."""
        def _get_stats():
            repo = ChordChartRepository(self.db)
            item_repo = ItemRepository(self.db)
            
            total_charts = repo.count()
            total_items = item_repo.count()
            
            # Get items with and without charts
            items_with_charts = self.db.query(ChordChart.item_id).distinct().count()
            items_without_charts = total_items - items_with_charts
            
            return {
                'total_chord_charts': total_charts,
                'items_with_charts': items_with_charts,
                'items_without_charts': items_without_charts,
                'avg_charts_per_item': total_charts / total_items if total_items > 0 else 0
            }
        
        return self._execute_with_transaction(_get_stats)