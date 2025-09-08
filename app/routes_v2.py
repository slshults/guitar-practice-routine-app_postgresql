"""
Updated routes using the data layer abstraction.
Drop-in replacement for existing routes.py during migration.
"""
from flask import render_template, request, jsonify, redirect, session, url_for
from app import app
from app.data_layer import data_layer
import logging
import os

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

# Chord Charts API - Updated to use data layer  
@app.route('/api/items/<int:item_id>/chord-charts', methods=['GET', 'POST'])
def item_chord_charts(item_id):
    """Handle chord charts for an item"""
    if request.method == 'GET':
        chord_charts = data_layer.get_chord_charts_for_item(item_id)
        return jsonify(chord_charts)
        
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        chord_data = request.json
        result = data_layer.add_chord_chart(item_id, chord_data)
        return jsonify(result)

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

@app.route('/api/routines/<int:routine_id>/items', methods=['GET', 'POST'])
def routine_items(routine_id):
    """Handle routine items"""
    if request.method == 'GET':
        items = data_layer.get_routine_items(routine_id)
        return jsonify(items)
        
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        item_data = request.json
        item_id = item_data.get('item_id')
        order = item_data.get('order')
        
        if not item_id:
            return jsonify({"error": "item_id is required"}), 400
            
        result = data_layer.add_item_to_routine(routine_id, int(item_id), order)
        return jsonify(result)

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