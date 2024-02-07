import csv
import logging
import os
import time
from datetime import datetime, timedelta
from config import KEY, SECRET, ADVERTISER_ID
import traceback
import aiohttp
from aiohttp import ClientSession, TCPConnector
import asyncio
from asyncio import Lock
from aiolimiter import AsyncLimiter
import ssl  # Import the ssl module
import inspect
import sys


rate_limiter = AsyncLimiter(10, 1)  # 20 requests per second

# Your credentials and access token
key = KEY
secret = SECRET
access_token = None
token_expiration_time = None

# API URLs
auth_url = "https://api.autotrader.co.uk/authenticate"
vehicles_api_url = "https://api.autotrader.co.uk/vehicles"
valuations_api_url = "https://api.autotrader.co.uk/valuations"
metrics_api_url = "https://api.autotrader.co.uk/vehicle-metrics"
stock_api_url = "https://api.autotrader.co.uk/stock"

# Just set the directory paths to the ones in your PythonAnywhere environment
input_dir = 'uploaded_files/'  # Directory for input CSV
output_dir = 'output_files/'  # Directory for output CSV

# Configure logging
log_dir = os.path.join('/home/tomdrayson/mysite/logs', datetime.now().strftime("%Y%m%d"))
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, f'bulk_retail_check_{datetime.now().strftime("%Y%m%d_%H%M")}.log')

class CustomFormatter(logging.Formatter):
    def format(self, record):
        record.extra_vrm = getattr(record, 'extra_vrm', 'N/A')
        return super().format(record)


formatter = CustomFormatter('%(asctime)s - VRM: %(extra_vrm)s - %(levelname)s - %(message)s')

# Create a logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a file handler and set formatter
handler = logging.FileHandler(log_file_path)
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

# Add a simple logging statement for debugging
logger.info("Script started")


# Create SSL context without using set_info_callback
ssl_context = ssl.create_default_context()
ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

