from flask import Flask, render_template, request, send_from_directory, session, abort
from werkzeug.utils import secure_filename
import os
import uuid
from mot_check_blueprint import mot_check_bp
from cap_vrm_blueprint import cap_vrm_bp
import logging
from logging.handlers import RotatingFileHandler

# Configuration
UPLOAD_FOLDER = '/home/tomdrayson/mysite/uploaded_files'
OUTPUT_FOLDER = '/home/tomdrayson/mysite/output_files'
LOG_FOLDER = '/home/tomdrayson/mysite/logs'
SECRET_KEY = 'your-secure-random-secret-key'  # Change this to a secure random key

# Ensure essential directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

# Initialize Flask app
app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=SECRET_KEY,
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    OUTPUT_FOLDER=OUTPUT_FOLDER
)

# Register blueprints
app.register_blueprint(mot_check_bp, url_prefix='/mot_check')
app.register_blueprint(cap_vrm_bp, url_prefix='/cap_vrm')

# After request - Set permissions policy
@app.after_request
def set_permissions_policy(response):
    response.headers['Permissions-Policy'] = 'interest-cohort=()'
    return response

# Index route
@app.route('/')
def index():
    session['user_id'] = session.get('user_id', str(uuid.uuid4()))
    return render_template('index.html')

@app.route('/mot_check')
def mot_check_route():
    return render_template('mot_check.html')

@app.route('/cap_vrm')
def cap_vrm_route():
    return render_template('cap_vrm.html')


# Download route
@app.route('/download/<filename>')
def download(filename):
    safe_filename = secure_filename(filename)
    try:
        return send_from_directory(app.config['OUTPUT_FOLDER'], safe_filename, as_attachment=True)
    except FileNotFoundError:
        app.logger.error(f'File {safe_filename} not found in output directory.')
        return abort(404, description='File not found')

# Logging
if not app.debug:
    file_handler = RotatingFileHandler(os.path.join(LOG_FOLDER, 'flask_app.log'), maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

if __name__ == '__main__':
    app.logger.info('Flask app startup')
    app.run(host='0.0.0.0', port=8080)
