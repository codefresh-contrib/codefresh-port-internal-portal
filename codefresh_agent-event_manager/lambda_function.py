# file: lambda_function.py
# lambda entrypoint: lambda_handler


import base64
import os
import logging
import jsonpickle
import json
import requests
import traceback
import urllib.parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CLIENT_ID = os.environ['PORT_CLIENT_ID']
CLIENT_SECRET = os.environ['PORT_CLIENT_SECRET']
CODEFRESH_API_KEY = os.environ['CODEFRESH_API_KEY']

# Constants and default values
PORT_API_URL = 'https://api.getport.io/v1'
CODEFRESH_URL = 'https://g.codefresh.io'
CODEFRESH_API_URL = f'{CODEFRESH_URL}/api'
PORT_RUN_STATUSES = {
    "success": "SUCCESS",
    "failure": "FAILURE",
    "in_progress": "IN_PROGRESS"
}


def convert_status_code_to_run_status(status_code: int):
    if 200 <= status_code < 300:
        return "SUCCESS"
    if status_code >= 300:
        return "FAILURE"
    return "IN_PROGRESS"


def convert_build_id_to_run_status(build_id):
    # This needs to be improved. There should be a pattern to determine a correct build ID
    if 23 <= len(str(build_id)) <= 25:
        return PORT_RUN_STATUSES['in_progress']
    if "error" in str(build_id).lower():
        return PORT_RUN_STATUSES['failure']
    return PORT_RUN_STATUSES['in_progress']


def get_port_api_token():
    '''
    Get a Port API access token

    This function uses a global ``CLIENT_ID`` and ``CLIENT_SECRET``
    '''
    credentials = {'clientId': CLIENT_ID, 'clientSecret': CLIENT_SECRET}

    token_response = requests.post(
        f'{PORT_API_URL}/auth/access_token', json=credentials)
    access_token = token_response.json()['accessToken']

    return access_token


def report_action_status(run_id: str, status: str):
    '''
    Reports to Port on the status of an action run
    '''
    logger.info('Fetching token')
    token = get_port_api_token()

    headers = {
        'Authorization': f'Bearer {token}'
    }

    body = {
        "status": status,
        "message": {
            "message": f"The action status is {status}"
        }
    }

    logger.info(f'Reporting action {run_id} status:')
    logger.info(json.dumps(body))
    response = requests.patch(
        f'{PORT_API_URL}/actions/runs/{run_id}', json=body, headers=headers)
    logger.info(response.status_code)
    logger.info(json.dumps(response.json()))

    return response.status_code


def report_action_links(run_id: str, links):
    '''
    Reports to Port on the Links of an action run
    '''
    logger.info('Fetching token')
    token = get_port_api_token()

    headers = {
        'Authorization': f'Bearer {token}'
    }

    body = {
        "link": links
    }

    logger.info(f'Reporting action {run_id} status:')
    logger.info(json.dumps(body))
    response = requests.patch(
        f'{PORT_API_URL}/actions/runs/{run_id}', json=body, headers=headers)
    logger.info(response.status_code)
    logger.info(json.dumps(response.json()))

    return response.status_code


def run_codefresh_pipeline(pipeline_name: str, payload):
    '''
    Runs a Pipeline in Codefresh
    '''

    headers = {
        'Authorization': f'{CODEFRESH_API_KEY}'
    }

    body = {

        "variables": [
            {
                "key": "port_payload",
                "value": json.dumps(payload)
            }
        ]
    }

    logger.info(
        f'Running Pipeline "{pipeline_name}" with the following options:')
    logger.info(f'Body: {json.dumps(body)}')
    encoded_pipeline_name = urllib.parse.quote(pipeline_name, safe='')
    response = requests.post(
        f'{CODEFRESH_API_URL}/pipelines/run/{encoded_pipeline_name}', json=body, headers=headers)
    build_id = str(response.json())

    logger.info(f'Status code: "{response.status_code}"')
    logger.info(f'Build ID: "{build_id}"')

    return build_id


def lambda_handler(event, context):
    '''
    Receives an event from AWS, if configured with a Kafka Trigger, the event includes an array of base64 encoded messages from the different topic partitions
    '''
    logger.info('## ENVIRONMENT VARIABLES\r' +
                jsonpickle.encode(dict(**os.environ)))
    logger.info('## EVENT\r' + jsonpickle.encode(event))
    logger.info('## CONTEXT\r' + jsonpickle.encode(context))
    for messages in event['records'].values():
        for encoded_message in messages:
            try:
                message_json_string = base64.b64decode(
                    encoded_message['value']).decode('utf-8')
                logger.info('Received message:')
                logger.info(message_json_string)
                message = json.loads(message_json_string)
                run_id = message['context']['runId']
                # The pipeline to execute will come from the cf_pipeline property of the Action in Port
                # It needs to match an existing CF pipeline ID or Pipeline Full Name. E.g., '64ed0bc7c64d3336272d6c51' or 'my_project/my_pipeline'
                pipeline_id = message['payload']['properties']['cf_pipeline']
                build_id = run_codefresh_pipeline(pipeline_id, message)
                links = [f'{CODEFRESH_URL}/build/{build_id}']
                report_action_links(run_id, links)

                run_status_from_build_id = convert_build_id_to_run_status(
                    build_id)
                logger.info(
                    f'Run status based on resulting Build Id ({build_id}): {run_status_from_build_id}')

                # Only report run status from this lambda, if the pipeline invocation failed.
                # Otherwise, the executed pipeline should be in charge of reporting the run status to Port
                if run_status_from_build_id == PORT_RUN_STATUSES['failure']:
                    report_action_status(run_id, run_status_from_build_id)
            except Exception as e:
                traceback.print_exc()
                logger.warn(f'Error: {e}')
    return {"message": "ok"}


if __name__ == "__main__":
    pass
