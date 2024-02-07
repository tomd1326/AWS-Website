from flask import Blueprint, request, jsonify, send_from_directory, current_app, session, render_template
from werkzeug.utils import secure_filename
import os
import cap_vrm  # Import your cap_vrm module
import csv
from datetime import datetime

cap_vrm_bp = Blueprint('cap_vrm', __name__)

UPLOAD_FOLDER = '/home/tomdrayson/mysite/uploaded_files'
OUTPUT_FOLDER = '/home/tomdrayson/mysite/output_files'

@cap_vrm_bp.route('/')
def cap_vrm_index():
    return render_template('cap_vrm.html')

@cap_vrm_bp.route('/upload_cap_vrm', methods=['POST'])
def upload_cap_vrm_file():
    try:
        file = request.files['file']
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            session['cap_vrm_file_path'] = filepath  # Store the file path in the session

            # Count rows, excluding the header
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                row_count = sum(1 for row in reader) - 1  # Subtract 1 for the header

            session['total_rows'] = row_count  # Store total row count in session
            session['processed_rows'] = 0  # Initialize processed rows

            return jsonify({'rowCount': max(row_count, 0)})  # Ensuring row count is non-negative
        else:
            return jsonify({'error': 'No file uploaded'}), 400
    except Exception as e:
        current_app.logger.error(f'Error during upload: {e}')
        return jsonify({'error': str(e)}), 500

@cap_vrm_bp.route('/process_cap_vrm', methods=['POST'])
def process_cap_vrm():
    try:
        # Create a unique filename for the output based on the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_filename = f'CAP_VRM_Output_{timestamp}.csv'
        output_filepath = os.path.join(OUTPUT_FOLDER, output_filename)

        # Retrieve input file path from the session
        input_file_path = session.get('cap_vrm_file_path')
        if not input_file_path:
            raise FileNotFoundError('No input file path found in session.')

        cap_vrm.process_file(input_file_path, output_filepath)  # Process the file

        # Store the output file path in the session
        session['output_file_name'] = output_filename  # Store just the filename

        return jsonify({'message': 'File processed successfully', 'output_filename': output_filename})
    except Exception as e:
        current_app.logger.error(f'Error during processing: {e}')
        return jsonify({'error': 'Processing failed.'}), 500

@cap_vrm_bp.route('/progress')
def progress():
    progress_info = {
        'progress': session.get('processing_progress', 0),
        'processed_rows': session.get('processed_rows', 0),
        'total_rows': session.get('total_rows', 0)
    }
    return jsonify(progress_info)

@cap_vrm_bp.route('/download_output', methods=['GET'])
def download_output():
    try:
        output_filename = session.get('output_file_name', 'CAP_VRM_Output.csv')  # Get the filename from the session
        if not output_filename:
            raise FileNotFoundError('No output file name found in session.')
        return send_from_directory(OUTPUT_FOLDER, output_filename, as_attachment=True)
    except FileNotFoundError as e:
        current_app.logger.error(f'File not found: {e}')
        return jsonify({'error': 'File not found.'}), 404
    except Exception as e:
        current_app.logger.error(f'Error during file download: {e}')
        return jsonify({'error': 'File download failed.'}), 500