# Guitar Practice App - API Mismatch Checklist
*PostgreSQL vs Sheets Version Comparison*
*Generated: 2024-09-09*

## ✅ MATCHED ROUTES (Working Correctly)

| Route | HTTP Methods | Function Name | Status |
|-------|-------------|---------------|--------|
| `/` | GET | `index()` | ✅ Match |
| `/api/items` | GET, POST | `items()` | ✅ Match |
| `/api/items/lightweight` | GET | `items_lightweight()` | ✅ Match |
| `/api/items/order` | PUT | `update_items_order()` vs `order_items()` | ⚠️ Function name differs |
| `/api/items/<item_id>` | GET, PUT, DELETE | `item()` | ✅ Match |
| `/api/routines` | GET, POST | `routines()` | ✅ Match |
| `/api/routines/<routine_id>` | GET, PUT, DELETE | `routine()` vs `routine_operations()` | ⚠️ Function name differs |
| `/api/routines/<routine_id>/items` | GET, POST | `routine_items()` vs `add_routine_item()` (POST) | ⚠️ Consolidated vs separate |
| `/api/routines/<routine_id>/items/<item_id>` | DELETE | `routine_item()` | ✅ Match |
| `/api/routines/<routine_id>/items/order` | PUT | `update_routine_items_order()` | ✅ Match |
| `/api/routines/<routine_id>/items/<item_id>/complete` | PUT | `mark_routine_item_complete()` vs `toggle_item_complete()` | ⚠️ Function name differs |
| `/api/routines/<routine_id>/reset` | POST | `reset_routine_progress()` | ✅ Match |
| `/api/practice/active-routine` | GET, POST, DELETE | `active_routine()` vs `get_active_routine_with_details()` | ⚠️ Consolidated vs separate |
| `/api/practice/active-routine/lightweight` | GET | `get_active_routine_lightweight()` | ✅ Match |
| `/api/routines/active` | GET | `get_active_routine_alt()` vs `get_active_routine_route()` | ⚠️ Function name differs |
| `/api/routines/<routine_id>/active` | PUT | `set_routine_active_status()` vs `set_routine_active_route()` | ⚠️ Function name differs |
| `/api/auth/status` | GET | `auth_status()` | ✅ Match |
| `/authorize` | GET | `authorize()` | ✅ Match |
| `/oauth2callback` | GET | `oauth2callback()` | ✅ Match |
| `/logout` | GET | `logout()` vs `logout_and_redirect()` | ⚠️ Function name differs |
| `/api/debug/log` | POST | `debug_log()` | ✅ Match |
| `/api/chord-charts/common/search` | GET | `search_common_chords()` | ✅ Match |
| `/api/items/<item_id>/chord-charts` | GET, POST | `item_chord_charts()` | ✅ Match |
| `/api/chord-charts/<int:chart_id>` | PUT, DELETE | `chord_chart()` | ✅ Match |
| `/api/items/<item_id>/chord-charts/order` | PUT | `update_chord_charts_order()` | ✅ Match |
| `/api/chord-charts/batch-delete` | POST | `batch_delete_chord_charts()` | ✅ Match (JUST FIXED!) |

## ❌ MISSING ROUTES (Need Implementation)

| Route | HTTP Methods | Function Name | Priority | Notes |
|-------|-------------|---------------|----------|-------|
| `/api/routines/<routine_id>/details` | GET | `get_routine_with_details()` | HIGH | Routine details with items |
| `/api/routines/<routine_id>/order` | PUT | `update_routine_order_route()` | MEDIUM | Routine ordering |
| `/api/routines/<routine_id>/items/<item_id>` | PUT | `routine_item()` | MEDIUM | Update routine item |
| `/api/items/<item_id>/notes` | GET, POST | `save_item_notes()` | HIGH | Item notes functionality |
| `/items` | GET | `items_page()` | LOW | Page route |
| `/test_sheets` | GET | `test_sheets()` | LOW | Testing route |
| `/api/chord-charts/common` | GET | Get all common chords | MEDIUM | Full common chords list |
| `/api/chord-charts/seed` | POST | Seed CommonChords | LOW | Development utility |
| `/api/chord-charts/bulk-import` | POST | Import from TormodKv | LOW | Bulk import |
| `/api/chord-charts/bulk-import-local` | POST | Local bulk import | LOW | Local import |
| `/api/chord-charts/copy` | POST | Copy chords between songs | MEDIUM | Chord copying |
| `/api/autocreate-chord-charts` | POST | AI chord creation | HIGH | Major feature |

## ⚠️ ROUTE MISMATCHES (Different Patterns)

| Sheets Version | PostgreSQL Version | Issue | Priority |
|---------------|-------------------|-------|----------|
| `/api/routines/<routine_id>/items` (POST) | Same, but different function | Consolidated vs separate functions | LOW |
| `/api/practice/active-routine` (GET) | Same, but different function | Consolidated vs separate functions | LOW |

## 🆕 POSTGRESQL-ONLY ROUTES (Not in Sheets)

| Route | HTTP Methods | Function Name | Purpose |
|-------|-------------|---------------|---------|
| `/api/system/status` | GET | `system_status()` | PostgreSQL system info |
| `/api/migration/switch/<mode>` | POST | `switch_mode()` | Migration utilities |
| `/api/health` | GET | `health_check()` | Health monitoring |
| `/api/dev/clear-cache` | POST | `clear_cache()` | Development utility |
| `/api/dev/migrate-test` | POST | `migrate_test()` | Migration testing |
| `/api/items/<item_id>/chord-charts/batch` | POST | `batch_add_chord_charts()` | Batch chord creation |
| `/api/open-folder` | POST | `open_folder()` | Songbook folder opening |

## 🎯 PRIORITY ACTION ITEMS

### HIGH Priority (Likely Missing Functionality)
1. **`/api/items/<item_id>/notes`** - Item notes functionality (users likely expect this)
2. **`/api/routines/<routine_id>/details`** - Detailed routine information 
3. **`/api/autocreate-chord-charts`** - Major AI chord creation feature

### MEDIUM Priority (Nice to Have)
4. **`/api/chord-charts/common`** - Full common chords list
5. **`/api/chord-charts/copy`** - Copy chords between songs
6. **`/api/routines/<routine_id>/order`** - Routine ordering

### LOW Priority (Development/Testing)
7. Function name differences (mostly cosmetic)
8. Bulk import features 
9. Development utilities

## 📝 NOTES
- Most core functionality is present and working
- The biggest gaps are in notes functionality and chord management features
- PostgreSQL version has additional system/migration utilities
- Focus on HIGH priority items first as these likely impact user experience

---
*This checklist should be updated as routes are implemented and tested.*