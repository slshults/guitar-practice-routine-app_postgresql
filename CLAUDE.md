# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Claude Model Coordination for Token Efficiency

### Using the Task Tool for Implementation Work

#### Division of Responsibilities

This is IMPORTANT for managing rate-limiting and billing efficiency. **Sonnet 4 should be the default model** since Task tool calls are billed under the calling model's usage:

**Sonnet 4 Role** claude-sonnet-4-20250514 (Default & Implementation):
- File editing and code changes
- Direct implementation of planned features
- Routine refactoring and code updates
- Following established patterns and conventions
- Executing well-defined tasks with clear requirements
- Basic debugging and troubleshooting
- Most day-to-day development work

**Opus 4.1 Role** claude-opus-4-1-20250805 (Complex Analysis via Task Tool):
- Complex analysis and architectural decisions
- Multi-file code investigation and understanding
- Task planning and breaking down requirements
- Code review and verification of implementations
- Handling complex debugging and system-level issues
- Multi-system reasoning and integration problems

#### When to Use the Task Tool

**Sonnet should delegate to Opus for:**
- Initial codebase exploration and analysis
- Complex architectural decisions
- Multi-system debugging
- Planning and requirement analysis
- Tasks requiring deep reasoning about system interactions
- Complex refactoring that affects multiple files/systems

**Sonnet should handle directly:**
- Making edits to existing files
- Implementing features with clear requirements
- Following established patterns (e.g., adding new API endpoints)
- Routine code updates and maintenance tasks
- Straightforward bug fixes and improvements

#### Best Practices

1. **Clear Task Definitions**: When using the Task tool, provide specific, actionable instructions
2. **Context Preservation**: Include relevant file paths, function names, and implementation details
3. **Pattern References**: Point Sonnet to existing examples in the codebase to follow
4. **Success Criteria**: Define what "done" looks like for the delegated task

### Debuggging:

When you hand off to Opus 4.1 for troubleshooting, please remind them to:
- Review the current conversation thus far
- Review the project CLAUDE.md file
- Tail `logs.gpr` to view the details of the most recent test
- Search the web for any details needed about how SVGuitar works as of late 2025 (do not make assumptions, your training data set is outdated)
This approach helps us stay within API rate limits while getting the best capabilities from both model types.

## Application Overview

This is a **Guitar Practice Routine App** - a web application that helps guitarists manage practice routines, exercises, and guitar-specific content like chord charts.

**Note**: This is the PostgreSQL port of the original Google Sheets-based application. We're currently in the process of migrating from Google Sheets API to PostgreSQL for improved performance and more traditional database operations. 

So, when we're fixing bugs, don't try to re-engineer it. Just refer to the code in the sheets version of the app to see how it worked correctly, and correctly port it for this postgres version of the app: https://github.com/slshults/guitar-practice-routine-app_sheets

## Tech Stack

- **Backend**: Flask (Python) with PostgreSQL database (migrating from Google Sheets API)
- **Frontend**: React 18.2.0 + Vite 4.x build system + Tailwind CSS
- **Authentication**: To be determined (previously Google OAuth2 for Sheets access)
- **Guitar Features**: SVGuitar library for chord chart rendering
- **UI Components**: Custom component library with Radix UI primitives
- **Analytics**: PostHog for event tracking and user behavior analysis (MCP integration enabled for direct API access)

## Development Commands

### Start Development Environment
```bash
./gpr.sh                 # Starts Flask server + Vite watcher (recommended)
```

