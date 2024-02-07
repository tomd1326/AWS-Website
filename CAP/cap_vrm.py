import aiohttp
import asyncio
from datetime import datetime
import csv
from xml.etree import ElementTree
import os
from collections import OrderedDict
import cap_config

current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')


# CAP API info
url_monthly = 'https://soap.cap.co.uk/vrm/capvrm.asmx/VRMValuation'  # Monthly values API endpoint
url_live = 'https://soap.cap.co.uk/usedvalueslive/capusedvalueslive.asmx/GetUsedLive_IdRegDateMileage'  # Live values API endpoint
headers = {'Content-Type': 'application/x-www-form-urlencoded'}
subscriber_id = cap_config.SUBSCRIBER_ID  # Updated to use CAP_config
password = cap_config.PASSWORD         # Updated to use CAP_config


# Function to display progress in KB
def get_file_size_in_kb(file_path):
    return os.path.getsize(file_path) / 1024

def round_mileage(mileage):
    return round((int(mileage) + 500) / 1000) * 1000

async def post_cap_vrm_request(session, vrm, rounded_mileage):
    data = {
        'SubscriberID': subscriber_id,
        'Password': password,
        'VRM': vrm,
        'Mileage': rounded_mileage,
        'StandardEquipmentRequired': 'false'
    }
    async with session.post(url_monthly, headers=headers, data=data) as response:
        return await response.text(), response.status, vrm

async def post_cap_request_live_values(session, vrm, capid, registered_date, rounded_mileage):
    data = {
        'subscriberId': subscriber_id,
        'password': password,
        'database': 'CAR',
        'capid': capid,
        'valuationDate': datetime.now().strftime('%Y-%m-%d'),
        'regDate': registered_date,
        'mileage': rounded_mileage
    }
    try:
        async with session.post(url_live, data=data) as response:
            response_text = await response.text()
            return response_text
    except Exception as e:
        print(f"Error during request for VRM {vrm}: {e}")
        return None




def extract_values(response):
    root = ElementTree.fromstring(response)
    namespaces = {'ns': 'https://soap.cap.co.uk/vrm'}


    database = root.find('.//ns:VRMLookup/ns:Database', namespaces)
    capid = root.find('.//ns:VRMLookup/ns:CAPID', namespaces)
    clean = root.find('.//ns:Valuation/ns:Clean', namespaces)
    retail = root.find('.//ns:Valuation/ns:Retail', namespaces)

    capman = root.find('.//ns:VRMLookup/ns:CAPMan', namespaces)
    caprange = root.find('.//ns:VRMLookup/ns:CAPRange', namespaces)
    capmod = root.find('.//ns:VRMLookup/ns:CAPMod', namespaces)
    capder = root.find('.//ns:VRMLookup/ns:CAPDer', namespaces)

    database_text = database.text if database is not None else 'Not Found'
    capid_text = capid.text if capid is not None else 'Not Found'
    clean_text = clean.text if clean is not None else 'Not Found'
    retail_text = retail.text if retail is not None else 'Not Found'

    capman_text = capman.text if capman is not None else 'Not Found'
    caprange_text = caprange.text if caprange is not None else 'Not Found'
    capmod_text = capmod.text if capmod is not None else 'Not Found'
    capder_text = capder.text if capder is not None else 'Not Found'

    registered_date = root.find('.//ns:VRMLookup/ns:RegisteredDate', namespaces)
    if registered_date is not None and registered_date.text:
        # Parse the existing date format
        registered_date_obj = datetime.strptime(registered_date.text, '%Y-%m-%dT%H:%M:%S')
        # Format it to the desired format
        registered_date_text = registered_date_obj.strftime('%d/%m/%Y')
    else:
        registered_date_text = 'Not Found'

    # Existing return statement with the addition of registered_date_text
    return database_text, capid_text, capman_text, caprange_text, capmod_text, capder_text, clean_text, retail_text, registered_date_text

def extract_live_values(response):
    root = ElementTree.fromstring(response)
    namespaces = {'ns': 'https://soap.cap.co.uk/usedvalueslive'}

    clean_live = root.find('.//ns:ValuationDate/ns:Valuations/ns:Valuation/ns:Clean', namespaces)
    retail_live = root.find('.//ns:ValuationDate/ns:Valuations/ns:Valuation/ns:Retail', namespaces)

    clean_live_text = clean_live.text if clean_live is not None else 'Not Found'
    retail_live_text = retail_live.text if retail_live is not None else 'Not Found'

    return clean_live_text, retail_live_text


def log_error(vrm, status_code):
    log_filename = f'CAP_VRM_errors_{current_datetime}.log'
    log_file_path = os.path.join(logs_dir, log_filename)
    
    with open(log_file_path, 'a', encoding='utf-8') as error_file:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        error_file.write(f"{timestamp}: {vrm}, HTTP Status Code: {status_code}\n")

