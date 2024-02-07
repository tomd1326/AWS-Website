from flask import Blueprint, request, jsonify, send_from_directory, current_app, session
from werkzeug.utils import secure_filename
import os
import mot_check  # Import your mot_check module
import csv
from datetime import datetime, timedelta

mot_check_bp = Blueprint('mot_check', __name__)

UPLOAD_FOLDER = '/home/tomdrayson/mysite/uploaded_files'
OUTPUT_FOLDER = '/home/tomdrayson/mysite/output_files'

@mot_check_bp.route('/upload_mot', methods=['POST'])
def upload_mot_file():
    try:
        file = request.files['file']
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            session['mot_file_path'] = filepath  # Store the file path in the session

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

@mot_check_bp.route('/process_mot', methods=['POST'])
def process_mot():
    try:
        vrm_list = request.form.getlist('vrmList[]')  # Get VRM list from form data

        # Create a unique filename for the output based on the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_filename = f'MOT_Output_{timestamp}.csv'
        output_filepath = os.path.join(OUTPUT_FOLDER, output_filename)

        mot_check.process_mot_checks(vrm_list, output_filepath, update_progress)

        # Store the output file path in the session
        session['output_file_name'] = output_filename  # Store just the filename

        return jsonify({'message': 'File processed successfully', 'output_filename': output_filename})
    except Exception as e:
        current_app.logger.error(f'Error during processing: {e}')
        return jsonify({'error': 'Processing failed.'}), 500
    
@mot_check_bp.route('/progress')
def progress():
    progress_info = {
        'progress': session.get('processing_progress', 0),
        'processed_rows': session.get('processed_rows', 0),
        'total_rows': session.get('total_rows', 0),
        'eta': str(session.get('eta', 'Calculating...'))
    }
    return jsonify(progress_info)

def update_progress(progress, processed_rows, total_rows, eta):
    session['processing_progress'] = progress
    session['processed_rows'] = processed_rows
    session['total_rows'] = total_rows
    # Convert eta to a serializable format
    if isinstance(eta, timedelta):
        eta = eta.total_seconds()  # or str(eta) if you prefer a string representation
    session['eta'] = eta
    session.modified = True

@mot_check_bp.route('/download_output', methods=['GET'])
def download_output():
    try:
        output_filename = session.get('output_file_name', 'MOT_Output.csv')  # Get the filename from the session
        if not output_filename:
            raise FileNotFoundError('No output file name found in session.')
        return send_from_directory(OUTPUT_FOLDER, output_filename, as_attachment=True)
    except FileNotFoundError as e:
        current_app.logger.error(f'File not found: {e}')
        return jsonify({'error': 'File not found.'}), 404
    except Exception as e:
        current_app.logger.error(f'Error during file download: {e}')
        return jsonify({'error': 'File download failed.'}), 500


