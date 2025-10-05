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
import json

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

        app.logger.info(f"Attempting to update item with ID: {item_id}, data: {request.json}")
        updated_item = data_layer.update_item(item_id, request.json)
        if updated_item:
            app.logger.info(f"Successfully updated item {item_id}")
            return jsonify(updated_item)
        else:
            app.logger.warning(f"Failed to update item {item_id} - item not found or update failed")
            return jsonify({"error": f"Item {item_id} not found or update failed"}), 404
        
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

# Item-specific chord chart deletion (supports sharing)
@app.route('/api/items/<int:item_id>/chord-charts/<int:chart_id>', methods=['DELETE'])
def delete_chord_chart_from_item(item_id, chart_id):
    """Delete a chord chart from a specific item (handles sharing properly)"""
    try:
        success = data_layer.delete_chord_chart_from_item(item_id, chart_id)
        return jsonify({"success": success})
    except Exception as e:
        app.logger.error(f"Error deleting chord chart {chart_id} from item {item_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Batch chord chart operations
@app.route('/api/items/<int:item_id>/chord-charts/batch', methods=['POST'])
def batch_add_chord_charts(item_id):
    """Create multiple chord charts at once"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    chord_charts_data = request.json
    app.logger.info(f"[MANUAL] Batch add chord charts for item {item_id}, received {len(chord_charts_data) if isinstance(chord_charts_data, list) else 'invalid'} charts")
    app.logger.info(f"[MANUAL] Chord charts data: {chord_charts_data}")

    if not isinstance(chord_charts_data, list):
        return jsonify({"error": "Request must be a list of chord charts"}), 400

    results = data_layer.batch_add_chord_charts(item_id, chord_charts_data)
    app.logger.info(f"[MANUAL] Batch add results: {results}")
    return jsonify(results)

@app.route('/api/chord-charts/batch-delete', methods=['POST'])
def batch_delete_chord_charts():
    """Delete multiple chord charts by IDs in a single transaction."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        chord_ids = data.get('chord_ids', [])
        item_id = data.get('item_id')  # Optional item context for sharing-aware deletion

        app.logger.info(f"DEBUG: Received batch delete request - data: {data}")
        app.logger.info(f"DEBUG: chord_ids: {chord_ids}, item_id: {item_id}")

        if not chord_ids:
            return jsonify({"error": "No chord IDs provided"}), 400

        if not isinstance(chord_ids, list):
            return jsonify({"error": "chord_ids must be an array"}), 400

        if item_id:
            app.logger.info(f"Batch deleting chord charts {chord_ids} from item {item_id} (sharing-aware)")
        else:
            app.logger.info(f"Batch deleting chord charts: {chord_ids} (complete deletion)")

        result = data_layer.batch_delete_chord_charts(chord_ids, item_id)
        
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

# YouTube transcript checking
@app.route('/api/youtube/check-transcript', methods=['POST'])
def check_youtube_transcript():
    """Check if a YouTube video has transcripts available"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        import re

        data = request.get_json()
        youtube_url = data.get('url')

        if not youtube_url:
            return jsonify({"error": "YouTube URL is required"}), 400

        app.logger.info(f"[YOUTUBE] Checking transcript for YouTube URL: {youtube_url}")

        # Extract video ID from YouTube URL
        video_id = extract_youtube_video_id(youtube_url)
        if not video_id:
            app.logger.error(f"[YOUTUBE] Invalid YouTube URL format: {youtube_url}")
            return jsonify({"error": "Invalid YouTube URL format"}), 400

        app.logger.info(f"[YOUTUBE] Extracted video ID: {video_id}")

        try:
            # Check if transcripts are available using 2025 API syntax
            app.logger.info(f"[YOUTUBE] Attempting to get transcript for video ID: {video_id}")
            ytt_api = YouTubeTranscriptApi()
            transcript_data = ytt_api.fetch(video_id)
            app.logger.info(f"[YOUTUBE] Successfully got transcript for video ID: {video_id}")

            # Extract text from transcript snippets
            snippets = transcript_data.snippets
            full_transcript = ' '.join([snippet.text for snippet in snippets])

            app.logger.info(f"[YOUTUBE] Successfully extracted transcript for video ID: {video_id}, length: {len(full_transcript)} characters, snippets: {len(snippets)}")

            return jsonify({
                "hasTranscript": True,
                "transcript": full_transcript
            })

        except Exception as transcript_error:
            app.logger.error(f"[YOUTUBE] No transcripts available for video ID {video_id}: {str(transcript_error)}")
            return jsonify({
                "hasTranscript": False,
                "transcript": None
            })

    except Exception as e:
        app.logger.error(f"Error checking YouTube transcript: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to check YouTube transcript: {str(e)}"}), 500

def extract_youtube_video_id(url):
    """Extract video ID from various YouTube URL formats"""
    import re

    # Regular expression patterns for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/watch\?.*?v=([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None

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
                
            # Check file size (5MB limit)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > 5 * 1024 * 1024:  # 5MB
                return {'error': f'File {filename} is too large (max 5MB)'}
                
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
            elif file_ext in ['txt'] or filename == 'youtube_transcript.txt':
                # Handle text files (including YouTube transcripts) as chord_names
                return {
                    'name': filename,
                    'type': 'chord_names',
                    'data': file_data.decode('utf-8')  # Store as text, not base64
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
        from app.utils.llm_analytics import track_llm_generation, track_llm_span
        client = anthropic.Anthropic(api_key=api_key)
        app.logger.info(f"[AUTOCREATE] Anthropic client initialized successfully")

        # Prepare the Claude analysis request
        app.logger.info(f"[AUTOCREATE] Starting Claude analysis for item {item_id}")
        app.logger.debug("Sending files to Claude for analysis")

        # Process with simplified autocreate logic
        analysis_result = analyze_files_with_claude(client, uploaded_files, item_id)
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

@app.route('/api/routines/<int:routine_id>/items/<item_id>', methods=['PUT', 'DELETE'])
def routine_item(routine_id, item_id):
    """Handle PUT (update) and DELETE for routine items"""
    routine_item_id = int(item_id)

    if request.method == 'PUT':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        update_data = request.json
        app.logger.info(f"Updating routine item {routine_item_id} in routine {routine_id} with data: {update_data}")

        try:
            updated_item = data_layer.update_routine_item(routine_id, routine_item_id, update_data)
            if updated_item:
                app.logger.info(f"Successfully updated routine item {routine_item_id}")
                return jsonify(updated_item)
            else:
                app.logger.warning(f"Routine item {routine_item_id} not found")
                return jsonify({"error": "Routine item not found"}), 404
        except Exception as e:
            app.logger.error(f"Error updating routine item: {str(e)}")
            return jsonify({"error": str(e)}), 500

    elif request.method == 'DELETE':
        """Remove an item from a routine by routine item ID (matches sheets version)"""
        success = data_layer.remove_routine_item_by_id(routine_id, routine_item_id)
        return jsonify({"success": success})

# Routine ordering (for main routines list drag-and-drop)
@app.route('/api/routines/order', methods=['PUT'])
def update_routines_order():
    """Update the order of routines in the main routines list"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    try:
        updates = request.json
        app.logger.info(f"Updating routines order with: {updates}")
        success = data_layer.update_routines_order(updates)
        return jsonify({"success": success})
    except Exception as e:
        app.logger.error(f"Error updating routines order: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/routines/<int:routine_id>/items/order', methods=['PUT'])
def update_routine_items_order(routine_id):
    """Update routine item ordering"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    app.logger.info(f"Updating routine {routine_id} items order with data: {request.json}")
    try:
        success = data_layer.update_routine_items_order(routine_id, request.json)
        app.logger.info(f"DataLayer returned success: {success}")
        return jsonify({"success": success})
    except Exception as e:
        app.logger.error(f"Error in routine items order endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/routines/<int:routine_id>/order', methods=['PUT'])
def update_routine_order_route(routine_id):
    """Update routine item ordering (alternative endpoint to match sheets version)"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    success = data_layer.update_routine_items_order(routine_id, request.json)
    if success:
        # Match sheets version: return updated items array
        updated_items = data_layer.get_routine_items(routine_id)
        return jsonify(updated_items)
    else:
        return jsonify({"error": "Failed to update order"}), 500

@app.route('/api/routines/<int:routine_id>/items/<int:routine_item_id>/complete', methods=['PUT'])
def mark_routine_item_complete(routine_id, routine_item_id):
    """Mark a routine item as completed or not"""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    completed = request.json.get('completed', True)
    success = data_layer.mark_item_complete(routine_id, routine_item_id, completed)
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
        # CRITICAL: item structure is {routineEntry: {...}, itemDetails: {...}}
        # Need to access nested properties correctly
        routine_entry = item.get("routineEntry", {})
        item_details = item.get("itemDetails", {})

        items_with_minimal_details.append({
            "routineEntry": {
                "A": routine_entry.get("A"),  # Routine item ID
                "B": routine_entry.get("B"),  # Item ID (Google Sheets ItemID like "67")
                "C": routine_entry.get("C"),  # Order
                "D": routine_entry.get("D")   # Completed status (already "TRUE"/"FALSE")
            },
            "itemMinimal": {
                "A": item_details.get("A", ""),  # Item ID
                "C": item_details.get("C", "")   # Item title
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

                    # Normalize finger data from objects to arrays (same as sheets version)
                    raw_fingers = chord_data.get('fingers', [])
                    normalized_fingers = []

                    for finger in raw_fingers:
                        if isinstance(finger, dict):
                            string_num = finger.get('string')
                            fret_num = finger.get('fret')
                            finger_num = finger.get('finger')
                            if string_num is not None and fret_num is not None:
                                if finger_num is not None:
                                    normalized_fingers.append([string_num, fret_num, finger_num])
                                else:
                                    normalized_fingers.append([string_num, fret_num])
                        elif isinstance(finger, list) and len(finger) >= 2:
                            normalized_fingers.append(finger)

                    # Flatten chord data to top level for frontend compatibility
                    chord_obj = {
                        "id": row[0],
                        "type": row[1],
                        "title": row[2],  # Frontend expects 'title' not 'name'
                        "created_at": row[4],
                        "order": row[5],
                        # Use normalized finger data instead of raw
                        "fingers": normalized_fingers,
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

                # Normalize finger data from objects to arrays (same as sheets version)
                raw_fingers = chord_data.get('fingers', [])
                normalized_fingers = []

                for finger in raw_fingers:
                    if isinstance(finger, dict):
                        string_num = finger.get('string')
                        fret_num = finger.get('fret')
                        finger_num = finger.get('finger')
                        if string_num is not None and fret_num is not None:
                            if finger_num is not None:
                                normalized_fingers.append([string_num, fret_num, finger_num])
                            else:
                                normalized_fingers.append([string_num, fret_num])
                    elif isinstance(finger, list) and len(finger) >= 2:
                        normalized_fingers.append(finger)

                # Flatten chord data to top level for frontend compatibility
                chord_obj = {
                    "id": row[0],
                    "type": row[1],
                    "title": row[2],  # Frontend expects 'title' not 'name'
                    "created_at": row[4],
                    "order": row[5],
                    # Use normalized finger data instead of raw
                    "fingers": normalized_fingers,
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
    """Open a local folder in the platform-appropriate file manager"""
    try:
        folder_path = request.json.get('path')
        if not folder_path:
            return jsonify({'error': 'No path provided'}), 400

        app.logger.debug(f"Opening folder: {folder_path}")

        # Detect platform and use appropriate command (like sheets version)
        import platform
        import os
        system = platform.system().lower()

        try:
            # Check if we're in WSL (Windows Subsystem for Linux)
            is_wsl = os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower()

            if system == 'windows' or is_wsl:
                # Windows (including WSL) - use explorer.exe like sheets version
                windows_path = folder_path.replace('/', '\\')
                try:
                    subprocess.run(['explorer.exe', windows_path], check=True)
                except subprocess.CalledProcessError:
                    # explorer.exe often returns non-zero exit status even when successful
                    # If it fails, it usually means the path doesn't exist, but folder still might open
                    pass  # Consider it successful since explorer behavior is inconsistent
            elif system == 'darwin':
                # macOS
                subprocess.run(['open', folder_path], check=True)
            elif system == 'linux':
                # Linux with GUI (X11/Wayland)
                subprocess.run(['xdg-open', folder_path], check=True)
            else:
                return jsonify({'error': f'Unsupported platform: {system}'}), 400

            return jsonify({'success': True, 'platform': system})

        except subprocess.CalledProcessError as e:
            app.logger.error(f"Failed to open folder on {system}: {str(e)}")
            return jsonify({'error': f'Failed to open folder: {str(e)}'}), 500
        except FileNotFoundError as e:
            app.logger.error(f"File manager not found on {system}: {str(e)}")
            return jsonify({'error': f'File manager not available on {system}'}), 500

    except Exception as e:
        app.logger.error(f"Error in open_folder: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Autocreate helper functions

def detect_file_types_with_sonnet(client, uploaded_files):
    """Detect file types using Sonnet 4 model (ported from sheets version)"""
    import time
    import json

    try:
        app.logger.info("Using Sonnet 4 to detect file types and content")

        # Build message content with files for analysis
        prompt_text = """🎸 **FILE TYPE DETECTION FOR GUITAR CONTENT**

Analyze the uploaded files and determine their content types. You need to categorize each file as either:

1. **"chord_charts"** - Files containing visual chord diagrams that can be imported directly
   - Hand-drawn chord charts
   - Printed chord reference sheets
   - Digital chord diagrams
   - Any files showing finger positions on fretboards

2. **"chord_names"** - Files with chord symbols above lyrics for CommonChords lookup
   - Lyrics with chord names above them (G, C, Am, etc.)
   - Song sheets with chord symbols
   - Lead sheets with chord progressions over text

3. **"tablature"** - Files containing actual guitar tablature notation
   - Text-based tablature with fret numbers on horizontal string lines (e.g. E|--0--3--0--|)
   - Tab files showing fingering patterns with numbers indicating frets

4. **"sheet_music"** - Files containing standard music notation
   - Traditional music notation with notes on staff lines
   - PDF files with musical scores and notation

**RESPONSE FORMAT:**
Return JSON with this exact structure:
```json
{
  "primary_type": "chord_charts",
  "has_mixed_content": false,
  "content_types": ["chord_charts"],
  "analysis": {
    "file_breakdown": [
      {
        "filename": "example.pdf",
        "type": "chord_charts",
        "confidence": "high",
        "reason": "Contains visual chord diagrams with finger positions"
      }
    ]
  }
}
```

**RULES:**
- Set "has_mixed_content": true ONLY if files contain BOTH visual chord diagrams AND chord names above lyrics
- Files with only chord names above lyrics (no visual diagrams) should be "chord_names" with has_mixed_content: false
- Files with only visual chord diagrams (no lyrics/chord names) should be "chord_charts" with has_mixed_content: false
- "primary_type" should be the most common content type found
- Use "high", "medium", or "low" for confidence levels
- Provide clear reasoning for each file classification

Analyze the files below:"""

        message_content = [{
            "type": "text",
            "text": prompt_text
        }]

        # Add all files for analysis
        for file_content in uploaded_files:
            name = file_content['name']

            # Add file label
            message_content.append({
                "type": "text",
                "text": f"\n\n**FILE: {name}**"
            })

            if file_content['type'] == 'pdf':
                message_content.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_content['data']
                    }
                })
            elif file_content['type'] == 'image':
                message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_content['media_type'],
                        "data": file_content['data']
                    }
                })

        # Use Sonnet 4 for file type detection
        llm_start_time = time.time()
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": message_content
            }]
        )
        llm_end_time = time.time()

        # Track LLM Analytics for file type detection
        from app.utils.llm_analytics import llm_analytics
        llm_analytics.track_generation(
            model="claude-sonnet-4-5-20250929",
            input_messages=[{"role": "user", "content": "File type detection for guitar content"}],
            output_choices=[{"message": {"content": response.content[0].text}}],
            usage={
                "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else None,
                "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else None
            },
            latency_seconds=llm_end_time - llm_start_time,
            custom_properties={
                "function": "detect_file_types_with_sonnet",
                "file_count": len(uploaded_files),
                "analysis_type": "file_type_detection"
            }
        )

        response_text = response.content[0].text

        # Parse JSON response
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON without markdown wrapper
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Fallback to chord_names if no JSON found
                app.logger.warning("Could not parse file type detection response, defaulting to chord_names")
                # For YouTube transcripts, don't trigger mixed content modal
                is_youtube_transcript = any(file_data.get('name') == 'youtube_transcript.txt' for file_data in uploaded_files)
                return {
                    "primary_type": "chord_names",
                    "has_mixed_content": not is_youtube_transcript,  # YouTube transcripts skip mixed content modal
                    "content_types": ["chord_names"] if is_youtube_transcript else ["chord_names"],
                    "analysis": {"error": "Could not parse detection response"}
                }

        result = json.loads(json_str)
        app.logger.info(f"File type detection result: {result.get('primary_type', 'unknown')} (mixed: {result.get('has_mixed_content', True)})")
        return result

    except Exception as e:
        app.logger.error(f"File type detection failed: {str(e)}")
        # Default to chord_names processing on error
        # For YouTube transcripts, don't trigger mixed content modal
        is_youtube_transcript = any(file_data.get('name') == 'youtube_transcript.txt' for file_data in uploaded_files)
        return {
            "primary_type": "chord_names",
            "has_mixed_content": not is_youtube_transcript,  # YouTube transcripts skip mixed content modal
            "content_types": ["chord_names"] if is_youtube_transcript else ["tablature"],
            "analysis": {"error": str(e)}
        }

