import requests
import csv
import codecs
from datetime import datetime

# Define your API key
api_key = "otJr5He60QFkb8077Ho58ajIn3wASTU54xjQWThh"

# Define the API endpoint URL
base_url = "https://beta.check-mot.service.gov.uk/trade/vehicles/mot-tests"

# Define the headers for the HTTP request
headers = {
    "Content-type": "application/json",
    "x-api-key": api_key
}

def get_mot_data(registration):
    url = f"{base_url}?registration={registration}"
    response = requests.get(url, headers=headers)
    # Consider handling errors and logging here
    if response.status_code == 200:
        return response.json()
    return None

def convert_date_format(date_str):
    try:
        date_format = "%Y.%m.%d %H:%M:%S" if " " in date_str else "%Y.%m.%d"
        date_obj = datetime.strptime(date_str, date_format)
        return date_obj.strftime("%d/%m/%Y")
    except ValueError:
        return ""

def process_mot_checks(vrm_list, output_csv_path, progress_callback=None):
    header = ["Registration", "Most Recent MOT Test Date", "Most Recent MOT Expiry Date", "MOT Mileage"]

    with open(output_csv_path, 'w', newline='') as output_file:
        output_csv = csv.writer(output_file)
        # Write the header for the output CSV
        output_csv.writerow(header)

        total_rows = len(vrm_list)
        processed_rows = 0
        start_time = datetime.now()  # Record the start time for ETA calculation

        for registration in vrm_list:
            registration = registration.strip()  # Trim whitespace
            mot_data = get_mot_data(registration)

            if mot_data and mot_data[0].get("motTests"):
                most_recent_test = mot_data[0]["motTests"][0]
                completed_date = convert_date_format(most_recent_test.get("completedDate", ""))
                expiry_date = convert_date_format(most_recent_test.get("expiryDate", ""))
                odometer_value = most_recent_test.get("odometerValue", "")
                output_csv.writerow([registration, completed_date, expiry_date, odometer_value])
            else:
                output_csv.writerow([registration, "", "", ""])

            processed_rows += 1
            if progress_callback:
                elapsed_time = datetime.now() - start_time
                average_time_per_row = elapsed_time / processed_rows
                estimated_time_remaining = average_time_per_row * (total_rows - processed_rows)
                progress = (processed_rows / total_rows) * 100
                progress_callback(progress, processed_rows, total_rows, estimated_time_remaining)


# Example usage of the progress_callback
def update_progress(progress, processed_rows, total_rows, estimated_time_remaining):
    print(f"Progress: {progress:.2f}%")
    print(f"Processed Rows: {processed_rows}/{total_rows}")
    print(f"ETA to completion: {estimated_time_remaining}")

# Replace this with your actual input and output file paths
input_file_path = "/home/tomdrayson/mysite/uploaded_files/MOT_Input.csv"
output_file_path = "/home/tomdrayson/mysite/output_files/MOT_Output.csv"


# Call process_mot_checks with the progress_callback
process_mot_checks(input_file_path, output_file_path, progress_callback=update_progress)