### Environment Setup
- Set `ANTHROPIC_API_KEY` in `.env` file for autocreate chord charts feature
- API key can be obtained from [Anthropic Console](https://console.anthropic.com/)

### Frontend Build Commands
```bash
npm run build           # Build production assets
npm run watch           # Watch mode for development
```

### Backend Commands
```bash
python run.py           # Start Flask server only (port 5000)
```

## Architecture

### Data Flow
The application has been **migrated to PostgreSQL as its database** with a **DataLayer abstraction** for seamless data source switching. The database includes:
- `Items` table: Practice items (exercises, songs, techniques)
- `Routines` table: Practice routine metadata  
- `RoutineItems` table: Junction table for routine-item relationships
- `ActiveRoutine` table: Tracks currently active routine
- `ChordCharts` table: Chord diagrams linked to practice items

**Data Flow**: React → Flask API routes → **DataLayer** (`app/data_layer.py`) → PostgreSQL Services/Repositories → PostgreSQL

### Frontend Structure
- **Path Aliases**: Use `@components`, `@hooks`, `@ui`, `@lib`, `@contexts` for clean imports
- **State Management**: React Context API (NavigationContext) + custom hooks
- **Component Pattern**: Modular components with separation between UI and business logic
- **Key Hooks**: `usePracticeItems`, `useActiveRoutine` for data management

### Backend Structure
- `run.py`: Flask application runner
- `app/routes.py`: API endpoints and HTTP request handling
- `app/sheets.py`: Google Sheets data layer (acts as ORM)
- `app/__init__.py`: Flask app initialization and OAuth setup

## Key Files and Locations

### Configuration Files
- `vite.config.js`: Frontend build configuration with path aliases
- `tailwind.config.js`: Tailwind CSS configuration
- `pyproject.toml`: Python dependencies and project metadata

### Core Components
- `app/static/js/components/PracticePage.jsx`: Main practice session interface
- `app/static/js/components/ChordChartEditor.jsx`: Interactive chord diagram editor
- `app/static/js/components/ChordGrid.jsx`: Chord chart display component
- `app/static/js/hooks/`: Custom React hooks for data fetching

### Data Layer
- `app/data_layer.py`: **DataLayer abstraction** - unified interface for both data sources
- `app/services/`: PostgreSQL business logic layer (ItemService, ChordChartService, etc.)
- `app/repositories/`: SQLAlchemy ORM data access layer 
- `app/models.py`: SQLAlchemy database models
- `app/sheets.py`: Legacy Google Sheets interactions (fallback mode)

## Development Workflow

### Multi-Process Development
The `gpr.sh` script runs:
1. Flask server with auto-reload (port 5000)
2. Vite build watcher for frontend assets
3. Python file watcher for backend changes

### Authentication Flow
- Legacy: OAuth2 flow for Google Sheets access (being removed)
- New authentication system: To be determined for PostgreSQL version

### API Endpoints
- `/api/items/*`: CRUD operations for practice items
- `/api/routines/*`: CRUD operations for practice routines
- `/api/practice/active-routine`: Get/set active practice routine
- `/api/auth/status`: Check authentication status
- `/api/items/<id>/chord-charts`: Get/create chord charts for practice items
- `/api/chord-charts/<id>`: Delete chord charts
- `/api/items/<id>/chord-charts/order`: Reorder chord charts  
- `/api/autocreate-chord-charts`: Upload files for AI-powered chord chart creation (requires ANTHROPIC_API_KEY)

## Special Considerations

### PostgreSQL Database (Migration Complete)
- **Status**: Migration completed - all tables migrated from Google Sheets using **exact 1:1 replica approach**
- **CRITICAL LESSON**: Stop over-engineering migrations - use exact sheet structure to avoid massive code refactoring
- **Schema**: Uses original Google Sheets column names (chord_id, item_id as string, order_col) for minimal code changes
- **Comma-separated ItemIDs**: Preserved exactly as "107, 61" format with LIKE pattern matching in queries
- Traditional relational database design with proper foreign key relationships
- Improved performance over sheet-based operations
- Standard SQL operations and ACID compliance
- Better support for concurrent access and complex queries

#### DataLayer Architecture Pattern
- **`app/data_layer.py`**: Unified interface supporting both postgres and sheets modes
- **Critical**: API routes MUST use DataLayer, never import sheets functions directly
- **ItemID Conversion**: DataLayer handles Google Sheets ItemID → PostgreSQL primary key conversion
- **Mode Detection**: Automatically switches based on environment variables (`MIGRATION_MODE=postgres`)

#### Common DataLayer Issues
**Symptom**: API returns wrong/empty data despite correct database contents
**Root Cause**: Routes importing sheets functions directly instead of using DataLayer
**Fix Pattern**:
```python
# WRONG (bypasses DataLayer):
from app.sheets import get_chord_charts_for_item
charts = get_chord_charts_for_item(item_id)

# CORRECT (uses DataLayer):
from app.data_layer import DataLayer
data_layer = DataLayer() 
charts = data_layer.get_chord_charts_for_item(item_id)
```

#### Migration Data Integrity Rules
- **CRITICAL:** Database tables must preserve exact Google Sheets structure
- **NO SORTING:** Repository/service layers should not sort data - preserve insertion order
- **Order Column:** Contains drag-and-drop values with gaps (0,1,2,3,5,6...) - use for display logic, not sorting
- **Physical Row Preservation:** Database should mirror exact physical sheet row sequence
- **CommonChords Migration:** Use `migrate_common_chords.py` with rate limiting for all 12,708+ records

### File Path Handling
- WSL-friendly path mapping for Windows folders (see `app/routes.py`)
- Local songbook folder linking supported

### Guitar-Specific Features
- SVGuitar integration for chord chart rendering
- Tuning tracking and display
- Chord chart editor with interactive grid interface
- **Autocreate chord charts**: Upload PDFs/images → Claude analyzes files → automatically creates chord charts with proper sections, tuning, and fingerings

### Build and Assets
- Vite compiles React/JSX and outputs to `app/static/`
- Tailwind CSS compiled to `app/static/css/main.css`
- Hot reloading supported for both frontend and backend

Here's a map of the columns for our Items sheet and routine sheets.  This is what our columns are now, for each sheet.

**ActiveRoutine**
- Column A: ID (The ID of the currently active routine)

**Routines**
- Column A: ID (routine ID)
- Column B: Routine Name
- Column C: Creation timestamp
- Column D: order*

**Items Sheet:**
- Column A: ID
- *Column B: Item ID*
- Column C: Title
- Column D: Notes
- Column E: Duration
- Column F: Description
- Column G: order*
- Column H: Tuning
- Column I: Songbook

**Routine Sheets:**
- Column A: ID (reference to Routines sheet)
- *Column B: Item ID* (reference to Items sheet)
- Column C: order*
- Column D: completed

- The "order" column is where we track the order in which the items are displayed on the page. This ties in with our drag-and-drop functionality. When we reorder with drag-and-drop, we only update the 'order' column, we do not try to reorder entire rows in the spreadsheet.

- Google Sheets forces us to use the name of each sheet to find it.  We were having problems with Routine Sheet names, so we decided to give each routine sheet a number as a name. The number used as the name for the routine sheet is the routine's ID from column `A` of the `Routines` index sheet.  Let me know of any questions about this. It's odd, but less clunky than trying to use the name of the routine typed by the user. (We're storing the name of the routine given by the user in column `B` of the `Routines` index sheet.)

  - So, we're using an ID too look up the sheet, but that ID is actually a sheet name as well. Let me know of any questions.  We still have many changes to make for this, but I've found we're more effective if we fix it as we go, so we can test each change and keep things under control.

IMPORTANT:
- No need to run npm to update after changes, the server is running and we have watchers in place to make updates for us as needed while we're developing.

- Please don't use `git` commands without discussing it together first. I usually prefer to run commits and pushes in and external terminal window. Thanks.

- You often try `python` first, which doesn't work, so just start with `python3`

- If we ask Opus 4 for debugging help, please remind them not to try to start the server because it's already running and watchers are taking care of updates.

- NEVER delete spreadsheet items. If you think something needs to be deleted, check with me first. In actuality, you we probably just need to change an ID instead of deleting.

- Contextual reminder: In guitar we count strings in order from high pitch to low, so the string on the right side of our charts is string one. Likewise with frets, so fret one is at the top, and when we go "up" a fret, that means the next fret downward on the chart

## SVGuitar Chord Chart Sizing

  The chord chart editor uses a three-part sizing system that must be kept
  synchronized:

  ### To Adjust Chart Size:
  1. **SVGuitar Config** (`defaultChartConfig` in ChordChartEditor.jsx):
     - `width` and `height` - Sets the base SVG dimensions
     - Current: 220 x 310

  2. **CSS Containers** (both Editor and Result sections):
     - Chart containers: `w-52 h-80` (208px x 320px)
     - Tuning letter containers: `w-52` (to match chart width)

  3. **Post-Processing Constraints** (`updateCharts` function):
     - `maxWidth` and `maxHeight` - Limits SVG size to fit containers
     - Current: 208px x 320px (matches CSS container dimensions)

  ### Example Size Change:
  To make charts larger, update all three in proportion:
  - SVGuitar config: 220x310 → 240x340
  - CSS containers: w-52 h-80 → w-56 h-84
  - Post-processing: 208x320 → 224x336

  **Note**: All three must be synchronized or charts will be
  clipped/distorted. The CSS container size should be slightly smaller than
  SVGuitar config to allow proper scaling.

## Chord Chart System (NEW)

### Overview
The application includes a comprehensive chord chart management system with **section organization** for chord progressions. Users can create labeled sections (Verse, Chorus, etc.) with repeat counts and save chord diagrams within each section.

### Autocreate System Architecture (Updated)
The autocreate chord charts feature uses a **3-path architecture** for optimal processing:

1. **`chord_charts`** - Visual chord diagrams (processed by Opus 4.1)
   - Hand-drawn or printed chord reference sheets
   - Uses visual analysis to extract exact finger positions
   
2. **`chord_names`** - Chord symbols above lyrics (processed by Sonnet 4)  
   - Lyrics with chord names like G, C, Am, F7, etc.
   - Uses CommonChords database lookup for standard tuning (EADGBE)
   - Preserves actual chord names and song section structure
   
3. **`tablature`** - Actual guitar tablature notation (processed by Sonnet 4)
   - Fret numbers on horizontal string lines (e.g., E|--0--3--0--|)
   - Creates generic "Chord1", "Chord2" names when chord names unavailable

**Key Design Principles:**
- **Cost efficiency**: Strategic Opus/Sonnet usage prevents rate limiting
- **Complete file processing**: Reads entire file, doesn't stop after finding chord charts
- **Tuning awareness**: CommonChords for standard, direct patterns for alternate tunings

### Common Regression Fixes

#### Chord Chart Updates Not Visible Until Page Refresh
**Symptom**: Changes to chord charts (editing, line breaks, etc.) aren't reflected in the UI until the page is refreshed.

**Root Cause**: This happens when the comma-separated ItemID feature breaks the `update_chord_chart` function in `sheets.py`. The function tries to parse corrupted ItemID data like `'71, 101'` as a single integer.

**Fix**: The `update_chord_chart` function in `sheets.py` now handles comma-separated ItemIDs properly:
```python
# Handle comma-separated ItemIDs properly - preserve all existing ItemIDs
item_id_raw = str(chart_to_update['B']).strip()

# For the return value, we need a single ItemID - use the first one
if ',' in item_id_raw:
    # Comma-separated ItemIDs - use the first one for the return value
    first_item_id = item_id_raw.split(',')[0].strip()
else:
    first_item_id = item_id_raw
```

**Key Points**:
- Chord charts can belong to multiple items via comma-separated ItemIDs in column B
- When updating a chord chart, preserve all existing ItemIDs 
- For return values, use the first ItemID from the comma-separated list
- The `get_chord_charts_for_item` function correctly handles comma-separated ItemIDs

### Database Schema
**ChordCharts Sheet:**
- Column A: ChordID (unique identifier)
- Column B: ItemID (references Items sheet Column A)
- Column C: Title (chord name like "C Major", "Am7", etc.)
- Column D: ChordData (JSON with fingers, barres, tuning, capo, **section metadata**)
- Column E: CreatedAt (timestamp)
- Column F: Order (display order within an item)

**Section Metadata in ChordData JSON:**
- `sectionId`: Unique section identifier (e.g., "section-1750638363428")
- `sectionLabel`: User-defined section name (e.g., "Verse", "Chorus")
- `sectionRepeatCount`: Repeat notation (e.g., "x4", "x2")

### Architecture
- **Backend**: Full CRUD functions in `sheets.py` including `update_chord_chart()` for section persistence
- **API**: RESTful endpoints for creating, reading, updating, deleting chord charts
- **Frontend**: Interactive chord chart editor with real-time section management
- **Display**: Organized by labeled sections with repeat counts, 4-per-row grid within sections
- **Travel-friendly**: Clean separation allows browsing chord charts directly in Google Sheets

### Key Components
- `ChordChartEditor.jsx`: Interactive chord diagram editor with click detection
- `PracticePage.jsx`: Section-aware chord chart display with debounced updates
- Chord chart API endpoints in `routes.py` including `PUT /api/chord-charts/<id>`
- ChordCharts CRUD functions in `sheets.py` including `update_chord_chart()`

### Section System Features
- **Real-time editing**: Section labels and repeat counts update immediately in UI
- **Debounced persistence**: Backend updates use 500ms debounce to prevent keystroke conflicts
- **Automatic grouping**: Chord charts automatically grouped by section metadata
- **Persistent sections**: Section data stored in each chord's JSON and survives page refreshes

### Data Flow
1. User creates chord in interactive editor
2. Clicks "Add Chord Chart" to save via API
3. Chart data stored as JSON in ChordCharts sheet
4. Charts loaded and displayed in 4-per-row grid during practice
5. SVGuitar renders saved charts for visual display

### Usage
- Available in practice mode for each song/item
- Toggle "Add New Chord" to open interactive editor
- Click on fretboard to place finger positions
- Enter chord name and save to persist in database
- Saved charts appear in collapsible "Chord Charts" section

## Development Tools

### Server Log Access
For debugging during development, you can access server logs via:
- **Terminal output**: The terminal running `./gpr.sh` shows Flask server logs in real-time
- **Log files**: Production logs stored in `logs/gpr.log` with rotation (50MB max, 2 files)
- **Console logging**: Browser console shows frontend errors and debug messages

**Log Rotation**: Logs automatically rotate at 50MB with 2 backup files (100MB total max)

## Performance Patterns & Optimizations

### Google Sheets API Rate Limiting (60 requests/minute/user)
**Critical**: Always use batch operations to minimize API calls, especially for chord chart operations.

#### Batch Operations Pattern:
- **Bad**: Individual `add_chord_chart()` calls for each chord (20+ API calls)
- **Good**: `batch_add_chord_charts()` with all chords at once (3 total API calls)
- **Implementation**: Use `batch_add_chord_charts(item_id, chord_charts_data)` in `sheets.py`

#### CommonChords Performance:
- **Fixed Range**: `get_common_chords_efficiently()` uses fixed range `A2:F12710` (12,709 chord records)
- **No Dynamic Detection**: Avoids extra API calls to determine data range
- **Pre-loading**: Load CommonChords once at start of autocreate, reuse for all chord lookups

### Frontend State Management

#### UI Refresh After Backend Operations:
**Critical Pattern**: Don't rely on conditional loaders like `loadChordChartsForItem()` which skip if data already exists.

**Correct Pattern for Immediate UI Updates:**
```javascript
// Force refresh with fresh API call
const response = await fetch(`/api/items/${itemId}/chord-charts`);
const charts = await response.json();

// Direct state updates
setChordCharts(prev => ({
  ...prev,
  [itemId]: charts
}));

setChordSections(prev => ({
  ...prev,
  [itemId]: buildSectionsFromCharts(charts)
}));
```

**Applied in:**
- Autocreate completion handler
- Delete operations
- Manual chord creation

### Autocreate System Optimizations

#### Rate Limiting Prevention:
1. **Pre-load CommonChords**: Single API call at start
2. **Batch Creation**: All chords created in one operation
3. **Smart Blocking**: Prevent autocreate when charts already exist

#### User Experience:
- Clear warning when trying autocreate on items with existing charts
- Progress messages with rotating content during processing
- Immediate UI refresh after completion

#### Visual Analysis Debugging Process (NEW)
**CRITICAL: Chord Diagram Reading Rules for Autocreate Feature**
- **Chord diagram anatomy**: Dots are positioned BETWEEN fret lines, not ON fret lines
- **Fret terminology**: "Fret 1" means the space between the top horizontal line (nut) and the 2nd horizontal line from the top
- **IGNORE position markers completely**: Position markers like "5fr", "3fr", etc. are completely irrelevant when recreating chord charts. They are just position indicators for guitarists and must be ignored during visual analysis
- **Fret counting**: ALWAYS count from the top - fret 1 = space between top line and 2nd line, fret 2 = space between 2nd and 3rd lines, etc.
- **Reference-first approach**: When reference files exist, recreate exactly as shown - ignore complex tablature integration, use tablature only for repeat counts
- **Exact recreation principle**: Preserve exact order (left-to-right, top-to-bottom), line breaks, and chord names from reference file
- **CRITICAL PROMPT FIX**: Visual analysis prompt must NOT assume alternate tuning - let Claude determine tuning naturally
- **Anti-knowledge instruction**: Explicitly tell Claude "NEVER use your knowledge of chord shapes - only extract what you visually observe"

#### Hybrid Model Approach (NEW)
**Smart Model Selection** for optimal cost/performance balance:
- **Opus 4.1**: Used automatically when reference chord diagrams are present (superior visual analysis)
- **Sonnet 4**: Used for tablature-only processing (cost-effective for text analysis)
- **Detection Logic**: System checks file categories and selects appropriate model
- **Rate Limit Management**: Helps us stay within Opus usage limits while getting best results

#### Visual Analysis Debugging Process (NEW)
**Common Issues with Reference Chord Diagrams:**
- **Conflicting prompt instructions** can confuse visual analysis models
- **Prompt structure matters**: Visual analysis instructions must come first, before tablature guidance
- **Chord name matching**: Remove suffixes like "(capoOn2)" for proper matching between files
- **Debug output**: Always require detailed visual descriptions in API responses
- **Validation steps**: Force models to re-examine and verify fret counting

**Key Debugging Steps:**
1. Check logs for extracted patterns vs expected patterns
2. Verify chord name matching logic is working
3. Ensure song structure is preserved from tablature
4. Validate visual analysis descriptions make sense

## Critical PostgreSQL Migration Bug (SOLVED)

### ItemID Mapping Issue in Routine Items
**Symptom**: Chord charts showing up on wrong songs despite correct titles (e.g., "Should I Stay or Should I Go" title but "My City Was Gone" chords)

**Root Cause**: The `_routine_item_to_sheets_format()` method in `app/repositories/routines.py` was returning database primary keys instead of Google Sheets ItemIDs in Column B.

**The Problem**: 
- Database ID 106 → ItemID "107" → "Should I Stay or Should I Go"
- But routine was returning Column B="106" instead of Column B="107"
- Frontend requests chord charts for ItemID "106" → gets "My City Was Gone" chords

**The Fix**: Modified `_routine_item_to_sheets_format()` to query the Items table and return the actual `item.item_id` string instead of the `routine_item.item_id` integer:

```python
# Get the actual ItemID string from the Items table
item = self.db.query(Item).filter(Item.id == routine_item.item_id).first()
item_id_str = item.item_id if item and item.item_id else str(routine_item.item_id)

return {
    'A': str(routine_item.id),  # RoutineItem ID
    'B': item_id_str,          # Google Sheets ItemID (e.g., "107", not 106)
    'C': str(routine_item.order),  # Order
    'D': 'TRUE' if routine_item.completed else 'FALSE'  # Completed
}
```

**Critical**: Always use Google Sheets ItemIDs for frontend communication, never database primary keys.

## PostgreSQL Migration Debugging Patterns

### API Endpoint Completeness Check
When implementing API endpoints, always verify BOTH directions of batch operations exist:
- **`/api/chord-charts/batch`** (POST) - GET chord charts for multiple items
- **`/api/chord-charts/batch-delete`** (POST) - DELETE multiple chord charts by IDs

**Common Issue**: Frontend may call both endpoints for different purposes. Check sheets version for complete endpoint list.

### Complex Debugging with Task Tool
For multi-system issues (missing endpoints, data format problems, etc.), use Task tool with general-purpose agent:
- Provide specific file paths and function names
- Include "don't re-engineer" reminder and sheets reference link
- Request detailed technical analysis with fix recommendations
- Very effective for systematic debugging

### Migration Progress Reference
See `API_MISMATCH_CHECKLIST.md` in project root for comprehensive comparison between PostgreSQL and sheets versions:
- Complete endpoint inventory
- Priority-based action items  
- Current implementation status
- Should be updated as features are implemented

## PostgreSQL Migration Troubleshooting Patterns

### Common ID Mismatch Issues
**Root Cause**: PostgreSQL migration preserved Google Sheets structure where:
- **Column A**: Database primary key (auto-incrementing integer)
- **Column B**: Google Sheets ItemID (string like "107")

**Symptoms**:
- Wrong item names in dialogs
- Filtering/sorting broken
- API returns wrong data despite correct database content

**Fix Pattern**: Always use ItemIDs (Column B) for frontend communication, never database primary keys (Column A).

### Common Repository/Model Attribute Issues
**ChordChart Model**: Uses `order_col` (not `order`) and `chord_id` (not `id`) to match Google Sheets columns
**Fix Pattern**: Check model definitions in `app/models.py` for exact attribute names

### File Upload Patterns
**Frontend sends**: `file0`, `file1`, etc. (not `'files'`)
**Backend fix**: Use `request.files.values()` to capture all files regardless of key names

Anon, we rock n roll 🙌🤘🎸...