def analyze_files_with_claude(client, uploaded_files, item_id):
    """Analyze files and route to appropriate processing function (complete sheets version)"""
    try:
        app.logger.info(f"[AUTOCREATE] analyze_files_with_claude called with {len(uploaded_files)} files for item {item_id}")

        # Check if user forced a type choice
        forced_type = None
        for file_data in uploaded_files:
            if 'forced_type' in file_data:
                forced_type = file_data['forced_type']
                break

        if forced_type:
            app.logger.info(f"[AUTOCREATE] User forced processing as: {forced_type}")
            # Skip detection, go straight to processing
            if forced_type == 'chord_charts':
                app.logger.info(f"[AUTOCREATE] Processing as chord charts (user choice)")
                return process_chord_charts_directly(client, uploaded_files, item_id)
            elif forced_type == 'chord_names':
                app.logger.info(f"[AUTOCREATE] Processing as chord names (user choice)")
                return process_chord_names_with_lyrics(client, uploaded_files, item_id)
            else:
                app.logger.warning(f"[AUTOCREATE] Unknown forced type: {forced_type}, falling back to chord names")
                return process_chord_names_with_lyrics(client, uploaded_files, item_id)

        # Step 1: File type detection using Sonnet 4
        app.logger.info(f"[AUTOCREATE] Step 1: Analyzing {len(uploaded_files)} files to detect content type using Sonnet 4")
        file_type_result = detect_file_types_with_sonnet(client, uploaded_files)

        # Step 2: Process based on detected content type
        if file_type_result.get('has_mixed_content'):
            # TODO: Return data for mixed content modal (Steven's requirement #2)
            return {
                'needs_user_choice': True,
                'mixed_content_options': file_type_result.get('content_types', []),
                'files': uploaded_files
            }

        # Process based on primary content type
        primary_type = file_type_result.get('primary_type', 'chord_names')
        app.logger.info(f"Processing files as: {primary_type}")

        # Step 3: Process files based on detected type
        if primary_type == 'chord_charts':
            return process_chord_charts_directly(client, uploaded_files, item_id)
        elif primary_type == 'chord_names':
            # Check if this is a YouTube transcript
            is_youtube_transcript = any(file_data.get('name') == 'youtube_transcript.txt' for file_data in uploaded_files)
            if is_youtube_transcript:
                return process_chord_names_from_youtube_transcript(client, uploaded_files, item_id)
            else:
                return process_chord_names_with_lyrics(client, uploaded_files, item_id)
        elif primary_type == 'tablature':
            return {
                'error': 'unsupported_format',
                'message': 'Sorry, we can only build chord charts. We can\'t process tablature here.',
                'title': 'Tablature Not Supported'
            }
        elif primary_type == 'sheet_music':
            return {
                'error': 'unsupported_format',
                'message': 'Sorry, we can only build chord charts. We can\'t process sheet music here.',
                'title': 'Sheet Music Not Supported'
            }
        else:
            # Fallback to chord names processing (most common case)
            app.logger.warning(f"Unknown primary_type '{primary_type}', falling back to chord names processing")
            return process_chord_names_with_lyrics(client, uploaded_files, item_id)

    except Exception as e:
        app.logger.error(f"Error in Claude analysis: {str(e)}")
        return {'error': f'Analysis failed: {str(e)}'}

