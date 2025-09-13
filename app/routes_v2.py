"""
Updated routes using the data layer abstraction.
Drop-in replacement for existing routes.py during migration.
"""
from flask import render_template, request, jsonify, redirect, session, url_for
from app import app
from app.data_layer import data_layer
from app.database import DatabaseTransaction
from sqlalchemy import text
import logging
import os
import subprocess
import base64
import anthropic

# Main route
@app.route('/')
def index():
    posthog_key = os.getenv('POSTHOG_API_KEY', '')
    return render_template('index.html.jinja', posthog_key=posthog_key)

# Items API - Updated to use data layer
@app.route('/api/items', methods=['GET', 'POST'])
def items():
    """Handle GET (list) and POST (create) for items"""
    if request.method == 'GET':
        return jsonify(data_layer.get_all_items())
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        new_item = request.json
        result = data_layer.add_item(new_item)
        return jsonify(result)

@app.route('/api/items/<item_id>', methods=['GET', 'PUT', 'DELETE'])
def item(item_id):
    """Handle GET (fetch), PUT (update) and DELETE for individual items"""
    try:
        item_id = int(float(item_id))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid item ID"}), 400
        
    if request.method == 'GET':
        # For single item GET, we can get from the full list for now
        items = data_layer.get_all_items()
        item = next((i for i in items if int(float(i['A'])) == item_id), None)
        return jsonify(item) if item else ('', 404)
        
    elif request.method == 'PUT':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        updated_item = data_layer.update_item(item_id, request.json)
        return jsonify(updated_item) if updated_item else ('', 404)
        
    elif request.method == 'DELETE':
        success = data_layer.delete_item(item_id)
        return jsonify({"success": success})

# Item ordering
@app.route('/api/items/order', methods=['PUT'])
def update_items_order():
    """Update item ordering (drag-and-drop support)"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    success = data_layer.update_items_order(request.json)
    return jsonify({"success": success})

# Item notes
@app.route('/api/items/<int:item_id>/notes', methods=['GET', 'POST'])
def item_notes(item_id):
    """Get or save notes for a specific item"""
    if request.method == 'GET':
        # Retrieve notes for the item
        result = data_layer.get_item_notes(item_id)
        if 'error' in result:
            return jsonify(result), 404
        return jsonify(result)
    
    elif request.method == 'POST':
        # Save notes for the item
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        notes = data.get('notes', '')
        
        app.logger.debug(f"DEBUG:save_notes:Received note text: {notes}")
        
        result = data_layer.save_item_notes(item_id, notes)
        if 'error' in result:
            return jsonify(result), 500
        
        return jsonify(result)

# Chord Charts API - Updated to use data layer  
@app.route('/api/items/<int:item_id>/chord-charts', methods=['GET', 'POST'])
def item_chord_charts(item_id):
    """Handle chord charts for an item"""
    if request.method == 'GET':
        chord_charts = data_layer.get_chord_charts_for_item(item_id)
        return jsonify(chord_charts)
        
    elif request.method == 'POST':
        try:
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
                
            chord_data = request.json
            app.logger.info(f"Creating chord chart for item {item_id}")
            result = data_layer.add_chord_chart(item_id, chord_data)
            app.logger.info(f"Successfully created chord chart")
            return jsonify(result)
        except Exception as e:
            app.logger.error(f"Error creating chord chart: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to save chord chart: {str(e)}"}), 500

@app.route('/api/chord-charts/<int:chart_id>', methods=['PUT', 'DELETE'])
def chord_chart(chart_id):
    """Handle individual chord chart operations"""
    if request.method == 'PUT':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        updated_chart = data_layer.update_chord_chart(chart_id, request.json)
        return jsonify(updated_chart) if updated_chart else ('', 404)
        
    elif request.method == 'DELETE':
        success = data_layer.delete_chord_chart(chart_id)
        return jsonify({"success": success})

# Chord chart ordering
@app.route('/api/items/<int:item_id>/chord-charts/order', methods=['PUT'])
def update_chord_charts_order(item_id):
    """Update chord chart ordering for an item"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    success = data_layer.update_chord_charts_order(item_id, request.json)
    return jsonify({"success": success})

