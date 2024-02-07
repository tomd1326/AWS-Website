from flask import Flask, render_template, request, send_from_directory, session, jsonify
from werkzeug.utils import secure_filename
import os
import bulk_retail_check
import logging
import uuid

app = Flask(__name__)
app.secret_key = 'tom'

UPLOAD_FOLDER = '/home/tomdrayson/mysite/uploaded_files'
OUTPUT_FOLDER = '/home/tomdrayson/mysite/output_files'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.after_request
def set_permissions_policy(response):
    response.headers['Permissions-Policy'] = 'attribution-reporting=(), run-ad-auction=(), join-ad-interest-group=(), idle-detection=(), browsing-topics=()'
    return response

@app.route('/')
def index():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/bulk_retail_check')
def bulk_retail_check_route():
    return render_template('bulk_retail_check.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('uploaded_file')
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        session['file_path'] = filepath
        row_count = bulk_retail_check.count_rows(filepath)  # Implement this function
        file_size = os.path.getsize(filepath)

        return jsonify({'rowCount': row_count, 'fileSize': file_size})
    else:
        return jsonify({'error': 'No file selected'}), 400


@app.route('/process', methods=['POST'])
def process_file():
    if 'file_path' in session:
        try:
            filepath = session['file_path']
            output_file_name, _ = bulk_retail_check.process_uploaded_file(filepath, app.config['OUTPUT_FOLDER'])
            # Clear the file path from the session after processing
            session.pop('file_path', None)
            return jsonify({
                'outputFileName': output_file_name  # Change to camelCase to match JavaScript
            })
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            # Clear the file path from the session in case of an error as well
            session.pop('file_path', None)
            return jsonify({'error': f"An error occurred: {e}"}), 500
    else:
        return jsonify({'error': 'No file to process'}), 400


@app.route('/download')
def download():
    output_file_name = request.args.get('output_file_name')
    if output_file_name:
        return send_from_directory(app.config['OUTPUT_FOLDER'], output_file_name, as_attachment=True)
    return 'No file to download', 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