def simple_analyze_files(client, uploaded_files, item_id):
    """Simplified file analysis that processes chord names by default"""
    import time
    from app.utils.llm_analytics import track_llm_generation, track_llm_span

    # Start timing for analytics
    start_time = time.time()
    generation_id = None

    try:
        app.logger.info(f"[AUTOCREATE] Processing {len(uploaded_files)} files as chord names")

        # Track span for file processing
        processing_span_id = track_llm_span(
            name="file_processing",
            span_type="preprocessing",
            start_time=start_time,
            custom_properties={
                "file_count": len(uploaded_files),
                "item_id": item_id,
                "file_types": [f.get("type") for f in uploaded_files]
            }
        )

        # For now, process everything as chord names (most common case)
        # This is a simplified version - the full implementation has more sophisticated detection
        
        # Create message content with cacheable instructions first, then variable files
        message_content = []

        # Add the static analysis prompt first with caching enabled
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

If you can't determine sections, use "Main" as the section name.""",
            "cache_control": {"type": "ephemeral"}
        })

        # Then add the variable file content
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

        # Call Claude API with prompt caching enabled
        llm_start_time = time.time()
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8000,
                messages=[{
                    "role": "user",
                    "content": message_content
                }],
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
            )
            llm_end_time = time.time()
            llm_latency = (llm_end_time - llm_start_time) * 1000  # Convert to milliseconds

            app.logger.info(f"[AUTOCREATE] Received response from Claude")

            # Extract usage information for analytics
            usage_dict = {}
            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                usage_dict = {
                    "input_tokens": getattr(usage, 'input_tokens', 0),
                    "output_tokens": getattr(usage, 'output_tokens', 0),
                    "cache_creation_input_tokens": getattr(usage, 'cache_creation_input_tokens', 0),
                    "cache_read_input_tokens": getattr(usage, 'cache_read_input_tokens', 0)
                }

                # Log cache usage
                if usage_dict.get('cache_creation_input_tokens'):
                    app.logger.info(f"[CACHE] Cache creation tokens: {usage_dict['cache_creation_input_tokens']}")
                if usage_dict.get('cache_read_input_tokens'):
                    app.logger.info(f"[CACHE] Cache read tokens: {usage_dict['cache_read_input_tokens']}")
                app.logger.info(f"[USAGE] Input tokens: {usage_dict['input_tokens']}, Output tokens: {usage_dict['output_tokens']}")

            # Track the LLM generation with PostHog LLM Analytics
            generation_id = track_llm_generation(
                model="claude-sonnet-4-5-20250929",
                input_messages=[{
                    "role": "user",
                    "content": "Extract chord names from uploaded guitar files"  # Simplified for privacy
                }],
                output_choices=[{
                    "role": "assistant",
                    "content": response.content[0].text[:200] + "..." if len(response.content[0].text) > 200 else response.content[0].text
                }],
                usage=usage_dict,
                latency_seconds=llm_latency / 1000,  # Will be converted back to ms in track_llm_generation
                status="success",
                custom_properties={
                    "feature": "autocreate_chord_charts",
                    "item_id": item_id,
                    "file_count": len(uploaded_files),
                    "file_types": [f.get("type") for f in uploaded_files],
                    "prompt_caching_enabled": True,
                    "cache_hit": bool(usage_dict.get('cache_read_input_tokens', 0) > 0)
                },
                privacy_mode=False  # Set to True to exclude actual input/output
            )

        except Exception as api_error:
            llm_end_time = time.time()
            llm_latency = (llm_end_time - llm_start_time) * 1000

            # Track failed generation
            generation_id = track_llm_generation(
                model="claude-sonnet-4-5-20250929",
                input_messages=[{"role": "user", "content": "Extract chord names from uploaded guitar files"}],
                output_choices=[],
                latency_seconds=llm_latency / 1000,  # Will be converted back to ms in track_llm_generation
                status="error",
                error=str(api_error),
                custom_properties={
                    "feature": "autocreate_chord_charts",
                    "item_id": item_id,
                    "file_count": len(uploaded_files),
                    "error_type": type(api_error).__name__
                }
            )
            raise api_error

        # Parse response
        response_text = response.content[0].text

        # Extract JSON from response
        import json, re

        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                chord_data = json.loads(json_match.group())

                # Handle both legacy and modern formats (matching sheets version behavior)
                chords = []

                # Check for modern sections-based format first (preferred)
                sections = chord_data.get('sections', [])
                if sections:
                    app.logger.info(f"[AUTOCREATE] Processing modern sections format with {len(sections)} sections")
                    for section in sections:
                        section_chords = section.get('chords', [])
                        section_label = section.get('label', 'Main')
                        for chord in section_chords:
                            # Add section info to chord for processing
                            chord['section'] = section_label
                            chords.append(chord)
                else:
                    # Fall back to legacy format (chord_data.chords with row/position)
                    chords = chord_data.get('chords', [])
                    app.logger.info(f"[AUTOCREATE] Processing legacy chords format")

                app.logger.info(f"[AUTOCREATE] Extracted {len(chords)} total chords")
                
                # Create chord charts using the data layer
                if chords:
                    # Load CommonChords for lookup
                    app.logger.info("[AUTOCREATE] Loading CommonChords for chord shape lookup")
                    common_chords = data_layer.get_common_chords_efficiently()
                    
                    # Create lookup dictionary by chord name
                    chord_lookup = {}
                    for common_chord in common_chords:
                        chord_name = common_chord['title'].strip().upper()
                        chord_lookup[chord_name] = common_chord
                    
                    app.logger.info(f"[AUTOCREATE] Loaded {len(common_chords)} common chords for lookup")
                    
                    # Convert to the format expected by batch_add_chord_charts
                    chord_charts_data = []

                    def process_single_chord(chord, chord_lookup, chord_charts_data, order):
                        chord_name = chord['name'].strip().upper()

                        # Look up chord shape in CommonChords
                        if chord_name in chord_lookup:
                            common_chord = chord_lookup[chord_name]
                            app.logger.info(f"[AUTOCREATE] Found shape for {chord_name}")

                            # Filter CommonChords fingers to only include fretted positions (fret > 0)
                            # This matches the visual analysis filtering and prevents blank chord displays
                            raw_fingers = common_chord['fingers']
                            filtered_fingers = []
                            if raw_fingers:
                                for finger in raw_fingers:
                                    if isinstance(finger, list) and len(finger) >= 2 and finger[1] > 0:
                                        filtered_fingers.append(finger)

                            chord_data = {
                                'fingers': filtered_fingers,
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
                                'sectionRepeatCount': '',
                                'lineBreakAfter': chord.get('lineBreakAfter', False)
                            }
                        else:
                            app.logger.warning(f"[AUTOCREATE] No shape found for {chord_name}, using empty chord")
                            chord_data = {
                                'fingers': [],
                                'barres': [],
                                'tuning': ['E', 'A', 'D', 'G', 'B', 'E'],
                                'sectionId': f"section-{hash(chord.get('section', 'Main')) % 10000}",
                                'sectionLabel': chord.get('section', 'Main'),
                                'sectionRepeatCount': '',
                                'lineBreakAfter': chord.get('lineBreakAfter', False)
                            }

                        chord_charts_data.append({
                            'title': chord['name'],
                            'chord_data': chord_data,
                            'order': order
                        })

                    # Handle both legacy row/position format and modern sections format for layout preservation
                    if chords and ('row' in chords[0] or any('row' in chord for chord in chords)):
                        app.logger.info("[AUTOCREATE] Processing format with row/position layout preservation")
                        # Group chords by section, then by row and position for layout preservation
                        sections_with_rows = {}
                        for chord in chords:
                            section = chord.get('section', 'Main')
                            row = chord.get('row', 1)
                            position = chord.get('position', 1)

                            if section not in sections_with_rows:
                                sections_with_rows[section] = {}
                            if row not in sections_with_rows[section]:
                                sections_with_rows[section][row] = {}
                            sections_with_rows[section][row][position] = chord

                        # Process chords maintaining section and row structure
                        for section_name in sections_with_rows:
                            rows = sections_with_rows[section_name]
                            for row_num in sorted(rows.keys()):
                                row_positions = rows[row_num]
                                max_position = max(row_positions.keys())
                                for pos_num in sorted(row_positions.keys()):
                                    chord = row_positions[pos_num]
                                    chord['section'] = section_name

                                    # Set lineBreakAfter for last chord in row to preserve layout
                                    chord['lineBreakAfter'] = (pos_num == max_position)

                                    # Process this chord
                                    process_single_chord(chord, chord_lookup, chord_charts_data, len(chord_charts_data))
                    else:
                        # Handle modern format without row/position or simple list
                        for i, chord in enumerate(chords):
                            # Check if lineBreakAfter is explicitly set from Claude's response
                            if 'lineBreakAfter' not in chord:
                                chord['lineBreakAfter'] = False  # Default to false
                            process_single_chord(chord, chord_lookup, chord_charts_data, i)
                    
                    # Track span for database operations
                    db_start_time = time.time()
                    db_span_id = track_llm_span(
                        name="database_chord_creation",
                        span_type="database",
                        start_time=db_start_time,
                        generation_id=generation_id,
                        custom_properties={
                            "chord_count": len(chord_charts_data),
                            "item_id": item_id
                        }
                    )

                    # Use data layer to create chord charts
                    app.logger.info(f"[AUTOCREATE] Creating {len(chord_charts_data)} chord charts in database")
                    results = data_layer.batch_add_chord_charts(item_id, chord_charts_data)

                    # Complete database span
                    db_end_time = time.time()
                    track_llm_span(
                        name="database_chord_creation",
                        span_type="database",
                        start_time=db_start_time,
                        end_time=db_end_time,
                        generation_id=generation_id,
                        custom_properties={
                            "chord_count": len(chord_charts_data),
                            "item_id": item_id,
                            "success": True
                        },
                        status="success"
                    )

                    # Complete processing span
                    processing_end_time = time.time()
                    track_llm_span(
                        name="file_processing",
                        span_type="preprocessing",
                        start_time=start_time,
                        end_time=processing_end_time,
                        generation_id=generation_id,
                        custom_properties={
                            "file_count": len(uploaded_files),
                            "item_id": item_id,
                            "chords_extracted": len(chords),
                            "chords_created": len(chord_charts_data)
                        },
                        status="success"
                    )

                    return {
                        'success': True,
                        'message': f'Successfully created {len(chord_charts_data)} chord charts',
                        'chord_charts_created': len(chord_charts_data),
                        'analysis': f'Found chord progression: {", ".join([c["name"] for c in chords])}',
                        'generation_id': generation_id  # For analytics correlation
                    }
                else:
                    return {'error': 'No chords found in the uploaded file'}
                    
            except json.JSONDecodeError as e:
                app.logger.error(f"Failed to parse JSON from Claude response: {e}")
                return {'error': 'Failed to parse chord data from file'}
        else:
            return {'error': 'No chord data found in file'}
            
    except Exception as e:
        # Track error span if we have a generation_id
        if generation_id:
            error_end_time = time.time()
            track_llm_span(
                name="file_processing",
                span_type="preprocessing",
                start_time=start_time,
                end_time=error_end_time,
                generation_id=generation_id,
                custom_properties={
                    "file_count": len(uploaded_files),
                    "item_id": item_id,
                    "error_type": type(e).__name__
                },
                status="error",
                error=str(e)
            )

        app.logger.error(f"Error in simple_analyze_files: {str(e)}")
        return {'error': f'Analysis failed: {str(e)}'}