def count_rows(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Assuming it's a CSV file
            reader = csv.reader(file)
            row_count = sum(1 for row in reader)
            return row_count
    except Exception as e:
        logging.error(f"Error counting rows in file {file_path}: {e}")
        raise

# Custom logging function for aiohttp requests and responses
async def log_request_info(session, trace_config_ctx, params):
    logging.info(f"Sending request to {params.url} with method {params.method}")

async def log_response_info(session, trace_config_ctx, params):
    logging.info(f"Received response with status {params.response.status}")

# Function to create a session with logging
async def create_async_session():
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        connector = TCPConnector(ssl=ssl_context)
        session = ClientSession(connector=connector)
        return session
    except ssl.SSLError as ssl_error:
        logging.error("SSL Error during session creation: %s", ssl_error)
        raise
    except Exception as e:
        logging.error("Error creating aiohttp session: %s", e)
        raise

# Global session for aiohttp
async def get_session():
    timeout = aiohttp.ClientTimeout(total=60)
    return aiohttp.ClientSession(timeout=timeout)

# Global lock for token refresh
token_refresh_lock = Lock()

async def authenticate(session):
    global access_token, token_expiration_time, token_refresh_lock

    logging.info(f"Attempting to acquire lock in event loop: {id(asyncio.get_event_loop())}")
    async with token_refresh_lock:
        logging.info(f"Lock acquired in event loop: {id(asyncio.get_event_loop())}")
        if is_token_valid():
            return

        logging.info("Refreshing access token...")  # Add this line
        try:
            # Replace with your actual authentication request logic
            async with session.post(auth_url, data={'key': key, 'secret': secret}) as response:
                if response.status == 200:
                    auth_data = await response.json()
                    access_token = auth_data.get('access_token')

                    # Update the expiration time. Adjust this according to the actual token's expiration logic
                    expires_in = auth_data.get('expires_in', 900)  # Defaulting to 15 minutes if not provided
                    token_expiration_time = datetime.utcnow() + timedelta(seconds=expires_in)
                else:
                    logging.error(f'Authentication failed with status code: {response.status}')
                    # Handle failed authentication appropriately
                    raise Exception(f'Authentication failed with status code: {response.status}')
        except Exception as e:
            logging.error(f'Error during authentication: {e}')
            raise

def is_token_valid():
    global access_token, token_expiration_time
    if access_token and token_expiration_time:
        current_time = datetime.utcnow()  # Using UTC time for consistency
        return current_time < token_expiration_time
    return False

# Function to log API responses with detailed error information
def log_api_response(api_name, vrm, response, error_only=False, response_body=None):
    if response is not None and response.status != 200 and response_body:
        logging.error(f'{api_name} API call for VRM {vrm} failed with status code: {response.status} and response body: {response_body}', extra={'extra_vrm': vrm})
    elif response is not None and not error_only:
        logging.info(f'{api_name} API call for VRM {vrm} succeeded with status code: {response.status}', extra={'extra_vrm': vrm})



def concatenate_description(make, model, derivative):
    make = make if make is not None else ''
    model = model if model is not None else ''
    derivative = derivative if derivative is not None else ''
    description = ' '.join(part for part in [make, model, derivative] if part)
    return description  # Return a string, not a tuple

# Function to process a single row
async def process_row(session, args):
    global rate_limiter, access_token  # Include access_token
    index, row, total_rows = args
    start_time = time.time()
    vrm = row['VRM']
    mileage = row.get('Mileage', '')

    # Initialize all variables to default values
    first_registration_date = ''
    make = ''
    model = ''
    derivative = ''
    derivative_id = ''
    market_condition = ''
    rating = ''
    original_days_to_sell = ''
    valuations_retail_valuation = ''
    total_results = 'N/A'
    description = ''
    factory_fitted_features = []
    factory_fitted_feature_names = []

    if not is_token_valid():
        await authenticate(session)

    try:
        headers = {'Authorization': f'Bearer {access_token}'}

        # Vehicles API call
        vehicles_params = {
            'advertiserId': ADVERTISER_ID,
            'registration': vrm,
            'valuations': 'true',
            'vehicleMetrics': 'true',
            'odometerReadingMiles': mileage,
            'includeFirstRegistrationDate': 'true',
            'competitors': 'true',
            'features': 'true'
        }

        async with rate_limiter:
            async with session.get(vehicles_api_url, params=vehicles_params, headers=headers, timeout=10) as vehicles_response:
                if vehicles_response.status == 429:
                    logging.error(f'Rate limit exceeded for Vehicles API call for VRM {vrm}', extra={'extra_vrm': vrm})
                    # Optionally, schedule a retry after a delay or handle this error appropriately
                    return
                elif vehicles_response.status == 200:
                    vehicles_data = await vehicles_response.json()
                    vehicle_info = vehicles_data.get('vehicle', {})
                    vehicle_metrics = vehicles_data.get('vehicleMetrics', {}).get('retail', {})
                    make = vehicle_info.get('make', '')
                    model = vehicle_info.get('model', '')
                    derivative = vehicle_info.get('derivative', '')
                    derivative_id = vehicle_info.get('derivativeId', '')
                    first_registration_date = vehicle_info.get('firstRegistrationDate', '')
                    market_condition = vehicle_metrics.get('marketCondition', {}).get('value', '')
                    rating = vehicle_metrics.get('rating', {}).get('value', '')
                    original_days_to_sell = vehicle_metrics.get('daysToSell', {}).get('value', '')
                    description = concatenate_description(make, model, derivative)

                    # Extract features and filter by factoryFitted == true
                    factory_fitted_features = []
                    factory_fitted_feature_names = []

                    # Ensure vehicles_data is a dictionary and features_data is a list
                    if isinstance(vehicles_data, dict):
                        features_data = vehicles_data.get('features', [])

                        if isinstance(features_data, list):
                            for feature in features_data:
                                # Check if feature is a dictionary
                                if isinstance(feature, dict):
                                    factory_fitted = feature.get('factoryFitted')
                                    feature_name = feature.get('name')

                                    if factory_fitted is True and feature_name:
                                        factory_fitted_feature_names.append(feature_name.strip())
                                        factory_fitted_features.append({"name": feature_name.strip()})
                else:
                    response_text = await vehicles_response.text()
                    logging.error(f"Vehicles API call for VRM {vrm} failed with status {vehicles_response.status} and response: {response_text}", extra={'extra_vrm': vrm})
                    logging.error(f'Expected vehicles_data to be a dictionary, but found {type(vehicles_data)} for VRM {vrm}', extra={'extra_vrm': vrm})

        # Valuations API call
        valuations_url = f"{valuations_api_url}?advertiserId={ADVERTISER_ID}"
        valuations_payload = {
            "vehicle": {
                "derivativeId": derivative_id,
                "firstRegistrationDate": first_registration_date,
                "odometerReadingMiles": mileage,
            },
            "features": factory_fitted_features  # Use factory-fitted features here
        }

        async with rate_limiter:
            async with session.post(valuations_url, json=valuations_payload, headers=headers, timeout=10) as valuations_response:
                if valuations_response.status == 200:
                    valuations_data = await valuations_response.json()
                    # Use VRM in logging
                    logging.info(f"Type of valuations_data: {type(valuations_data)}", extra={'extra_vrm': vrm})
                    logging.info(f"Content of valuations_data: {valuations_data}", extra={'extra_vrm': vrm})
                    valuations_retail_valuation = valuations_data.get('valuations', {}).get('retail', {}).get('amountGBP', 'N/A')
                    logging.info(f"Valuations_data for VRM {vrm}: {valuations_data}", extra={'extra_vrm': vrm})  # Add this line
                else:
                    log_api_response('Valuations', vrm, valuations_response, error_only=True, response_body=await valuations_response.text())

        # Extract competitor link
        competitor_link = vehicles_data.get('links', {}).get('competitors', {}).get('href', 'N/A')

        # Check if competitor link is available
        if competitor_link != 'N/A':
            if 'advertiserId=' not in competitor_link:
                competitor_link = f"{competitor_link}&advertiserId={ADVERTISER_ID}" if '?' in competitor_link else f"{competitor_link}?advertiserId={ADVERTISER_ID}"

            if 'advertiserType=' not in competitor_link:
                competitor_link += '&advertiserType=Trade'

            if '!insuranceWriteoffCategory=' not in competitor_link:
                competitor_link += '&!insuranceWriteoffCategory='

            async with session.get(competitor_link, headers=headers) as stock_response:
                if stock_response.status == 200:
                    stock_response_json = await stock_response.json()
                    total_results = stock_response_json.get('totalResults', 'N/A')

    except aiohttp.ClientConnectorSSLError as ssl_error:
        current_line = inspect.currentframe().f_lineno
        logging.error(f'SSL Error when accessing {valuations_url} for VRM {vrm}: {ssl_error} (Line {current_line})', extra={'extra_vrm': vrm})
        return  # Return to avoid further processing
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = {
            'filename': exc_traceback.tb_frame.f_code.co_filename,
            'lineno': exc_traceback.tb_lineno,
            'name': exc_traceback.tb_frame.f_code.co_name,
            'type': exc_type.__name__,
            'message': str(e)
        }

        if "list' object has no attribute 'get'" in str(e):
            # Log the error message, the row, and the line number
            logging.error(f'Error processing row with VRM {vrm}, Row: {row}: {exc_value} (Line {traceback_details["lineno"]})')
            logging.error(f'Row Data: {row}', extra={'extra_vrm': vrm})
            # Log the traceback to capture the line of code
            logging.error(traceback.format_exc())
        else:
            # Log other exceptions with VRM, row, and traceback
            logging.error(f'Exception processing row with VRM {vrm}, Row: {row}: {e} (Line {traceback_details["lineno"]})\n{traceback.format_exc()}', extra={'extra_vrm': vrm})
        return  # Return to avoid further processing

    end_time = time.time()
    processing_time = end_time - start_time

    return {
        'index': index,
        'data': [
            description,  # Vehicle description
            vrm,  # Vehicle registration mark
            mileage,  # Vehicle mileage
            valuations_retail_valuation,  # Retail valuation from the Valuations API
            rating,  # Rating from the Vehicles API
            original_days_to_sell,  # Days to sell from the Vehicles API
            market_condition,  # Market condition from the Vehicles API
            total_results,  # Total results from competitor analysis
            ', '.join(factory_fitted_feature_names)  # Comma-separated list of factory-fitted features
        ],
        'message': f'Processing row {index + 1} of {total_rows} - VRM: {vrm}',
        'time': processing_time
    }



async def process_all_rows(rows):
    async with await create_async_session() as session:
        tasks = [process_row(session, (index, row, len(rows))) for index, row in enumerate(rows)]
        return await asyncio.gather(*tasks)


def write_to_csv(results, output_csv_path):
    with open(output_csv_path, 'w', newline='') as output_csv_file:
        writer = csv.writer(output_csv_file)
        writer.writerow(['Description', 'VRM', 'Mileage', 'Retail Valuation', 'Rating', 'Days to sell', 'Market Condition', 'National Competitors', 'Factory Fitted Features'])
        for result in results:
            writer.writerow(result['data'])

def process_uploaded_file(input_file_path, output_base_dir):
    try:
        # Generate a unique filename with a timestamp
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")
        output_csv_filename = f'Vehicles_API_Output_{current_datetime}.csv'
        output_csv_path = os.path.join(output_base_dir, output_csv_filename)

        with open(input_file_path, 'r') as input_csv_file:
            csv_reader = csv.DictReader(input_csv_file)
            rows = list(csv_reader)

        # Process all rows asynchronously and gather results
        results = asyncio.run(process_all_rows(rows))

        # The total count of processed rows is the length of the results list
        total_rows_processed = len(results)

        # Here you can include logic to handle or aggregate data from 'results' if needed

        write_to_csv(results, output_csv_path)

        return output_csv_filename, total_rows_processed
    except Exception as e:
        # Handle exceptions and possibly log them
        print(f"An error occurred in process_uploaded_file: {e}")
        raise