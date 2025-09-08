# Guitar Practice Routine Assistant (PostgreSQL)

A web application that helps guitar players manage practice routines, create and organize chord charts, and track practice progress using PostgreSQL as the database backend.

**Note**: This is the PostgreSQL port of the original [Google Sheets-based version](https://github.com/slshults/guitar-practice-routine-app_sheets). The application supports both PostgreSQL and Google Sheets backends through a unified DataLayer abstraction.

## Features

### Practice Session Management
- **Timer-based practice sessions** with customizable durations for each item
- **Progress tracking** - mark items as complete during practice
- **Organized routines** with drag-and-drop reordering
- **Visual progress indicators** showing completion status

### Chord Chart System
- **Interactive chord chart editor** with click-to-place finger positions
- **Section organization** - organize chords by song sections (Verse, Chorus, etc.)
- **SVGuitar integration** for professional chord diagram rendering
- **Autocreate feature** - upload PDFs or images to automatically generate chord charts using Claude AI
- **Shared chord charts** - charts can belong to multiple songs via comma-separated ItemIDs
- **CommonChords database** with 12,700+ pre-defined chord patterns

### Data Management
- **Dual-mode architecture** - switch between PostgreSQL and Google Sheets backends
- **Complete CRUD operations** for routines, items, and chord charts
- **Exact data preservation** from Google Sheets migration
- **Section metadata** stored within chord data for organization
- **Order preservation** maintaining physical insertion order from original sheets

### AI Integration
- **Autocreate chord charts** from uploaded files (PDFs, images)
- **Three processing paths**: Visual chord diagrams, chord names above lyrics, and tablature notation
- **Hybrid model approach** - Opus 4.1 for visual analysis, Sonnet 4 for text processing
- **Cost-efficient processing** with smart model selection

## Getting Started

### Prerequisites

#### Option 1: PostgreSQL Setup (Recommended)
- **PostgreSQL 12+** installed and running
- **Python 3.8+**
- **Node.js 16+** and npm

Install PostgreSQL:
- **Official docs**: https://www.postgresql.org/docs/current/installation.html
- **Windows**: https://www.postgresql.org/download/windows/
- **macOS**: https://www.postgresql.org/download/macosx/
- **Linux**: https://www.postgresql.org/download/linux/

#### Option 2: Google Sheets Fallback
- **Google Cloud Project** with Sheets API enabled
- **OAuth2 credentials** for Google Sheets access
- **Python 3.8+**
- **Node.js 16+** and npm

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/slshults/guitar-practice-routine-app_postgresql.git
   cd guitar-practice-routine-app_postgresql
   ```

2. **Set up Python environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   
   # Install Python dependencies
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**
   ```bash
   npm install
   ```

4. **Database Setup**

   **Option A: PostgreSQL (Recommended)**
   ```bash
   # Create database and user
   sudo -u postgres psql
   CREATE DATABASE guitar_practice;
   CREATE USER guitar_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE guitar_practice TO guitar_user;
   \q
   
   # Set environment variables
   cp .env.template .env
   # Edit .env and set:
   DATABASE_URL=postgresql://guitar_user:your_password@localhost/guitar_practice
   MIGRATION_MODE=postgres
   ```

   **Option B: Google Sheets Fallback**
   ```bash
   cp .env.template .env
   # Edit .env and set:
   MIGRATION_MODE=sheets
   # Add your Google OAuth credentials
   ```

5. **Initialize Database** (PostgreSQL only)
   ```bash
   # Create tables
   python -c "from app.database import create_tables; create_tables()"
   
   # Optional: Migrate existing Google Sheets data
   python migrate_items.py
   python migrate_routines.py  
   python migrate_chord_charts.py
   ```

6. **Configure Environment Variables**
   ```bash
   # Optional: For autocreate chord charts feature
   ANTHROPIC_API_KEY=your_anthropic_api_key
   
   # Optional: For PostHog analytics
   POSTHOG_API_KEY=your_posthog_key
   ```

### Running the Application

```bash
# Start both Flask server and Vite watcher
./gpr.sh

# Or run components separately:
# Backend only:
python run.py
# Frontend build watcher:
npm run watch
```

Open your browser to `http://localhost:5000`

## PostgreSQL Database Schema

### Core Tables

```sql
-- Practice items (exercises, songs, techniques)
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    item_id VARCHAR(50),          -- Google Sheets ItemID for compatibility
    title VARCHAR(255) NOT NULL,
    notes TEXT,
    duration VARCHAR(50),
    description TEXT,
    order_col INTEGER DEFAULT 0,
    tuning VARCHAR(50),
    songbook VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Practice routines metadata
CREATE TABLE routines (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    order_col INTEGER DEFAULT 0
);

-- Junction table for routine-item relationships  
CREATE TABLE routine_items (
    id INTEGER PRIMARY KEY,
    routine_id INTEGER REFERENCES routines(id),
    item_id INTEGER REFERENCES items(id),
    order_col INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chord diagrams with section metadata
CREATE TABLE chord_charts (
    chord_id INTEGER PRIMARY KEY,
    item_id TEXT NOT NULL,        -- Supports comma-separated ItemIDs
    title VARCHAR(255) NOT NULL,  -- Chord name (e.g., "D", "G", "Am7")
    chord_data JSON NOT NULL,     -- SVGuitar data + section metadata  
    created_at TIMESTAMP DEFAULT NOW(),
    order_col INTEGER DEFAULT 0
);

-- Tracks currently active routine
CREATE TABLE active_routine (
    id INTEGER PRIMARY KEY,
    routine_id INTEGER REFERENCES routines(id),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Example Data

#### Sample Routine
```sql
INSERT INTO routines (id, name) VALUES 
(1, 'Daily Practice Routine');

INSERT INTO items (id, item_id, title, duration, tuning) VALUES
(1, '107', 'Practice Should I Stay or Should I Go (relearning)', '5', 'EADGBE');

INSERT INTO routine_items (routine_id, item_id, order_col) VALUES
(1, 1, 0);
```

#### Sample Chord Chart
```sql
INSERT INTO chord_charts (chord_id, item_id, title, chord_data) VALUES
(292, '107', 'D', '{
  "fingers": [[3, 2, null], [2, 3, null], [1, 2, null]],
  "barres": [],
  "tuning": "EADGBE", 
  "capo": 0,
  "startingFret": 1,
  "numFrets": 5,
  "numStrings": 6,
  "openStrings": [],
  "mutedStrings": [6, 5],
  "sectionId": "section-1754960333032",
  "sectionLabel": "Intro", 
  "sectionRepeatCount": "",
  "hasLineBreakAfter": false
}');
```

## Architecture

### Backend (Flask + PostgreSQL)
- **Flask application** with RESTful API endpoints
- **SQLAlchemy ORM** with PostgreSQL database  
- **DataLayer abstraction** for dual-mode support (postgres/sheets)
- **Service layer** for business logic (ItemService, ChordChartService, etc.)
- **Repository layer** for data access with Google Sheets format compatibility

### Frontend (React + Vite)
- **React 18.2.0** with functional components and hooks
- **Vite 4.x** for fast development and building
- **Tailwind CSS** for styling
- **SVGuitar integration** for chord diagram rendering
- **Path aliases** (`@components`, `@hooks`, `@ui`, etc.)

### Key Components
- `PracticePage.jsx` - Main practice session interface
- `ChordChartEditor.jsx` - Interactive chord diagram editor  
- `ChordGrid.jsx` - Chord chart display component
- `DataLayer` - Unified interface for postgres/sheets backends

## API Endpoints

### Items
- `GET /api/items` - List all practice items
- `POST /api/items` - Create new item
- `GET /api/items/<id>` - Get item details
- `PUT /api/items/<id>` - Update item
- `DELETE /api/items/<id>` - Delete item

### Routines  
- `GET /api/routines` - List all routines
- `POST /api/routines` - Create new routine
- `GET /api/routines/<id>` - Get routine with items
- `PUT /api/routines/<id>` - Update routine
- `DELETE /api/routines/<id>` - Delete routine

### Chord Charts
- `GET /api/items/<id>/chord-charts` - Get chord charts for item
- `POST /api/items/<id>/chord-charts` - Create chord chart
- `PUT /api/chord-charts/<id>` - Update chord chart
- `DELETE /api/chord-charts/<id>` - Delete chord chart
- `POST /api/autocreate-chord-charts` - AI-powered chord chart creation

## Usage Tips

### Practice Sessions
1. **Select or create a routine** from the main page
2. **Set it as active** to begin practice
3. **Use timers** to track practice duration for each item
4. **Mark items complete** as you finish them
5. **View chord charts** by expanding the chord section

### Chord Chart Management
1. **Toggle "Add New Chord"** to open the interactive editor
2. **Click on fret positions** to place fingers
3. **Organize chords by sections** (Verse, Chorus, etc.)
4. **Use autocreate** to generate charts from PDFs or images
5. **Copy chord charts** between songs to avoid duplication

### Data Migration
- **From Google Sheets**: Use provided migration scripts
- **Preserve order**: Physical insertion order maintained from sheets
- **Comma-separated ItemIDs**: Shared chord charts supported
- **Section metadata**: Preserved within chord data JSON

## Development

### Project Structure
```
app/
├── static/js/components/     # React components
├── static/js/hooks/         # Custom React hooks
├── static/js/utils/         # Utility functions
├── static/css/              # Compiled CSS
├── templates/               # Jinja2 templates
├── models.py               # SQLAlchemy models
├── data_layer.py           # Unified data abstraction
├── services/               # Business logic layer
├── repositories/           # Data access layer
└── routes.py               # Flask API endpoints

migrations/                  # Database migration scripts
├── migrate_items.py
├── migrate_routines.py
└── migrate_chord_charts.py
```

### Common Commands
```bash
# Development server with watchers
./gpr.sh

# Build production assets
npm run build

# Database migrations
python migrate_items.py --clear --force
python migrate_routines.py --clear --force  
python migrate_chord_charts.py --clear --force

# Linting and formatting
npm run lint
python -m flake8 app/
```

## Troubleshooting

### Database Issues
- **Connection errors**: Check `DATABASE_URL` in `.env`
- **Migration failures**: Ensure database exists and user has permissions
- **Data inconsistencies**: Verify ItemID mappings between tables

### Frontend Issues  
- **Chord charts not loading**: Check browser console for API errors
- **SVGuitar rendering problems**: Verify chord data format in database
- **Section organization**: Ensure section metadata is preserved in chord_data JSON

### Performance
- **Slow chord chart loading**: Check database indexes on `item_id` and `order_col`
- **API timeouts**: Consider pagination for large datasets
- **Frontend bundling**: Use `npm run build` for production optimization

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality  
5. Ensure all tests pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

### Open Source Projects
This project wouldn't be possible without these amazing open source libraries:

**Backend:**
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM and database toolkit
- [PostgreSQL](https://www.postgresql.org/) - Database system

**Frontend:**
- [React](https://reactjs.org/) - UI library
- [Vite](https://vitejs.dev/) - Build tool and development server  
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS framework
- [SVGuitar](https://github.com/omnibrain/svguitar) by [@omnibrain](https://github.com/omnibrain) - Guitar chord diagram rendering

**Guitar Data:**
- [SVGuitar-ChordCollection](https://github.com/TormodKv/SVGuitar-ChordCollection) by [@TormodKv](https://github.com/TormodKv) - Comprehensive chord database

**AI Integration:**
- [Anthropic Claude](https://www.anthropic.com/) - AI-powered chord chart analysis and generation

### Development Tools
- [Claude Code](https://claude.ai/code) - AI pair programming assistant
- [PostHog](https://posthog.com/) - Product analytics and feature flags

Special thanks to the entire open source community for building the tools and libraries that make projects like this possible! 🎸

---

**Happy practicing!** 🎵

*If you find this helpful, please consider starring the repository and sharing it with other guitar players.*# guitar-practice-routine-app_postgresql