def process_chord_charts_directly(client, uploaded_files, item_id):
    """Process files containing chord charts for direct import (complete sheets version)"""
    import time
    import json

    try:
        app.logger.info("Processing chord chart files for direct import")

        prompt_text = """🎸 **CHORD DIAGRAM VISUAL ANALYSIS WITH LAYOUT STRUCTURE**

Hey there! I need your help with something really important. I'm asking you to look at guitar chord diagrams and extract the exact finger positions you see. This is tricky because I need you to be like a perfect camera - just tell me what's there, don't "correct" anything based on what you think it should be.

**🚨 REALLY IMPORTANT:** Here's the thing - please don't use any of your guitar knowledge here. I know you know what an "Em9" or "C7/G" chord typically looks like, but I need you to completely ignore that knowledge. Think of yourself as someone who's never seen a guitar chord before - you're just looking at dots and lines and telling me where the dots are positioned.

Why? Because people create their own chord variations and fingerings, and we want to capture THEIR version, not the "standard" version you might know.

**FUNDAMENTAL RULE**: If the file contains chord charts, that's the user's way of asking you to use exactly the chord chart fingerings/shapes and chord chart names seen in the reference image. DO NOT substitute standard tuning patterns - use only what you actually see in the chord charts in the uploaded file.

**OVERRIDE INSTRUCTION**: If the uploaded file contains only Chord Charts (no lyrics), then even if you recognize these as "standard" chord names like E, A, G, etc., you MUST read the actual marker positions shown in THIS specific diagram. These may not be standard tuning - read only what you see, not what you expect these chords to look like.

**Here's how to read these diagrams:**

**Fret Counting** (this trips people up a lot):
- That thick line at the top? That's the "nut" - call it fret 0
- **Fret 1** is the space between the nut and the next horizontal line down
- **Fret 2** is the space between the 2nd and 3rd horizontal lines
- **Fret 3** is the space between the 3rd and 4th horizontal lines
- You're counting the *spaces between lines*, not the lines themselves!

**String Order** (left to right):
- String 6 = Leftmost vertical line (lowest pitch)
- String 5 = Second from left
- String 4 = Third from left
- String 3 = Fourth from left
- String 2 = Second from right
- String 1 = Rightmost vertical line (highest pitch)

**What the symbols mean:**
- Dots, circles, numbered circles (1,2,3,4), lettered circles (T) = finger positions (NOTE: Numbers inside of circles denote which finger is to be used. Do not confuse numbers in the image for marker positions.)
- "O" above the nut = play this string open (fret 0)
- "X" above the nut = don't play this string (muted, fret -1)

**Please ignore these completely:**
- Any "3fr", "5fr" position markers - those are just reference, not part of the pattern
- What you think the chord "should" be - just tell me what you see!

**CRITICAL: Layout and Structure Rules:**
- Match the layout of chords exactly as seen in the uploaded file
- **Section Preservation**: When you see sections labeled `Intro`, `Verse 1`, `Chorus`, `Solo`, `Bridge`, `Outro`, etc, replicate those sections, and fill with the same chords seen in the uploaded chord chart file
- **Line Breaks Within Sections**: Mark where new rows begin, match the uploaded file
- **Row Counting**: Assign row numbers (1, 2, 3...) to track chord layout within each section
- **Position Counting**: Assign position numbers (1, 2, 3...) within each row
- Read left-to-right, top-to-bottom - exactly as they appear in the file
- Identify line breaks - when chord diagrams start a new row
- Use EXACT chord names from diagrams, remove capo suffixes like "(capoOn2)"
- Group chords that appear on the same horizontal level
- Preserve the exact order - number chords 1, 2, 3... in reading order
- **Set lineBreakAfter: true for the last chord in each row**

**Your detailed analysis process for each chord:**
- **Identify the chord name** from the label above the diagram
- **Examine each string (left to right, strings 6 through 1):**
  - Look above the nut: O = open (0), X = muted (-1)
  - Look for markers: count which fret space they occupy
  - If no marker and no O/X, assume open (0)
- **Double-check your work:** Re-examine the diagram and verify each position
- **Create detailed description:** Describe exactly what you see

**Your process for each chord:**
1. Spot the chord name (Em9, C7/G, etc.)
2. Go string by string from left to right (strings 6-1)
3. For each string: check above the nut first (O or X?), then look for any dots/markers in the fret spaces
4. Tell me exactly what you see in detail - this helps me debug if something goes wrong
5. Double-check your work before moving on

**Example 1:** If you see a chord with:
- String 6: "O" above nut
- String 5: dot in the space between 2nd and 3rd horizontal lines
- String 4: dot in the space between 3rd and 4th horizontal lines
- String 3: "O" above nut
- String 2: "O" above nut
- String 1: "O" above nut

You'd report: [0, 2, 3, 0, 0, 0] and describe it like: "String 6 open, string 5 has dot in fret 2, string 4 has dot in fret 3, strings 3-1 are open"

**Example 2:** If you see:
- String 6: "X" above nut
- String 5: dot in first fret space (between nut and 2nd line)
- Strings 4,3,2,1: "O" above nut

You'd report: [-1, 1, 0, 0, 0, 0] and describe: "String 6 muted, string 5 dot at fret 1, strings 4-1 open"

Make sense? You're being my eyes here, and I really appreciate the help!

**OUTPUT FORMAT:**
```json
{
  "tuning": "DETECT_FROM_FILE",
  "capo": 0,
  "analysis": {
    "referenceChordDescriptions": [
      {
        "name": "Em9",
        "visualDescription": "DEBUG: String 6: O (open, fret 0), String 5: O (open, fret 0), String 4: O (open, fret 0), String 3: numbered circle '1' in fret space 2 (fret 2), String 2: numbered circle '4' in fret space 4 (fret 4), String 1: O (open, fret 0). Final pattern: [0,0,0,2,4,0]",
        "extractedPattern": [0, 0, 0, 2, 4, 0]
      }
    ]
  },
  "sections": [
    {
      "label": "Main",
      "chords": [
        {
          "name": "Em9",
          "frets": [0, 0, 0, 2, 4, 0],
          "sourceType": "chord_chart_direct",
          "row": 1,
          "position": 1,
          "lineBreakAfter": false
        }
      ]
    }
  ],
  "totalRows": 3
}
```

**A couple more things that really help me out:**
- Please include that detailed visualDescription for each chord - it's like showing your work in math class, and it helps me figure out if something went wrong
- If you see something confusing or contradictory, just tell me about it - I'd rather know you're uncertain than guess wrong
- Remember the frets array goes [string 6, string 5, string 4, string 3, string 2, string 1] (low to high pitch)
- Use -1 for muted (X), 0 for open (O), and 1, 2, 3, etc. for fretted positions

**One last technical note:** Please set lineBreakAfter: true for chords at the end of lines/phrases, and return only the JSON format shown above (no extra explanatory text). Thanks!

Thanks so much for being thorough with this, you rock Claude! 🤘🎸🚀"""

        message_content = [{
            "type": "text",
            "text": prompt_text
        }]

        # Add all files for visual analysis
        for file_content in uploaded_files:
            name = file_content['name']

            # Add file label
            message_content.append({
                "type": "text",
                "text": f"\n\n**FILE: {name}**"
            })

            if file_content['type'] == 'pdf':
                message_content.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_content['data']
                    }
                })
            elif file_content['type'] == 'image':
                message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_content['media_type'],
                        "data": file_content['data']
                    }
                })

        # Use Sonnet 4.5 for visual analysis of chord diagrams
        app.logger.info("Using Sonnet 4.5 for chord chart visual analysis")
        llm_start_time = time.time()
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=6000,
            messages=[{
                "role": "user",
                "content": message_content
            }]
        )
        llm_end_time = time.time()

        response_text = response.content[0].text

        # Track LLM generation with PostHog Analytics
        from app.utils.llm_analytics import llm_analytics
        llm_analytics.track_generation(
            model="claude-sonnet-4-5-20250929",
            input_messages=[{"role": "user", "content": "Chord chart processing and analysis"}],
            output_choices=[{"message": {"content": response_text}}],
            usage={
                "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else None,
                "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else None
            },
            latency_seconds=llm_end_time - llm_start_time,
            custom_properties={
                "function": "process_chord_charts_directly",
                "file_count": len(uploaded_files),
                "analysis_type": "chord_chart_processing",
                "item_id": str(item_id)
            }
        )

        response_text = response.content[0].text

        # Parse JSON response (matching sheets version logic)
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON without markdown wrapper
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return {'error': 'Failed to parse chord chart data from analysis response'}

        try:
            chord_data = json.loads(json_str)
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON in chord chart analysis response'}

        if chord_data is None:
            return {'error': 'Failed to parse chord chart data from analysis response'}

        # Create chord charts from the structured data using sheets version logic
        created_charts = create_chord_charts_from_data(chord_data, item_id)

        # Extract filename for frontend display
        filename = uploaded_files[0]['name'] if uploaded_files else 'unknown'

        return {
            'success': True,
            'charts_created': len(created_charts),
            'analysis': f'Successfully processed chord charts',
            'uploaded_file_names': filename
        }

    except Exception as e:
        app.logger.error(f"Failed to process chord charts: {str(e)}")
        return {'error': f'Failed to process chord charts: {str(e)}'}

