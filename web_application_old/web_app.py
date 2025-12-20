#!/usr/bin/env python3
"""
Simple Flask web application for Pesticide Database
Run this on your EC2 instance to provide web access to the database
"""

from flask import Flask, render_template, jsonify, request
import mysql.connector
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

def get_db_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            autocommit=True
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.route('/')
def homepage():
    """Homepage"""
    return render_template('homepage.html')

@app.route('/pesticide-database')
def pesticide_database():
    """Pesticide database page"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn and conn.is_connected():
            conn.close()
            return jsonify({'status': 'healthy', 'database': 'connected'})
        else:
            return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/pesticides')
def get_pesticides():
    """Get pesticides with optional search"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(dictionary=True)
        
        # Get search parameters
        search = request.args.get('search', '')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        # Build query
        if search:
            query = """
                SELECT * FROM pesticides 
                WHERE name LIKE %s OR description LIKE %s 
                ORDER BY name
                LIMIT %s OFFSET %s
            """
            params = (f'%{search}%', f'%{search}%', limit, offset)
        else:
            query = "SELECT * FROM pesticides ORDER BY name LIMIT %s OFFSET %s"
            params = (limit, offset)
        
        cursor.execute(query, params)
        pesticides = cursor.fetchall()
        
        # Get total count
        if search:
            count_query = "SELECT COUNT(*) as total FROM pesticides WHERE name LIKE %s OR description LIKE %s"
            cursor.execute(count_query, (f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("SELECT COUNT(*) as total FROM pesticides")
        
        total = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'pesticides': pesticides,
            'total': total,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pesticides/<int:pesticide_id>')
def get_pesticide(pesticide_id):
    """Get specific pesticide by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pesticides WHERE id = %s", (pesticide_id,))
        pesticide = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if pesticide:
            return jsonify(pesticide)
        else:
            return jsonify({'error': 'Pesticide not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(dictionary=True)
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM pesticides")
        total = cursor.fetchone()['total']
        
        # Get recent additions (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as recent 
            FROM pesticides 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        recent = cursor.fetchone()['recent']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_pesticides': total,
            'recent_additions': recent
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Pesticide Database Web Server...")
    print(f"Database Host: {os.getenv('DB_HOST', 'Not set')}")
    print(f"Database Name: {os.getenv('DB_NAME', 'Not set')}")
    print("Server will be available at: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False) 