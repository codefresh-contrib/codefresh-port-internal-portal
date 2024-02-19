import logging
import json 
import requests 
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s: %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

CLIENT_ID = os.environ['PORT_CLIENT_ID']
CLIENT_SECRET = os.environ['PORT_CLIENT_SECRET']
PORT_RUN_ID = os.environ['PORT_RUN_ID']
CF_BUILD_STATUS = str(os.environ['CF_BUILD_STATUS'])
PORT_RUN_STATUS = str(os.environ.get('PORT_RUN_STATUS', ''))
PORT_RUN_SUMMARY = str(os.environ.get('PORT_RUN_SUMMARY', ''))

# Constants
PORT_RUN_RUNNING_STATUS = 'RUNNING'
PORT_RUN_SUCCESS_STATUS = 'SUCCESS'
PORT_RUN_FAILURE_STATUS = 'FAILURE'


API_URL = 'https://api.getport.io/v1'

def get_port_api_token():
    '''
    Get a Port API access token

    This function uses a global ``CLIENT_ID`` and ``CLIENT_SECRET``
    '''
    credentials = {'clientId': CLIENT_ID, 'clientSecret': CLIENT_SECRET}

    token_response = requests.post(f'{API_URL}/auth/access_token', json=credentials)
    access_token = token_response.json()['accessToken']

    return access_token

def report_action_status(run_id: str, cf_build_status: str):
    '''
    Reports to Port on the status of an action run
    '''
    cf_build_status = cf_build_status.lower()
    port_run_status = PORT_RUN_RUNNING_STATUS
    if cf_build_status.count("success") > 0:
        port_run_status = PORT_RUN_SUCCESS_STATUS
    elif cf_build_status.count("fail") > 0 or cf_build_status.count("error") > 0 :
        port_run_status = PORT_RUN_FAILURE_STATUS

    # Overwrite run status regardless of CF build status
    if PORT_RUN_STATUS != '':
        port_run_status = PORT_RUN_STATUS

    port_run_summary = PORT_RUN_SUMMARY if PORT_RUN_SUMMARY != '' else f"The action status is {port_run_status}"

    logger.info('Fetching token')
    token = get_port_api_token()

    headers = {
        'Authorization': f'Bearer {token}'
    }

    body = {
        "status": port_run_status,
        "summary": port_run_summary
    }

    logger.info(f'Reporting action {run_id} status:')
    logger.info(json.dumps(body))
    response = requests.patch(f'{API_URL}/actions/runs/{run_id}', json=body, headers=headers)
    logger.info(response.status_code)
    logger.info(json.dumps(response.json()))

    return response.status_code


if __name__ == "__main__":
    report_action_status(PORT_RUN_ID, CF_BUILD_STATUS)