def create_chord_charts_from_data(chord_data, item_id):
    """Create chord charts from parsed data using the data layer (adapted from sheets version)"""
    try:
        from app.data_layer import DataLayer
        data_layer = DataLayer()

        created_charts = []

        # Extract tuning and capo from the analysis
        tuning = chord_data.get('tuning', 'EADGBE')
        capo = chord_data.get('capo', 0)

        # Log Claude's visual analysis for debugging (if present)
        try:
            if 'analysis' in chord_data:
                analysis = chord_data.get('analysis', {})
                if 'referenceChordDescriptions' in analysis:
                    app.logger.info("=== Claude's Visual Analysis of Reference Chord Diagrams ===")
                    for ref_chord in analysis['referenceChordDescriptions']:
                        app.logger.info(f"Chord: {ref_chord.get('name', 'Unknown')}")
                        app.logger.info(f"Visual Description: {ref_chord.get('visualDescription', 'No description')}")
                        app.logger.info(f"Extracted Pattern: {ref_chord.get('extractedPattern', 'No pattern')}")
                    app.logger.info("=== End Visual Analysis ===")
        except Exception as e:
            app.logger.warning(f"Error logging Claude visual analysis: {str(e)}")

        # REFERENCE-FIRST APPROACH: When reference files are present, use them directly
        reference_chord_shapes = []

        # Extract reference chord shapes in order of appearance
        if 'analysis' in chord_data:
            analysis = chord_data.get('analysis', {})
            if 'referenceChordDescriptions' in analysis:
                app.logger.info("=== REFERENCE-FIRST: Using Reference Chord Patterns Directly ===")
                for ref_chord in analysis['referenceChordDescriptions']:
                    chord_name = ref_chord.get('name', '').strip()
                    extracted_pattern = ref_chord.get('extractedPattern', [])

                    if chord_name and extracted_pattern:
                        # Clean chord name (remove capo suffix)
                        clean_name = chord_name.replace('(capoOn2)', '').replace('(capoon2)', '').strip()

                        reference_chord_data = {
                            'name': clean_name,
                            'frets': extracted_pattern,
                            'source': 'reference_diagram'
                        }

                        reference_chord_shapes.append(reference_chord_data)
                        app.logger.info(f"Reference chord #{len(reference_chord_shapes)}: {clean_name} → {extracted_pattern}")

                app.logger.info(f"✅ Loaded {len(reference_chord_shapes)} reference chords for direct use")

        # Process sections and create chord charts
        chart_order = 0
        sections = chord_data.get('sections', [])

        for section in sections:
            section_label = section.get('label', 'Main')
            section_chords = section.get('chords', [])

            for chord in section_chords:
                chord_name = chord.get('name', 'Unknown')
                chord_frets = chord.get('frets', [])

                # If no frets in chord data but we have reference shapes, try to match
                if not chord_frets and reference_chord_shapes:
                    for ref_chord in reference_chord_shapes:
                        if ref_chord['name'].lower() == chord_name.lower():
                            chord_frets = ref_chord['frets']
                            break

                # Convert frets array to CommonChords 2-element array format [string, fret]
                # CRITICAL: Frets array is left-to-right (string 6 to string 1)
                # but CommonChords uses actual string numbers (1=high E, 6=low E)
                fingers = []
                if chord_frets:
                    for string_idx, fret in enumerate(chord_frets):
                        if fret is not None and fret > 0:  # Skip muted (-1), open (0), and null strings
                            # Convert: frets[0] = string 6, frets[1] = string 5, ..., frets[5] = string 1
                            actual_string_number = 6 - string_idx  # Reverse the order
                            fingers.append([actual_string_number, fret])  # [string, fret] format like CommonChords

                # Create chord chart data
                chord_chart_data = {
                    'title': chord_name,
                    'fingers': fingers,
                    'barres': [],  # TODO: Handle barres from sheets version if needed
                    'tuning': list(tuning) if isinstance(tuning, str) else ['E', 'A', 'D', 'G', 'B', 'E'],
                    'capo': capo,
                    'section': section_label,
                    'sectionLabel': section_label,
                    'sectionRepeatCount': '1',
                    'order': chart_order
                }

                # Create the chord chart
                created_chart = data_layer.add_chord_chart(item_id, chord_chart_data)
                if created_chart:
                    created_charts.append(created_chart)
                    chart_order += 1

        app.logger.info(f"Created {len(created_charts)} chord charts from visual analysis")
        return created_charts

    except Exception as e:
        app.logger.error(f"Error creating chord charts from data: {str(e)}")
        return []


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


def process_chord_names_from_youtube_transcript(client, uploaded_files, item_id):
    """Process YouTube transcript files to extract chord names from spoken dialogue"""
    try:
        app.logger.info(f"[AUTOCREATE] process_chord_names_from_youtube_transcript called with {len(uploaded_files)} files for item {item_id}")
        app.logger.info("Processing YouTube transcript for spoken chord names")

        prompt_text = """🎸 **Hey Claude! YouTube Transcript Chord Extraction**

Hi there! This time I need your help with a YouTube video transcript - this is spoken dialogue from a guitar lesson video. So, it's just a voice-to-text version of the words spoken in the video. We're going to create chord charts for the song taught in the video.

**Examples of what you're looking for:**
- Chord names mentioned in spoken dialogue (like "play a G chord", "then go to C", "Am7 sounds great here")
- References to chord progressions ("G to C to D", "the verse goes Am, F, C, G")
- Song sections mentioned in speech ("in the chorus we play...", "for the bridge use...")
- Spoken chord sequences ("so it's G, C, Am, F throughout")

**What to IGNORE:**
- Music theory discussions without specific chord names
- General guitar technique talk
- References to fret positions without chord names
- Equipment or setup discussions

**Your job:**
- Listen for actual chord names mentioned in the dialogue
- Group them by song sections, if mentioned (e.g. Intro, Verse, Chorus, Bridge, etc.)
- Keep the chord charts in the order they're to be played in the song

**OUTPUT FORMAT:**
```json
{
  "tuning": "EADGBE",
  "capo": 0,
  "sections": [
    {
      "label": "Verse",
      "chords": [
        {
          "name": "G",
          "sourceType": "chord_names",
          "lineBreakAfter": false
        },
        {
          "name": "C",
          "sourceType": "chord_names",
          "lineBreakAfter": true
        }
      ]
    }
  ]
}
```

Key difference from lyrics sheets: Here you're reading a transcript of spoken words about chords, from a teaching video. This differs from reading chord symbols positioned above lyrics, but the output is to be similar.

Important: If no chord names are actually mentioned in the transcript, respond with: "No chord names found in this transcript." (The scenario here will be video lessons of lead guitar lines, which would be about playing specific notes, instead of chords.)

Thanks for helping me extract chord progressions from this voice-to-text transcript of a guitar lesson video from youtube!"""

        message_content = [{
            "type": "text",
            "text": prompt_text
        }]

        # Add all uploaded files
        for file_content in uploaded_files:
            name = file_content['name']
            message_content.append({
                "type": "text",
                "text": f"\n\n**FILE: {name}**"
            })

            if file_content['type'] == 'pdf':
                message_content.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_content['data']
                    }
                })
            elif file_content['type'] == 'image':
                message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_content['media_type'],
                        "data": file_content['data']
                    }
                })
            elif file_content['type'] == 'chord_names':
                # Handle text files including YouTube transcripts
                message_content.append({
                    "type": "text",
                    "text": file_content['data']
                })

        # Use Sonnet 4 for chord names analysis (cost-efficient)
        app.logger.info(f"[AUTOCREATE] Using Sonnet 4 for YouTube transcript chord analysis")
        app.logger.info(f"[AUTOCREATE] Making API call with {len(message_content)} content items")
        app.logger.info(f"[AUTOCREATE] Message content types: {[item.get('type', 'unknown') for item in message_content]}")

        try:
            app.logger.info(f"[AUTOCREATE] Starting Anthropic API call to claude-sonnet-4-5-20250929")
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8000,  # Increased for complex songs with multiple sections
                temperature=0.1,
                messages=[{"role": "user", "content": message_content}]
            )
            app.logger.info(f"[AUTOCREATE] API call successful, response received with {len(response.content)} content items")
            if response.content:
                app.logger.info(f"[AUTOCREATE] Response content length: {len(response.content[0].text) if response.content[0].text else 0} characters")
        except Exception as api_error:
            app.logger.error(f"[AUTOCREATE] API call failed: {str(api_error)}")
            app.logger.error(f"[AUTOCREATE] API error type: {type(api_error)}")
            return {'error': f'Claude API call failed: {str(api_error)}'}

        # Parse Claude's response
        response_text = response.content[0].text.strip()
        app.logger.info(f"[AUTOCREATE] Parsing Claude response for YouTube transcript chord names")
        app.logger.info(f"[AUTOCREATE] Claude response preview: {response_text[:500]}...")

        if not response_text:
            app.logger.error("Empty response from Claude API")
            return {'error': 'Empty response from Claude API'}

        # Try to extract JSON from response (might be wrapped in markdown)
        try:
            # Look for JSON block in markdown
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
                app.logger.info(f"[AUTOCREATE] Found JSON in markdown, attempting to parse {len(json_text)} chars")
                chord_data = json.loads(json_text)
                app.logger.info(f"[AUTOCREATE] Successfully parsed JSON from markdown!")
            else:
                # Try to parse the entire response as JSON
                app.logger.info(f"[AUTOCREATE] No markdown wrapper found, trying direct JSON parse")
                chord_data = json.loads(response_text)
                app.logger.info(f"[AUTOCREATE] Successfully parsed response as direct JSON!")
        except json.JSONDecodeError as parse_error:
            app.logger.error(f"[AUTOCREATE] JSON parsing failed: {str(parse_error)}")
            app.logger.error(f"[AUTOCREATE] Failed response text: {response_text}")

            # Try to extract a clean JSON block if markdown parsing failed
            if '```json' in response_text:
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    try:
                        clean_json = json_match.group(1)
                        app.logger.info(f"[AUTOCREATE] Found JSON in markdown, attempting to parse {len(clean_json)} chars")
                        chord_data = json.loads(clean_json)
                        app.logger.info(f"[AUTOCREATE] Successfully parsed JSON from markdown!")
                    except json.JSONDecodeError as clean_parse_error:
                        app.logger.error(f"[AUTOCREATE] Even markdown-extracted JSON failed to parse: {clean_parse_error}")
                        return {'error': f'Failed to parse chord chart data - JSON truncated or malformed. Error: {str(parse_error)}'}
            else:
                app.logger.error(f"[AUTOCREATE] No markdown JSON blocks found in response")
                # Check if Claude's response indicates no chords were found
                if any(phrase in response_text.lower() for phrase in [
                    'no chord names', 'no chords', 'doesn\'t contain chord',
                    'if you have the actual chord', 'share that and i\'ll be happy',
                    'chord chart or lyrics sheet', 'no chord symbols',
                    'no chord names found in this transcript'
                ]):
                    return {'error': 'No chord names found in this transcript. This appears to be a guitar lesson or discussion about the song rather than lyrics with chord symbols above them. Please try a different video or upload a file with chord names above lyrics.'}
                else:
                    return {'error': f'Failed to parse chord chart data from analysis response: {str(parse_error)}'}

        # Create chord charts from the structured data using CommonChords lookup
        created_charts = create_chord_charts_from_data(chord_data, item_id)

        # Extract filename for frontend display
        filename = uploaded_files[0]['name'] if uploaded_files else 'unknown'

        return {
            'success': True,
            'message': f'Successfully created {len(created_charts)} chord charts from YouTube transcript',
            'chord_count': len(created_charts),
            'content_type': 'youtube_transcript',
            'uploaded_file_names': filename
        }

    except Exception as e:
        app.logger.error(f"Error processing YouTube transcript chord names: {str(e)}")
        return {'error': f'Failed to process YouTube transcript: {str(e)}'}