def convert_date_format(date_str):
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError:
        return None

async def process_row(session, row, index, pbar):
    try:
        # Use the round_mileage function to round the mileage
        rounded_mileage = round_mileage(row['Mileage'])

        response, status_code, vrm = await post_cap_vrm_request(session, row['VRM'], rounded_mileage)
        database, capid, capman, caprange, capmod, capder, clean, retail, registered_date = extract_values(response)

        # Convert the registered_date to the required format
        formatted_registered_date = convert_date_format(registered_date)
        if not formatted_registered_date:
            raise ValueError(f"Invalid date format for VRM {vrm}")

        live_response = await post_cap_request_live_values(session, vrm, capid, formatted_registered_date, rounded_mileage)
        live_clean, live_retail = extract_live_values(live_response)

        row_to_write = OrderedDict([
            ('VRM', row['VRM']),
            ('Unused1', ''),  # Unused column
            ('CAPMan', capman),
            ('CAPMod', capmod),
            ('CAPDer', capder),
            ('RegisteredDate', registered_date),
            ('CAPID', capid),
            ('Mileage', row['Mileage']),
            ('Unused2', ''),  # Unused column
            ('Unused3', ''),  # Unused column
            ('Unused4', ''),  # Unused column
            ('Unused5', ''),  # Unused column
            ('Unused6', ''),  # Unused column
            ('Unused7', ''),  # Unused column
            ('Unused8', ''),  # Unused column
            ('Unused9', ''),  # Unused column
            ('Monthly_Clean', clean),
            ('Unused10', ''),  # Unused column
            ('Unused11', ''),  # Unused column
            ('Monthly_Retail', retail),
            ('Unused12', ''),  # Unused column
            ('Unused13', ''),  # Unused column
            ('Unused14', ''),  # Unused column
            ('Database', database),  # Unused column
            ('Unused16', ''),  # Unused column
            ('Unused17', ''),  # Unused column
            ('Unused18', ''),  # Unused column
            ('Unused19', ''),  # Unused column
            ('Unused20', ''),  # Unused column
            ('Live_Clean', live_clean),
            ('Unused21', ''),  # Unused column
            ('Unused22', ''),  # Unused column
            ('Live_Retail', live_retail)
        ])

        if capid == 'Not Found':
            log_error(vrm, status_code)

        pbar.update(1)  # Update the progress bar here
        return index, row_to_write

    except Exception as exc:
        log_error(row['VRM'], f"Exception: {exc}")
        pbar.update(1)  # Ensure the progress bar is updated even if an exception occurs
        return index, None


    
async def process_file(input_file_path, output_directory, logs_directory, headers, subscriber_id, password):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    if not os.path.exists(logs_directory):
        os.makedirs(logs_directory)

    current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file_path = os.path.join(output_directory, f'CAP_VRM_Output_{current_datetime}.csv')

    with open(input_file_path, mode='r', newline='', encoding='utf-8-sig') as infile:
        reader = csv.DictReader(infile)
        total_rows = sum(1 for row in reader)
        infile.seek(0)

        async with aiohttp.ClientSession() as session:
            with open(output_file_path, mode='w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=[
                'VRM', 'Unused1', 'CAPMan', 'CAPMod', 'CAPDer', 'RegisteredDate', 
                'CAPID', 'Mileage', 'Unused2', 'Unused3', 'Unused4', 'Unused5', 
                'Unused6', 'Unused7', 'Unused8', 'Unused9', 'Monthly_Clean', 
                'Unused10', 'Unused11', 'Monthly_Retail', 'Unused12', 'Unused13', 
                'Unused14', 'Database', 'Unused16', 'Unused17', 'Unused18', 
                'Unused19', 'Unused20', 'Live_Clean', 'Unused21', 'Unused22', 'Live_Retail'
            ])
            writer.writeheader()

            tasks = []
            for index, row in enumerate(reader):
                task = asyncio.create_task(process_row(session, row, logs_directory, headers, subscriber_id, password))
                tasks.append(task)

    return output_file_path  # Return the path to the output file for Flask to provide a download link

if __name__ == '__main__':
    input_path = '/path/to/your/input/VRM_Input.csv'  # Update this path as necessary
    output_dir = '/home/tomdrayson/mysite/output_files'
    logs_dir = '/home/tomdrayson/mysite/logs'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    subscriber_id = cap_config.SUBSCRIBER_ID
    password = cap_config.PASSWORD
    
    asyncio.run(process_file(input_path, output_dir, logs_dir, headers, subscriber_id, password))