# Batch chord chart operations
@app.route('/api/items/<int:item_id>/chord-charts/batch', methods=['POST'])
def batch_add_chord_charts(item_id):
    """Create multiple chord charts at once"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    chord_charts_data = request.json
    if not isinstance(chord_charts_data, list):
        return jsonify({"error": "Request must be a list of chord charts"}), 400
    
    results = data_layer.batch_add_chord_charts(item_id, chord_charts_data)
    return jsonify(results)

@app.route('/api/chord-charts/batch-delete', methods=['POST'])
def batch_delete_chord_charts():
    """Delete multiple chord charts by IDs in a single transaction."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        chord_ids = data.get('chord_ids', [])
        
        if not chord_ids:
            return jsonify({"error": "No chord IDs provided"}), 400
        
        if not isinstance(chord_ids, list):
            return jsonify({"error": "chord_ids must be an array"}), 400
        
        app.logger.info(f"Batch deleting chord charts: {chord_ids}")
        
        result = data_layer.batch_delete_chord_charts(chord_ids)
        
        if result['success']:
            app.logger.info(f"Successfully batch deleted {result['deleted_count']} chord charts")
            return jsonify(result)
        else:
            app.logger.error(f"Batch delete failed: {result.get('error', 'Unknown error')}")
            return jsonify(result), 500
            
    except Exception as e:
        app.logger.error(f"Error in batch delete chord charts: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to batch delete chord charts: {str(e)}"}), 500