def process_chord_names_with_lyrics(client, uploaded_files, item_id):
    """Process files with chord names above lyrics using CommonChords lookup"""
    try:
        app.logger.info(f"[AUTOCREATE] process_chord_names_with_lyrics called with {len(uploaded_files)} files for item {item_id}")
        app.logger.info("Processing chord names above lyrics with CommonChords lookup")

        # POWER OPTIMIZATION: Try OCR extraction first for PDFs and images
        file_data = uploaded_files[0]  # Process single file
        if file_data.get('type') in ['pdf', 'image']:
            app.logger.info(f"[AUTOCREATE] Attempting OCR extraction for {file_data.get('type')} file: {file_data.get('name')}")

            try:
                from app.utils.chord_ocr import extract_chords_from_file, should_use_ocr_result

                # Extract chords using OCR
                if file_data.get('type') == 'pdf':
                    import base64
                    pdf_bytes = base64.b64decode(file_data['data'])
                    ocr_result = extract_chords_from_file(pdf_bytes, 'pdf', file_data['name'])
                elif file_data.get('type') == 'image':
                    ocr_result = extract_chords_from_file(file_data['data'], 'image', file_data['name'])

                # Check if OCR found enough chords to use lightweight processing
                if ocr_result and should_use_ocr_result(ocr_result, minimum_chords=2):
                    app.logger.info(f"[AUTOCREATE] 🚀 OCR SUCCESS! Found {len(ocr_result['chords'])} chords, using lightweight Sonnet processing for 80% power savings!")

                    # Log the OCR raw text for debugging
                    app.logger.info(f"[AUTOCREATE] OCR Raw Text (first 500 chars): {ocr_result['raw_text'][:500]}...")
                    app.logger.info(f"[AUTOCREATE] OCR Found Chords: {ocr_result['chords']}")

                    # Replace file content with complete OCR text to preserve sectional structure
                    file_data['data'] = ocr_result['raw_text']
                    file_data['type'] = 'chord_names'

                    app.logger.info(f"[AUTOCREATE] Feeding complete OCR text to existing Sonnet processing (preserves sections)")

                    # NEW: Assess OCR trustworthiness using Sonnet 4 intelligence
                    ocr_assessment = assess_ocr_trustworthiness(client, ocr_result['raw_text'], file_data['name'])
                    if not ocr_assessment['trustworthy']:
                        app.logger.info(f"[AUTOCREATE] OCR contains gibberish ({ocr_assessment['reason']}), falling back to visual analysis")
                        # Fall back to Opus 4.1 visual analysis for complex layouts
                        return process_chord_charts_directly(client, uploaded_files, item_id)

                    app.logger.info(f"[AUTOCREATE] OCR text assessed as trustworthy, proceeding with Sonnet processing")
                    # Continue to existing Sonnet processing below (no return here)

                else:
                    chords_found = len(ocr_result.get('chords', [])) if ocr_result else 0
                    app.logger.info(f"[AUTOCREATE] OCR found {chords_found} chords (need 2+), falling back to LLM processing")

            except Exception as e:
                app.logger.warning(f"[AUTOCREATE] OCR extraction failed: {str(e)}, falling back to LLM processing")

        else:
            app.logger.info(f"[AUTOCREATE] Text file detected, skipping OCR and using LLM processing")

        prompt_text = """🎸 **Hey Claude! Chord Names from Lyrics Processing**

Hi there! This time I need your help with a different type of file - these are lyrics sheets with chord names written above the words (like "G" or "Am" or "F7" above the lyrics), NOT chord diagrams with dots and lines.

**What you're looking for:**
- Chord symbols like G, C, Am, F, D7, etc. positioned above lyrics
- Song sections marked like [Verse], [Chorus], [Bridge], [Intro], etc.
- The order that chords appear within each section
- Sometimes there might be repeat markers like "x2" or chord timing

**Your job:**
- Extract all the chord names exactly as written (don't "correct" them)
- Group them by song sections
- Keep them in the order they appear
- Preserve the song structure the songwriter intended

**OUTPUT FORMAT:**
```json
{
  "tuning": "EADGBE",
  "capo": 0,
  "sections": [
    {
      "label": "Verse",
      "chords": [
        {
          "name": "G",
          "sourceType": "chord_names",
          "lineBreakAfter": false
        },
        {
          "name": "C",
          "sourceType": "chord_names",
          "lineBreakAfter": true
        }
      ]
    }
  ]
}
```

**Key difference from chord diagrams:** Here you're just reading text/chord symbols, not analyzing visual finger positions. So if you see "Am7" written above some lyrics, just extract "Am7" - don't worry about what frets that chord uses.

**A few helpful tips:**
- Sometimes chords repeat in a progression like "G - C - G - C" - capture each occurrence
- Watch for timing info like "Em (hold)" or "F x4"
- Section names can vary: Verse, Verse 1, Chorus, Bridge, Outro, etc.
- If you're not sure which section a chord belongs to, your best guess is fine
- Use EXACT chord names from document (G, C, Am, F7, etc.)
- Preserve section structure and progression order

Thanks for helping me extract these chord progressions! This saves me tons of time.

**One last technical note:** Please set lineBreakAfter: true for chords at the end of lines/phrases, and return only the JSON format shown above (no extra explanatory text). Thanks!"""

        message_content = [{
            "type": "text",
            "text": prompt_text
        }]

        # Add all uploaded files
        for file_content in uploaded_files:
            name = file_content['name']
            message_content.append({
                "type": "text",
                "text": f"\n\n**FILE: {name}**"
            })

            if file_content['type'] == 'pdf':
                message_content.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_content['data']
                    }
                })
            elif file_content['type'] == 'image':
                message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_content['media_type'],
                        "data": file_content['data']
                    }
                })
            elif file_content['type'] == 'chord_names':
                # Handle text files including YouTube transcripts
                message_content.append({
                    "type": "text",
                    "text": file_content['data']
                })

        # Use Sonnet 4 for chord names analysis (cost-efficient)
        app.logger.info(f"[AUTOCREATE] Using Sonnet 4 for chord names analysis")
        app.logger.info(f"[AUTOCREATE] Making API call with {len(message_content)} content items")
        app.logger.info(f"[AUTOCREATE] Message content types: {[item.get('type', 'unknown') for item in message_content]}")

        try:
            app.logger.info(f"[AUTOCREATE] Starting Anthropic API call to claude-sonnet-4-5-20250929")
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8000,  # Increased for complex songs with multiple sections
                temperature=0.1,
                messages=[{"role": "user", "content": message_content}]
            )
            app.logger.info(f"[AUTOCREATE] API call successful, response received with {len(response.content)} content items")
            if response.content:
                app.logger.info(f"[AUTOCREATE] Response content length: {len(response.content[0].text) if response.content[0].text else 0} characters")
        except Exception as api_error:
            app.logger.error(f"[AUTOCREATE] API call failed: {str(api_error)}")
            app.logger.error(f"[AUTOCREATE] API error type: {type(api_error)}")
            return {'error': f'Claude API call failed: {str(api_error)}'}

        # Parse Claude's response
        response_text = response.content[0].text.strip()
        app.logger.info(f"[AUTOCREATE] Parsing Claude response for chord names")
        app.logger.info(f"[AUTOCREATE] Claude response preview: {response_text[:500]}...")

        if not response_text:
            app.logger.error("Empty response from Claude API")
            return {'error': 'Empty response from Claude API'}

        # Try to extract JSON from response (might be wrapped in markdown)
        try:
            # Look for JSON block in markdown
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text

            chord_data = json.loads(json_text)
        except json.JSONDecodeError as parse_error:
            app.logger.error(f"[AUTOCREATE] Failed to parse JSON response: {parse_error}")
            app.logger.error(f"[AUTOCREATE] Parse error location: line {getattr(parse_error, 'lineno', 'unknown')} column {getattr(parse_error, 'colno', 'unknown')}")
            app.logger.error(f"[AUTOCREATE] Response length: {len(response_text)} characters")
            app.logger.error(f"[AUTOCREATE] Response preview (first 1000 chars): {response_text[:1000]}")
            app.logger.error(f"[AUTOCREATE] Response end (last 500 chars): {response_text[-500:]}")

            # Try to extract JSON from markdown code blocks if present
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    clean_json = json_match.group(1)
                    app.logger.info(f"[AUTOCREATE] Found JSON in markdown, attempting to parse {len(clean_json)} chars")
                    chord_data = json.loads(clean_json)
                    app.logger.info(f"[AUTOCREATE] Successfully parsed JSON from markdown!")
                except json.JSONDecodeError as clean_parse_error:
                    app.logger.error(f"[AUTOCREATE] Even markdown-extracted JSON failed to parse: {clean_parse_error}")
                    return {'error': f'Failed to parse chord chart data - JSON truncated or malformed. Error: {str(parse_error)}'}
            else:
                app.logger.error(f"[AUTOCREATE] No markdown JSON blocks found in response")
                # Check if Claude's response indicates no chords were found
                if any(phrase in response_text.lower() for phrase in [
                    'no chord names', 'no chords', 'doesn\'t contain chord',
                    'if you have the actual chord', 'share that and i\'ll be happy',
                    'chord chart or lyrics sheet', 'no chord symbols'
                ]):
                    return {'error': 'No chord names found in this transcript. This appears to be a guitar lesson or discussion about the song rather than lyrics with chord symbols above them. Please try a different video or upload a file with chord names above lyrics.'}
                else:
                    return {'error': f'Failed to parse chord chart data from analysis response: {str(parse_error)}'}

        # Create chord charts from the structured data using CommonChords lookup
        created_charts = create_chord_charts_from_data(chord_data, item_id)

        # Extract filename for frontend display
        filename = uploaded_files[0]['name'] if uploaded_files else 'unknown'

        return {
            'success': True,
            'message': f'Imported {len(created_charts)} chord charts',
            'charts': created_charts,
            'analysis': chord_data,
            'uploaded_file_names': filename
        }

    except Exception as e:
        app.logger.error(f"Error processing chord names: {str(e)}")
        return {'error': f'Failed to process chord names: {str(e)}'}


