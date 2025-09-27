#!/usr/bin/env python3
"""
Web Frontend for Newegg Scraper
Provides dashboard, data viewing, and CSV upload functionality
"""

import os
import sys
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.database.database import DatabaseHandler
from utils.csv_processor import CSVProcessor
from config import settings

app = Flask(__name__)
app.secret_key = 'newegg_scraper_secret_key_2024'

# Configuration from settings
UPLOAD_FOLDER = settings.UPLOAD_DIR
ALLOWED_EXTENSIONS = {'csv'}
DATABASE_PATH = settings.DATABASE_PATH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database handler
db = DatabaseHandler(DATABASE_PATH)
csv_processor = CSVProcessor(DATABASE_PATH)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def dashboard():
    """Main dashboard showing statistics and overview"""
    try:
        stats = db.get_session_statistics()

        # Get recent sessions
        recent_sessions = db.get_recent_sessions(limit=10)

        # Get product count
        product_count = db.get_product_count()

        return render_template('dashboard.html',
                             stats=stats,
                             recent_sessions=recent_sessions,
                             product_count=product_count)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html',
                             stats={},
                             recent_sessions=[],
                             product_count=0)

@app.route('/products')
def products():
    """View all products"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    try:
        products_data = db.get_products_paginated(page=page, per_page=per_page)
        return render_template('products.html',
                             products=products_data['products'],
                             pagination=products_data['pagination'])
    except Exception as e:
        flash(f'Error loading products: {str(e)}', 'error')
        return render_template('products.html', products=[], pagination={})

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """View individual product details with reviews"""
    try:
        product = db.get_product_by_id(product_id)
        reviews = db.get_reviews_by_product_id(product_id, limit=1000)  # Show up to 1000 reviews
        return render_template('product_detail.html',
                             product=product,
                             reviews=reviews)
    except Exception as e:
        flash(f'Error loading product details: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/sessions')
def sessions():
    """View all scraping sessions"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    try:
        sessions_data = db.get_sessions_paginated(page=page, per_page=per_page)
        return render_template('sessions.html',
                             sessions=sessions_data['sessions'],
                             pagination=sessions_data['pagination'])
    except Exception as e:
        flash(f'Error loading sessions: {str(e)}', 'error')
        return render_template('sessions.html', sessions=[], pagination={})

@app.route('/upload', methods=['GET', 'POST'])
def upload_csv():
    """CSV upload and processing"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)

            try:
                file.save(filepath)

                # Process the CSV file
                result = csv_processor.process_csv_file(filepath)

                if result['success']:
                    flash(f'CSV processed successfully! {result["sessions_created"]} sessions created.', 'success')
                else:
                    flash(f'CSV processing failed: {result["error"]}', 'error')

            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')

            return redirect(url_for('upload_csv'))
        else:
            flash('Only CSV files are allowed', 'error')

    return render_template('upload.html')

@app.route('/api/stats')
def api_stats():
    """API endpoint for real-time statistics"""
    try:
        stats = db.get_session_statistics()
        product_count = db.get_product_count()

        return jsonify({
            'success': True,
            'stats': stats,
            'product_count': product_count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/recent_activity')
def api_recent_activity():
    """API endpoint for recent activity"""
    try:
        recent_sessions = db.get_recent_sessions(limit=5)
        return jsonify({
            'success': True,
            'recent_sessions': recent_sessions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    # Create templates directory and basic templates if they don't exist
    os.makedirs('templates', exist_ok=True)

    app.run(host='0.0.0.0', port=8000, debug=True)