@app.route('/api/chord-charts/batch', methods=['POST'])
def batch_get_chord_charts():
    """Get chord charts for multiple items in a single request."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        item_ids = data.get('item_ids', [])
        
        if not item_ids:
            return jsonify({"error": "No item IDs provided"}), 400
        
        if not isinstance(item_ids, list):
            return jsonify({"error": "item_ids must be an array"}), 400
        
        app.logger.info(f"Batch getting chord charts for items: {item_ids}")
        
        result = data_layer.batch_get_chord_charts(item_ids)
        
        app.logger.info(f"Successfully retrieved chord charts for {len(result)} items")
        return jsonify(result)
            
    except Exception as e:
        app.logger.error(f"Error in batch get chord charts: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to batch get chord charts: {str(e)}"}), 500

# AI chord chart creation
@app.route('/api/autocreate-chord-charts', methods=['POST'])
def autocreate_chord_charts():
    """Autocreate chord charts from uploaded PDF/image files using Claude"""
    try:
        app.logger.debug("Starting autocreate chord charts process")
        
        # Check if files were uploaded (frontend sends as file0, file1, etc.)
        # Use request.files.values() to get all files regardless of key names
        files_list = list(request.files.values())
        if not files_list:
            return jsonify({'error': 'No files uploaded'}), 400
            
        item_id = request.form.get('itemId')
        if not item_id:
            return jsonify({'error': 'No itemId provided'}), 400
            
        app.logger.debug(f"Processing files for item ID: {item_id}")
        
        # Process uploaded files - simplified single collection
        uploaded_files = []
        
        def process_file(file):
            """Helper function to process a single file"""
            if file.filename == '':
                return None
                
            # Validate file type and size
            from werkzeug.utils import secure_filename
            filename = secure_filename(file.filename)
            if not filename:
                return None
                
            # Check file size (10MB limit)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                return {'error': f'File {filename} is too large (max 10MB)'}
                
            # Read file content
            file_data = file.read()
            
            # Determine file type
            file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
            
            if file_ext == 'pdf':
                return {
                    'name': filename,
                    'type': 'pdf',
                    'data': base64.b64encode(file_data).decode('utf-8')
                }
            elif file_ext in ['png', 'jpg', 'jpeg']:
                return {
                    'name': filename,
                    'type': 'image',
                    'data': base64.b64encode(file_data).decode('utf-8'),
                    'media_type': f'image/{file_ext if file_ext != "jpg" else "jpeg"}'
                }
            else:
                return {'error': f'Unsupported file type: {file_ext}'}
        
        # Process single uploaded file only (simplified approach)
        if len(files_list) > 1:
            return jsonify({'error': 'Please upload only one file at a time for autocreate'}), 400
        
        if len(files_list) == 0:
            return jsonify({'error': 'No file uploaded'}), 400
            
        # Process the single file
        file = files_list[0]
        result = process_file(file)
        if result:
            if 'error' in result:
                return jsonify(result), 400
            uploaded_files.append(result)
        
        app.logger.info(f"Processed 1 file for analysis: {result.get('name', 'unknown')}")
                
        if not uploaded_files:
            return jsonify({'error': 'No valid file found'}), 400
            
        # Check if user provided a choice for mixed content
        user_choice = request.form.get('userChoice')
        if user_choice:
            app.logger.info(f"[AUTOCREATE] User chose to process files as: {user_choice}")
            app.logger.info(f"[AUTOCREATE] Processing {len(uploaded_files)} files with user choice override")
            # Override file type detection with user choice
            for file_data in uploaded_files:
                file_data['forced_type'] = user_choice
        else:
            app.logger.info(f"[AUTOCREATE] No user choice provided, will use automatic detection")
            
        # Get Anthropic API key from environment
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return jsonify({'error': 'Anthropic API key not configured'}), 500
            
        # Initialize Anthropic client
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        app.logger.info(f"[AUTOCREATE] Anthropic client initialized successfully")
        
        # Prepare the Claude analysis request
        app.logger.info(f"[AUTOCREATE] Starting Claude analysis for item {item_id}")
        app.logger.debug("Sending files to Claude for analysis")
        
        # Process with simplified autocreate logic
        analysis_result = simple_analyze_files(client, uploaded_files, item_id)
        app.logger.info(f"[AUTOCREATE] Claude analysis completed, result type: {type(analysis_result)}")
        
        app.logger.debug("Claude analysis complete, creating chord charts")
        
        return jsonify(analysis_result)
        
    except Exception as e:
        app.logger.error(f"Error in autocreate chord charts: {str(e)}")
        return jsonify({'error': str(e)}), 500

# System status and migration utilities
@app.route('/api/system/status', methods=['GET'])
def system_status():
    """Get current system status and data layer information"""
    return jsonify({
        "data_layer": data_layer.get_mode_info(),
        "stats": data_layer.get_stats()
    })

@app.route('/api/migration/switch/<mode>', methods=['POST'])
def switch_mode(mode):
    """Switch data layer mode (for testing)"""
    if mode not in ['sheets', 'postgres']:
        return jsonify({"error": "Invalid mode. Use 'sheets' or 'postgres'"}), 400
    
    # This would require restarting the app or dynamic configuration
    # For now, just return current status
    return jsonify({
        "message": f"To switch to {mode} mode, set MIGRATION_MODE={mode} in .env and restart",
        "current_mode": data_layer.mode
    })

# Health check
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        stats = data_layer.get_stats()
        return jsonify({
            "status": "healthy",
            "data_source": stats.get('data_source', 'unknown'),
            "total_items": stats.get('total_items', 0)
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

# Authentication routes
@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    if data_layer.mode == 'postgres':
        # For PostgreSQL mode, no authentication needed (single user app)
        return jsonify({
            "authenticated": True, 
            "hasSpreadsheetAccess": True,  # PostgreSQL always has "database access"
            "user": "local_user", 
            "mode": "postgresql"
        })
    else:
        # For Sheets mode, check if we have valid credentials
        try:
            from app import sheets
            creds, _ = sheets.get_credentials()
            if not creds or not creds.valid:
                return jsonify({"authenticated": False, "hasSpreadsheetAccess": False})
            
            # Test spreadsheet access
            test_result = sheets.test_sheets_connection()
            return jsonify({
                "authenticated": True,
                "hasSpreadsheetAccess": test_result.get("success", False),
                "user": "sheets_user", 
                "mode": "google_sheets"
            })
        except Exception:
            return jsonify({
                "authenticated": False, 
                "hasSpreadsheetAccess": False,
                "auth_url": "/authorize", 
                "mode": "google_sheets"
            })

@app.route('/authorize')
def authorize():
    """Initiate OAuth flow for Google Sheets (fallback for Sheets mode)"""
    if data_layer.mode == 'postgres':
        # No authentication needed for PostgreSQL mode
        return redirect('/')
    else:
        # Import OAuth logic from original routes
        try:
            from app.sheets import get_credentials
            from google_auth_oauthlib.flow import Flow
            
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
                        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [request.url_root + 'oauth2callback']
                    }
                },
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            flow.redirect_uri = request.url_root + 'oauth2callback'
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            session['state'] = state
            return redirect(authorization_url)
        except Exception as e:
            return f"OAuth setup error: {str(e)}", 500

@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth callback for Google Sheets"""
    if data_layer.mode == 'postgres':
        # No authentication needed for PostgreSQL mode
        return redirect('/')
    else:
        try:
            from google_auth_oauthlib.flow import Flow
            
            state = session.get('state')
            if not state:
                return "Invalid state parameter", 400
            
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
                        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [request.url_root + 'oauth2callback']
                    }
                },
                scopes=['https://www.googleapis.com/auth/spreadsheets'],
                state=state
            )
            flow.redirect_uri = request.url_root + 'oauth2callback'
            
            # Get tokens
            flow.fetch_token(authorization_response=request.url)
            
            # Save credentials to file
            credentials = flow.credentials
            with open('token.json', 'w') as token_file:
                token_file.write(credentials.to_json())
            
            return redirect('/')
        except Exception as e:
            return f"OAuth callback error: {str(e)}", 500