def create_chord_charts_from_data(chord_data, item_id):
    """Create chord charts from parsed chord data using batch operations"""
    try:
        created_charts = []

        # Extract tuning and capo from the analysis
        tuning = chord_data.get('tuning', 'EADGBE')
        capo = chord_data.get('capo', 0)

        # Pre-load all common chords efficiently to reduce API calls
        try:
            app.logger.info(f"[AUTOCREATE] Starting CommonChords lookup - getting all common chords efficiently")
            all_common_chords = data_layer.get_common_chords_efficiently()
            app.logger.info(f"[AUTOCREATE] Successfully loaded {len(all_common_chords)} common chords for autocreate")
        except Exception as e:
            app.logger.error(f"[AUTOCREATE] Failed to load common chords: {str(e)}")
            app.logger.error(f"[AUTOCREATE] CommonChords error type: {type(e)}")
            all_common_chords = []

        # Log Claude's visual analysis for debugging
        try:
            if 'analysis' in chord_data:
                analysis = chord_data.get('analysis', {})
                if 'referenceChordDescriptions' in analysis:
                    app.logger.info("=== Claude's Visual Analysis of Reference Chord Diagrams ===")
                    for ref_chord in analysis['referenceChordDescriptions']:
                        app.logger.info(f"Chord: {ref_chord.get('name', 'Unknown')}")
                        app.logger.info(f"Visual Description: {ref_chord.get('visualDescription', 'No description')}")
                        app.logger.info(f"Extracted Pattern: {ref_chord.get('extractedPattern', 'No pattern')}")
                        # Add position marker debugging info if present in description
                        description = ref_chord.get('visualDescription', '')
                        if 'fr' in description.lower():
                            app.logger.info(f"🎯 Position marker detected in description: {description}")
                    app.logger.info("=== End Visual Analysis ===")
                else:
                    app.logger.info("No reference chord descriptions found in analysis")
            else:
                app.logger.info("No analysis field found in Claude response (using older prompt format)")
        except Exception as e:
            app.logger.warning(f"Error logging Claude visual analysis: {str(e)}")

        # REFERENCE-FIRST APPROACH: When reference files are present, use them directly
        reference_chord_shapes = []  # Reference chord shapes in order of appearance
        reference_chord_by_name = {}  # Map: chord_name -> reference_chord_data

        # Extract reference chord shapes in order of appearance
        if 'analysis' in chord_data:
            analysis = chord_data.get('analysis', {})
            if 'referenceChordDescriptions' in analysis:
                app.logger.info("=== REFERENCE-FIRST: Using Reference Chord Patterns Directly ===")
                for ref_chord in analysis['referenceChordDescriptions']:
                    chord_name = ref_chord.get('name', '').strip()
                    extracted_pattern = ref_chord.get('extractedPattern', [])

                    if chord_name and extracted_pattern:
                        # Clean chord name (remove capo suffix)
                        clean_name = chord_name.replace('(capoOn2)', '').replace('(capoon2)', '').strip()

                        reference_chord_data = {
                            'name': clean_name,
                            'frets': extracted_pattern,
                            'source': 'reference_diagram'
                        }

                        reference_chord_shapes.append(reference_chord_data)
                        # Also create name-based lookup for intelligent matching
                        reference_chord_by_name[clean_name.lower()] = reference_chord_data

                        app.logger.info(f"Reference chord #{len(reference_chord_shapes)}: {clean_name} → {extracted_pattern}")

                app.logger.info(f"✅ Loaded {len(reference_chord_shapes)} reference chords for direct use")
            else:
                app.logger.info("No reference chord descriptions found - will use chord names approach")
        else:
            app.logger.info("No analysis field found - will use chord names approach")

        # When no reference chords, we'll fall back to CommonChords lookup for chord names
        if not reference_chord_shapes:
            app.logger.info("=== NO REFERENCE DIAGRAMS: Will use CommonChords lookup for chord names ===")

        # Collect all chord charts to create in one batch
        all_chord_charts = []
        chart_order = 0

        # INTELLIGENT MISMATCH HANDLING: When reference has more chords than chord data
        if reference_chord_shapes:
            app.logger.info("=== INTELLIGENT REFERENCE-CHORD DATA INTEGRATION ===")

            # Count chords in chord data sections
            total_chord_instances = sum(len(section.get('chords', [])) for section in chord_data.get('sections', []))
            app.logger.info(f"Chord data has {total_chord_instances} chord instances across all sections")
            app.logger.info(f"Reference file has {len(reference_chord_shapes)} unique chord shapes")

            if len(reference_chord_shapes) > total_chord_instances:
                app.logger.info(f"📊 MISMATCH DETECTED: Reference file contains MORE chords than chord data")
                app.logger.info(f"📊 SOLUTION: Will include ALL reference chords, organized by chord data structure")

                # Add extra reference chords to the last section to ensure they're all included
                sections = chord_data.get('sections', [])
                if sections:
                    last_section = sections[-1]
                    existing_chord_names = {chord.get('name', '').lower() for section in sections for chord in section.get('chords', [])}

                    # Add any reference chords not found in chord data to the last section
                    for ref_chord in reference_chord_shapes:
                        ref_name = ref_chord['name'].lower()
                        if ref_name not in existing_chord_names:
                            app.logger.info(f"🔍 Adding missing reference chord to last section: {ref_chord['name']}")
                            last_section.setdefault('chords', []).append({
                                'name': ref_chord['name'],
                                'frets': ref_chord['frets'],
                                'sourceType': 'reference_only'
                            })

        # Use sections as provided by Claude analysis (preserve section structure)
        sections = chord_data.get('sections', [])
        if not sections:
            sections = [{'label': 'Chords', 'chords': []}]

        for section in sections:
            section_label = section.get('label', 'Chords')
            section_repeat = section.get('repeatCount', '')

            # Generate a unique section ID
            import time
            section_id = f"section-{int(time.time() * 1000)}"

            for chord in section.get('chords', []):
                chord_name = chord.get('name', 'Unknown')
                chord_frets = chord.get('frets', [])
                chord_fingers = chord.get('fingers', [])
                source_type = chord.get('sourceType', 'chord_names')  # Default to chord_names if not specified
                line_break_after = chord.get('lineBreakAfter', False)  # Get lineBreakAfter from Claude response

                # REFERENCE-FIRST APPROACH: Check for reference chord by name
                reference_match = None
                if reference_chord_shapes and chord_name.lower() != 'unknown':
                    reference_match = reference_chord_by_name.get(chord_name.lower())

                    if reference_match:
                        # Use reference chord shape and name directly
                        original_chord_data = f"{chord_name}: {chord_frets}" if chord_frets else f"{chord_name}: no frets"
                        chord_frets = reference_match['frets']
                        chord_name = reference_match['name']
                        source_type = 'reference_direct'
                        app.logger.info(f"✅ REFERENCE-FIRST: {original_chord_data} → {chord_name} {chord_frets}")
                    else:
                        app.logger.debug(f"No reference match found for chord name '{chord_name}'")

                # Simplified processing: reference patterns or direct chord data
                use_reference_pattern = (source_type in ['reference', 'reference_direct', 'reference_only'] and chord_frets)
                use_direct_pattern = (source_type == 'chord_names' and chord_frets and tuning != 'EADGBE')

                if use_reference_pattern:
                    app.logger.info(f"✅ Using reference diagram: {chord_name} = {chord_frets} in {tuning}")
                elif use_direct_pattern:
                    app.logger.info(f"✅ Using direct chord pattern: {chord_name} = {chord_frets} in {tuning}")

                # Find the chord in pre-loaded common chords (case-insensitive)
                common_chord = None
                chord_name_lower = chord_name.lower()

                # Only lookup in CommonChords for standard tuning when not using direct patterns
                is_standard_tuning = tuning.upper() in ['EADGBE', 'STANDARD']
                if not (use_reference_pattern or use_direct_pattern):
                    if not is_standard_tuning:
                        app.logger.warning(f"⚠️  FALLBACK: Skipping CommonChords lookup for alternate tuning: {tuning}. CommonChords only contains EADGBE patterns.")
                    elif chord_name_lower != 'unknown':
                        for common in all_common_chords:
                            if common.get('title', '').lower() == chord_name_lower:
                                common_chord = common
                                app.logger.info(f"📚 FALLBACK: Found {chord_name} in pre-loaded CommonChords by name")
                                break

                    # If not found by name and we have fret data, try to find by fret pattern (standard tuning only)
                    if not common_chord and chord_frets and is_standard_tuning:
                        # Try to match fret pattern in CommonChords (for transposed patterns)
                        for common in all_common_chords:
                            common_frets = common.get('frets', [])
                            if common_frets == chord_frets:
                                common_chord = common
                                chord_name = common.get('title', chord_name)  # Use the chord name from CommonChords
                                app.logger.info(f"📚 FALLBACK: Found chord by fret pattern match: {chord_name}")
                                break

                # Create chord chart data (unified processing for reference patterns or direct patterns)
                if use_reference_pattern or use_direct_pattern:
                    frets = chord_frets

                    # Build SVGuitar-compatible data from chord pattern
                    open_strings = []
                    muted_strings = []
                    svguitar_fingers = []

                    if frets:
                        for i, fret_val in enumerate(frets):
                            # Convert AI array format to SVGuitar format
                            # AI: [low E, A, D, G, B, high E] → SVGuitar: string 1=high E, string 6=low E
                            string_num = 6 - i
                            if fret_val == 0:
                                open_strings.append(string_num)
                            elif fret_val == -1:
                                muted_strings.append(string_num)
                            elif fret_val > 0:
                                svguitar_fingers.append([string_num, fret_val])  # No finger numbers - leave to user

                    # 🔧 SVGuitar Debug Logging (Reference Pattern Path)
                    app.logger.info(f"🔧 SVGuitar Conversion Debug for {chord_name} (Reference Pattern):")
                    app.logger.info(f"   Input frets: {frets}")
                    app.logger.info(f"   SVGuitar fingers: {svguitar_fingers}")
                    app.logger.info(f"   Open strings: {open_strings}")
                    app.logger.info(f"   Muted strings: {muted_strings}")
                    app.logger.info(f"   Tuning: {tuning}")

                    chord_chart_data = {
                        'title': chord_name,
                        'chord_data': {
                            'tuning': tuning,
                            'capo': capo,
                            'numFrets': 5,
                            'numStrings': len(frets) if frets else 6,
                            'fingers': svguitar_fingers,
                            'barres': [],
                            'openStrings': open_strings,
                            'mutedStrings': muted_strings,
                            'sectionId': section_id,
                            'sectionLabel': section_label,
                            'sectionRepeatCount': section_repeat,
                            'lineBreakAfter': line_break_after
                        },
                        'order': chart_order
                    }

                    source_desc = "reference diagram" if use_reference_pattern else "chord pattern"
                    app.logger.info(f"✅ Created chord chart from {source_desc}: {chord_name} = {frets} in {tuning}")

                elif common_chord:
                    # Use the chord from CommonChords (standard tuning path)
                    # Filter fingers to only include fretted positions (fret > 0) to prevent blank chord displays
                    raw_fingers = common_chord.get('fingers', [])
                    filtered_fingers = []
                    if raw_fingers:
                        for finger in raw_fingers:
                            if isinstance(finger, list) and len(finger) >= 2 and finger[1] > 0:
                                filtered_fingers.append(finger)

                    chord_chart_data = {
                        'title': chord_name,
                        'chord_data': {
                            'tuning': common_chord.get('tuning', tuning),
                            'capo': common_chord.get('capo', capo),
                            'startingFret': common_chord.get('startingFret', 1),
                            'numFrets': common_chord.get('numFrets', 5),
                            'numStrings': common_chord.get('numStrings', 6),
                            'fingers': filtered_fingers,
                            'frets': common_chord.get('frets', []),
                            'barres': common_chord.get('barres', []),
                            'openStrings': common_chord.get('openStrings', []),
                            'mutedStrings': common_chord.get('mutedStrings', []),
                            'sectionId': section_id,
                            'sectionLabel': section_label,
                            'sectionRepeatCount': section_repeat,
                            'lineBreakAfter': line_break_after
                        },
                        'order': chart_order
                    }
                else:
                    # Fallback: use raw data from Claude/chord analysis (chord not found in CommonChords)
                    # Prioritize fret data from chord analysis over generic fallback
                    frets = chord_frets if chord_frets else chord.get('frets', [])
                    fingers = chord_fingers if chord_fingers else chord.get('fingers', [])
                    starting_fret = chord.get('startingFret', 1)

                    # Calculate starting fret from fret pattern if not specified
                    if frets and starting_fret == 1:
                        non_zero_frets = [f for f in frets if f > 0]
                        if non_zero_frets:
                            starting_fret = min(non_zero_frets)

                    # Convert frets to SVGuitar fingers format if fingers are empty but frets exist
                    svguitar_fingers = fingers if fingers else []
                    open_strings = []
                    muted_strings = []

                    if frets and not svguitar_fingers:
                        app.logger.info(f"Converting frets to SVGuitar format for {chord_name}: {frets}")
                        for i, fret_val in enumerate(frets):
                            # Fix string numbering: AI arrays are [low E, A, D, G, B, high E] (index 0-5)
                            # SVGuitar expects: string 1=high E, string 6=low E
                            string_num = 6 - i  # Convert: index 0 (low E) → SVGuitar string 6
                                                 #          index 5 (high E) → SVGuitar string 1
                            if fret_val == 0:
                                open_strings.append(string_num)
                            elif fret_val == -1:  # Sometimes muted strings are marked as -1
                                muted_strings.append(string_num)
                            elif fret_val > 0:  # Fretted note
                                svguitar_fingers.append([string_num, fret_val])  # No finger numbers - leave to user

                    # 🔧 SVGuitar Debug Logging (Fallback Pattern Path)
                    app.logger.info(f"🔧 SVGuitar Conversion Debug for {chord_name} (Fallback Pattern):")
                    app.logger.info(f"   Input frets: {frets}")
                    app.logger.info(f"   SVGuitar fingers: {svguitar_fingers}")
                    app.logger.info(f"   Open strings: {open_strings}")
                    app.logger.info(f"   Muted strings: {muted_strings}")
                    app.logger.info(f"   Tuning: {tuning}")

                    chord_chart_data = {
                        'title': chord_name,
                        'chord_data': {
                            'tuning': tuning,
                            'capo': capo,
                            'numFrets': 5,  # Default to 5 frets
                            'numStrings': len(frets) if frets else 6,
                            'fingers': svguitar_fingers,  # Use converted SVGuitar format
                            'openStrings': open_strings,   # Derive from fret pattern
                            'mutedStrings': muted_strings, # Derive from fret pattern
                            'frets': frets,
                            'barres': [],  # Could be enhanced to detect barres
                            'sectionId': section_id,
                            'sectionLabel': section_label,
                            'sectionRepeatCount': section_repeat,
                            'lineBreakAfter': line_break_after
                        },
                        'order': chart_order
                    }

                    app.logger.debug(f"Using chord fret data for {chord_name}: frets={frets}, fingers={fingers}")

                # Include the order in the chord data itself
                all_chord_charts.append((chord_name, section_label, chord_chart_data))
                chart_order += 1

        # Batch create all chord charts in one API call
        if all_chord_charts:
            chord_data_list = [chart_data for _, _, chart_data in all_chord_charts]

            app.logger.info(f"[AUTOCREATE] Batch creating {len(chord_data_list)} chord charts for item {item_id}")
            app.logger.info(f"[AUTOCREATE] Starting batch_add_chord_charts API call")

            try:
                batch_results = data_layer.batch_add_chord_charts(item_id, chord_data_list)
                app.logger.info(f"[AUTOCREATE] Batch creation completed, got {len(batch_results)} results")
            except Exception as batch_error:
                app.logger.error(f"[AUTOCREATE] Batch creation failed: {str(batch_error)}")
                app.logger.error(f"[AUTOCREATE] Batch error type: {type(batch_error)}")
                raise

            # Build response with chord names and sections
            for (chord_name, section_label, _), result in zip(all_chord_charts, batch_results):
                created_charts.append({
                    'name': chord_name,
                    'section': section_label,
                    'id': result.get('id') if result else None
                })

        return created_charts

    except Exception as e:
        app.logger.error(f"Error creating chord charts: {str(e)}")
        raise

def assess_ocr_trustworthiness(client, ocr_text, filename):
    """
    Use Sonnet 4 to intelligently assess if OCR text contains too much gibberish.
    Returns dict with 'trustworthy' bool and 'reason' string.
    """
    try:
        app.logger.info(f"[AUTOCREATE] Assessing OCR trustworthiness for {filename}")

        assessment_prompt = f"""**OCR Trustworthiness Assessment**

I need you to assess whether this OCR-extracted text is trustworthy for chord chart processing, or if it contains too much gibberish to trust.

**Your Task:**
Look for OCR artifacts and gibberish strings that indicate corrupted data, such as:
- Random isolated characters mixed with symbols (like "oD t=" or "G =¥i")
- Fragmented text with unusual symbol combinations
- Text that looks like OCR recognition errors rather than real content

**OCR Text to Assess:**
```
{ocr_text[:1000]}{'...' if len(ocr_text) > 1000 else ''}
```

**Response Format:**
Respond with ONLY one of these two options:

TRUSTWORTHY - if the text appears clean and usable despite minor OCR imperfections
CORRUPTED - if there are significant gibberish patterns that indicate unreliable data

**Important:** Be conservative - if you see clear gibberish artifacts, mark as CORRUPTED even if some parts look good."""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=100,  # Short response needed
            temperature=0.1,
            messages=[{"role": "user", "content": assessment_prompt}]
        )

        assessment_result = response.content[0].text.strip().upper()

        if "TRUSTWORTHY" in assessment_result:
            app.logger.info(f"[AUTOCREATE] OCR assessment: TRUSTWORTHY")
            return {'trustworthy': True, 'reason': 'Sonnet assessed OCR text as clean and usable'}
        elif "CORRUPTED" in assessment_result:
            app.logger.info(f"[AUTOCREATE] OCR assessment: CORRUPTED")
            return {'trustworthy': False, 'reason': 'Sonnet detected gibberish patterns in OCR text'}
        else:
            # Default to untrusted if unclear response
            app.logger.warning(f"[AUTOCREATE] OCR assessment unclear: {assessment_result}, defaulting to untrusted")
            return {'trustworthy': False, 'reason': 'OCR assessment response unclear, being conservative'}

    except Exception as e:
        app.logger.error(f"[AUTOCREATE] OCR trustworthiness assessment failed: {str(e)}")
        # Default to untrusted on error - better safe than sorry
        return {'trustworthy': False, 'reason': f'Assessment error: {str(e)}'}