@app.route('/logout')
def logout():
    """Logout endpoint"""
    if data_layer.mode == 'postgres':
        # For PostgreSQL mode, just redirect to home
        return redirect('/')
    else:
        # For Sheets mode, remove token file
        try:
            import os
            if os.path.exists('token.json'):
                os.remove('token.json')
        except Exception:
            pass
        return redirect('/authorize')

# Debug and logging routes
@app.route('/api/debug/log', methods=['POST'])
def debug_log():
    """Handle frontend debug logging"""
    if request.is_json:
        message = request.json.get('message', 'No message')
        level = request.json.get('level', 'info')
        app.logger.info(f"[FRONTEND {level.upper()}] {message}")
    return jsonify({"success": True})

# Lightweight item endpoint
@app.route('/api/items/lightweight', methods=['GET'])
def items_lightweight():
    """Get lightweight item data"""
    items = data_layer.get_all_items()
    # Return just ID and title for performance
    lightweight = [{"A": item["A"], "C": item["C"]} for item in items]
    return jsonify(lightweight)

# Routines API - Now using data layer
@app.route('/api/routines', methods=['GET', 'POST'])
def routines():
    """Handle GET (list) and POST (create) for routines"""
    if request.method == 'GET':
        return jsonify(data_layer.get_all_routines())
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        new_routine = request.json
        result = data_layer.create_routine(new_routine)
        return jsonify(result)

@app.route('/api/routines/<int:routine_id>', methods=['GET', 'PUT', 'DELETE'])
def routine(routine_id):
    """Handle GET (fetch), PUT (update) and DELETE for individual routines"""
    if request.method == 'GET':
        # Get routine with items
        routine_data = data_layer.get_routine_with_items(routine_id)
        return jsonify(routine_data) if routine_data else ('', 404)
        
    elif request.method == 'PUT':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        updated_routine = data_layer.update_routine(routine_id, request.json)
        return jsonify(updated_routine) if updated_routine else ('', 404)
        
    elif request.method == 'DELETE':
        success = data_layer.delete_routine(routine_id)
        return jsonify({"success": success})

@app.route('/api/routines/<int:routine_id>/details', methods=['GET'])
def get_routine_with_details(routine_id):
    """Get a routine with all item details and metadata."""
    try:
        # Use existing DataLayer method that already provides detailed routine info
        routine_data = data_layer.get_routine_with_items(routine_id)
        if not routine_data:
            return jsonify({"error": "Routine not found"}), 404
        
        return jsonify(routine_data)
    except Exception as e:
        app.logger.error(f"Error getting routine with details: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/routines/<int:routine_id>/items', methods=['GET', 'POST'])
def routine_items(routine_id):
    """Handle routine items"""
    if request.method == 'GET':
        items = data_layer.get_routine_items(routine_id)
        return jsonify(items)
        
    elif request.method == 'POST':
        try:
            if not request.is_json:
                return jsonify({"error": "Request must be JSON"}), 400
                
            item_data = request.json
            # Accept both camelCase (itemId) and snake_case (item_id) for compatibility
            item_id = item_data.get('itemId') or item_data.get('item_id')
            order = item_data.get('order')
            
            if not item_id:
                return jsonify({"error": "itemId is required"}), 400
                
            app.logger.info(f"Adding item {item_id} to routine {routine_id}")
            result = data_layer.add_item_to_routine(routine_id, int(item_id), order)
            app.logger.info(f"Successfully added item to routine")
            return jsonify(result)
        except Exception as e:
            app.logger.error(f"Error adding item to routine: {str(e)}", exc_info=True)
            return jsonify({"error": f"Failed to add item to routine: {str(e)}"}), 500

@app.route('/api/routines/<int:routine_id>/items/<int:item_id>', methods=['DELETE'])
def routine_item(routine_id, item_id):
    """Remove an item from a routine"""
    success = data_layer.remove_item_from_routine(routine_id, item_id)
    return jsonify({"success": success})

@app.route('/api/routines/<int:routine_id>/items/order', methods=['PUT'])
def update_routine_items_order(routine_id):
    """Update routine item ordering"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    success = data_layer.update_routine_items_order(routine_id, request.json)
    return jsonify({"success": success})

@app.route('/api/routines/<int:routine_id>/items/<int:item_id>/complete', methods=['PUT'])
def mark_routine_item_complete(routine_id, item_id):
    """Mark a routine item as completed or not"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    completed = request.json.get('completed', True)
    success = data_layer.mark_item_complete(routine_id, item_id, completed)
    return jsonify({"success": success})

@app.route('/api/routines/<int:routine_id>/reset', methods=['POST'])
def reset_routine_progress(routine_id):
    """Reset all items in a routine to not completed"""
    success = data_layer.reset_routine_progress(routine_id)
    return jsonify({"success": success})

# Active routine management
@app.route('/api/practice/active-routine', methods=['GET', 'POST', 'DELETE'])
def active_routine():
    """Handle active routine operations"""
    if request.method == 'GET':
        active = data_layer.get_active_routine()
        return jsonify(active) if active else jsonify(None)
        
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        routine_id = request.json.get('routine_id')
        if not routine_id:
            return jsonify({"error": "routine_id is required"}), 400
            
        success = data_layer.set_active_routine(int(routine_id))
        return jsonify({"success": success})
        
    elif request.method == 'DELETE':
        success = data_layer.clear_active_routine()
        return jsonify({"success": success})

@app.route('/api/practice/active-routine/lightweight', methods=['GET'])
def get_active_routine_lightweight():
    """Get lightweight active routine data"""
    active = data_layer.get_active_routine()
    if not active:
        return jsonify({"active_id": None, "items": []})
    
    # Get routine with items
    routine_id = int(active.get("A"))
    routine_with_items = data_layer.get_routine_with_items(routine_id)
    
    if not routine_with_items:
        return jsonify({"active_id": None, "items": []})
    
    # Format the response to match what the frontend expects
    items_with_minimal_details = []
    for item in routine_with_items.get("items", []):
        # item is already in the correct format with A, B, C, D keys from _routine_item_to_sheets_format
        # and itemDetails from the service
        items_with_minimal_details.append({
            "routineEntry": {
                "A": item.get("A"),  # Routine item ID
                "B": item.get("B"),  # Item ID
                "C": item.get("C"),  # Order
                "D": item.get("D")   # Completed status (already "TRUE"/"FALSE")
            },
            "itemMinimal": {
                "A": item.get("itemDetails", {}).get("A", ""),  # Item ID
                "C": item.get("itemDetails", {}).get("C", "")   # Item title
            }
        })
    
    return jsonify({
        "active_id": str(routine_id),
        "name": routine_with_items.get("B", ""),  # Column B contains routine name
        "items": items_with_minimal_details
    })

@app.route('/api/routines/<int:routine_id>/active', methods=['PUT'])
def set_routine_active_status(routine_id):
    """Set a routine as active or inactive"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    active = request.json.get('active', True)
    
    if active:
        # Set this routine as active
        success = data_layer.set_active_routine(routine_id)
    else:
        # Clear active routine (deactivate)
        success = data_layer.clear_active_routine()
    
    return jsonify({"success": success})

@app.route('/api/routines/active', methods=['GET'])
def get_active_routine_alt():
    """Alternative active routine endpoint"""
    return active_routine()

# Development and testing routes
@app.route('/api/dev/clear-cache', methods=['POST'])
def clear_cache():
    """Clear any caches (useful during development)"""
    # For now, just return success
    return jsonify({"success": True, "message": "Cache cleared"})

@app.route('/api/dev/migrate-test', methods=['POST'])
def migrate_test():
    """Test data migration between systems"""
    return jsonify({
        "message": "Migration test not implemented yet",
        "current_mode": data_layer.mode
    })

@app.route('/api/chord-charts/common', methods=['GET'])
def get_common_chord_charts():
    """Get all common chord charts from the PostgreSQL database."""
    try:
        app.logger.info("Fetching all common chord charts from PostgreSQL")
        
        with DatabaseTransaction() as session:
            # Get all common chords from PostgreSQL
            result = session.execute(text("""
                SELECT id, title, chord_data, created_at, "order"
                FROM common_chords 
                ORDER BY "order" ASC, title ASC
            """))
            
            common_chords = []
            for row in result:
                chord_id, title, chord_data_str, created_at, order = row
                
                # Parse chord data JSON
                try:
                    import json
                    chord_data = json.loads(chord_data_str) if chord_data_str else {}
                except json.JSONDecodeError:
                    chord_data = {}
                
                common_chords.append({
                    'id': str(chord_id),
                    'title': title,
                    'chord_data': chord_data,
                    'created_at': created_at.isoformat() if created_at else None,
                    'order': order
                })
        
        # Add cache control headers to allow caching but ensure freshness
        response = jsonify(common_chords)
        response.headers['Cache-Control'] = 'public, max-age=300'  # Cache for 5 minutes
        
        app.logger.info(f"Returning {len(common_chords)} common chord charts from PostgreSQL")
        return response
        
    except Exception as e:
        app.logger.error(f"Error fetching common chord charts from PostgreSQL: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chord-charts/common/search', methods=['GET'])
def search_common_chords():
    """Search CommonChords by chord name"""
    chord_name = request.args.get('name', '').strip()
    if not chord_name:
        return jsonify({"error": "name parameter is required"}), 400
    
    try:
        # Search for exact matches first, then partial matches
        with DatabaseTransaction() as db:
            # Exact match first (case-insensitive)
            exact_results = db.execute(
                text("""
                    SELECT id, type, name, chord_data, created_at, order_col
                    FROM common_chords 
                    WHERE LOWER(name) = LOWER(:name)
                    ORDER BY order_col, id
                    LIMIT 10
                """),
                {"name": chord_name}
            ).fetchall()
            
            if exact_results:
                # Convert to format expected by frontend
                chords = []
                for row in exact_results:
                    # Parse the chord_data JSON and flatten it to top level
                    import json
                    chord_data = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                    
                    # Flatten chord data to top level for frontend compatibility  
                    chord_obj = {
                        "id": row[0],
                        "type": row[1], 
                        "title": row[2],  # Frontend expects 'title' not 'name'
                        "created_at": row[4],
                        "order": row[5],
                        # Flatten chord data properties to top level
                        "fingers": chord_data.get("fingers", []),
                        "barres": chord_data.get("barres", []),
                        "openStrings": chord_data.get("openStrings", []),
                        "mutedStrings": chord_data.get("mutedStrings", []),
                        "startingFret": chord_data.get("startingFret", 1),
                        "numFrets": chord_data.get("numFrets", 5),
                        "numStrings": chord_data.get("numStrings", 6),
                        "tuning": chord_data.get("tuning", "EADGBE"),
                        "capo": chord_data.get("capo", 0)
                    }
                    chords.append(chord_obj)
                return jsonify(chords)
            
            # If no exact matches, try partial matches
            partial_results = db.execute(
                text("""
                    SELECT id, type, name, chord_data, created_at, order_col
                    FROM common_chords 
                    WHERE LOWER(name) LIKE LOWER(:pattern)
                    ORDER BY order_col, id
                    LIMIT 10
                """),
                {"pattern": f"%{chord_name}%"}
            ).fetchall()
            
            chords = []
            for row in partial_results:
                # Parse the chord_data JSON and flatten it to top level
                import json
                chord_data = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                
                # Flatten chord data to top level for frontend compatibility  
                chord_obj = {
                    "id": row[0],
                    "type": row[1], 
                    "title": row[2],  # Frontend expects 'title' not 'name'
                    "created_at": row[4],
                    "order": row[5],
                    # Flatten chord data properties to top level
                    "fingers": chord_data.get("fingers", []),
                    "barres": chord_data.get("barres", []),
                    "openStrings": chord_data.get("openStrings", []),
                    "mutedStrings": chord_data.get("mutedStrings", []),
                    "startingFret": chord_data.get("startingFret", 1),
                    "numFrets": chord_data.get("numFrets", 5),
                    "numStrings": chord_data.get("numStrings", 6),
                    "tuning": chord_data.get("tuning", "EADGBE"),
                    "capo": chord_data.get("capo", 0)
                }
                chords.append(chord_obj)
            
            return jsonify(chords)
            
    except Exception as e:
        app.logger.error(f"Error searching CommonChords: {str(e)}")
        return jsonify({"error": "Failed to search CommonChords"}), 500

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    """Open a local folder in Windows Explorer (WSL-compatible)"""
    try:
        folder_path = request.json.get('path')
        if not folder_path:
            return jsonify({'error': 'No path provided'}), 400

        app.logger.debug(f"Opening folder: {folder_path}")

        # Keep Windows path format but ensure proper escaping
        windows_path = folder_path.replace('/', '\\')
        
        # In WSL, we'll use explorer.exe to open Windows File Explorer
        try:
            # Use the Windows path directly with explorer.exe
            subprocess.run(['explorer.exe', windows_path], check=True)
            return jsonify({'success': True})
        except subprocess.CalledProcessError as e:
            app.logger.error(f"Failed to open folder: {str(e)}")
            return jsonify({'error': f'Failed to open folder: {str(e)}'}), 500

    except Exception as e:
        app.logger.error(f"Error in open_folder: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Autocreate helper functions
def simple_analyze_files(client, uploaded_files, item_id):
    """Simplified file analysis that processes chord names by default"""
    try:
        app.logger.info(f"[AUTOCREATE] Processing {len(uploaded_files)} files as chord names")
        
        # For now, process everything as chord names (most common case)
        # This is a simplified version - the full implementation has more sophisticated detection
        
        # Create a simple prompt for chord name extraction
        message_content = []
        
        for i, file_data in enumerate(uploaded_files):
            if file_data['type'] == 'pdf':
                message_content.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_data['data']
                    }
                })
            elif file_data['type'] == 'image':
                message_content.append({
                    "type": "image", 
                    "source": {
                        "type": "base64",
                        "media_type": file_data['media_type'],
                        "data": file_data['data']
                    }
                })
        
        # Add the analysis prompt
        message_content.append({
            "type": "text",
            "text": """Extract chord names from this file. Look for chord symbols like G, C, Am, F7, etc.
            
Return a JSON array of chord objects with this format:
{
  "chords": [
    {"name": "G", "section": "Verse"},
    {"name": "C", "section": "Verse"},
    {"name": "Am", "section": "Chorus"},
    {"name": "F", "section": "Chorus"}
  ]
}

If you can't determine sections, use "Main" as the section name."""
        })
        
        # Call Claude API
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8000,
            messages=[{
                "role": "user", 
                "content": message_content
            }]
        )
        
        app.logger.info(f"[AUTOCREATE] Received response from Claude")
        
        # Parse response
        response_text = response.content[0].text
        
        # Extract JSON from response
        import json, re
        
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                chord_data = json.loads(json_match.group())
                chords = chord_data.get('chords', [])
                
                app.logger.info(f"[AUTOCREATE] Extracted {len(chords)} chords")
                
                # Create chord charts using the data layer
                if chords:
                    # Load CommonChords for lookup
                    app.logger.info("[AUTOCREATE] Loading CommonChords for chord shape lookup")
                    from app.sheets import get_common_chords_efficiently
                    common_chords = get_common_chords_efficiently()
                    
                    # Create lookup dictionary by chord name
                    chord_lookup = {}
                    for common_chord in common_chords:
                        chord_name = common_chord['title'].strip().upper()
                        chord_lookup[chord_name] = common_chord
                    
                    app.logger.info(f"[AUTOCREATE] Loaded {len(common_chords)} common chords for lookup")
                    
                    # Convert to the format expected by batch_add_chord_charts
                    chord_charts_data = []
                    for i, chord in enumerate(chords):
                        chord_name = chord['name'].strip().upper()
                        
                        # Look up chord shape in CommonChords
                        if chord_name in chord_lookup:
                            common_chord = chord_lookup[chord_name]
                            app.logger.info(f"[AUTOCREATE] Found shape for {chord_name}")
                            chord_data = {
                                'fingers': common_chord['fingers'],
                                'barres': common_chord['barres'],
                                'tuning': common_chord['tuning'] if isinstance(common_chord['tuning'], list) else ['E', 'A', 'D', 'G', 'B', 'E'],
                                'numFrets': common_chord['numFrets'],
                                'numStrings': common_chord['numStrings'],
                                'capo': common_chord['capo'],
                                'openStrings': common_chord['openStrings'],
                                'mutedStrings': common_chord['mutedStrings'],
                                'startingFret': common_chord['startingFret'],
                                'sectionId': f"section-{hash(chord.get('section', 'Main')) % 10000}",
                                'sectionLabel': chord.get('section', 'Main'),
                                'sectionRepeatCount': ''
                            }
                        else:
                            app.logger.warning(f"[AUTOCREATE] No shape found for {chord_name}, using empty chord")
                            chord_data = {
                                'fingers': [],
                                'barres': [],
                                'tuning': ['E', 'A', 'D', 'G', 'B', 'E'],
                                'sectionId': f"section-{hash(chord.get('section', 'Main')) % 10000}",
                                'sectionLabel': chord.get('section', 'Main'),
                                'sectionRepeatCount': ''
                            }
                        
                        chord_charts_data.append({
                            'title': chord['name'],
                            'chord_data': chord_data,
                            'order': i
                        })
                    
                    # Use data layer to create chord charts
                    app.logger.info(f"[AUTOCREATE] Creating {len(chord_charts_data)} chord charts in database")
                    results = data_layer.batch_add_chord_charts(item_id, chord_charts_data)
                    
                    return {
                        'success': True,
                        'message': f'Successfully created {len(chord_charts_data)} chord charts',
                        'chord_charts_created': len(chord_charts_data),
                        'analysis': f'Found chord progression: {", ".join([c["name"] for c in chords])}'
                    }
                else:
                    return {'error': 'No chords found in the uploaded file'}
                    
            except json.JSONDecodeError as e:
                app.logger.error(f"Failed to parse JSON from Claude response: {e}")
                return {'error': 'Failed to parse chord data from file'}
        else:
            return {'error': 'No chord data found in file'}
            
    except Exception as e:
        app.logger.error(f"Error in simple_analyze_files: {str(e)}")
        return {'error': f'Analysis failed: {str(e)}'}


# Chord chart copy functionality  
@app.route('/api/chord-charts/copy', methods=['POST'])
def copy_chord_charts_route():
    """Copy chord charts from one song to multiple other songs."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        source_item_id = data.get('source_item_id')
        target_item_ids = data.get('target_item_ids', [])
        
        if not source_item_id:
            return jsonify({"error": "source_item_id is required"}), 400
            
        if not target_item_ids or not isinstance(target_item_ids, list):
            return jsonify({"error": "target_item_ids must be a non-empty array"}), 400
        
        app.logger.info(f"Copying chord charts from item {source_item_id} to items {target_item_ids}")
        
        # Use the data layer for PostgreSQL compatibility
        result = data_layer.copy_chord_charts_to_items(source_item_id, target_item_ids)
        
        app.logger.info(f"Successfully copied {result['charts_found']} chord charts to {len(result['target_items'])} items")
        
        return jsonify({
            'success': True,
            'message': f"Copied {result['charts_found']} chord charts to {len(result['target_items'])} songs",
            'result': result
        })
        
    except Exception as e:
        app.logger.error(f"Error copying chord charts: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500