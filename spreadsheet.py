import gspread
from datetime import datetime, timedelta
import re, requests
import geopy
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from oauth2client.service_account import ServiceAccountCredentials
from trello import TrelloApi

from postcodes import *

requests = {
    'Shopping': 'Picking up shopping and medications',
    'Prescription': 'Picking up shopping and medications',
    'Energy Top-up': 'Topping up electric or gas keys',
    'Post': 'Posting letters',
    'Phone Call': 'A friendly telephone call',
    'Dog Walk': 'Dog walking'
}


def get_nearest_volunteers(vol_names, vol_locs, vol_requests, location, request_type):

    distances = distance_between(location, vol_locs)
    closest_vols = np.argsort(distances)

    potential_vols = []
    for x in closest_vols:
        if requests[request_type] in vol_requests[x]:
            potential_vols.append(x)
        if len(potential_vols) == 5:
            break

    print(f'Closest volunteers are {[vol_names[x] for x in potential_vols]} who are at {[vol_locs[x] for x in potential_vols]} and are {[distances[x] for x in potential_vols]} away')
    return potential_vols


if __name__ == "__main__":
    # use creds to create a client to interact with the Google Drive API
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    client = gspread.authorize(creds)

    trello = TrelloApi('96ea110307fae0a88aad529ed8f29423',
        #api_secret='a39b184a567529d192651db11a9e993b01724434bc793aaa1b7ab7cba66bf5a1',
        'b9c9b53acc2f7de0972a217366742f905ee7bb7670662e1aa6897df4fd8cfc23')
        #token_secret='your-oauth-token-secret'
    #)

    lists = trello.boards.get_list('KKkfsmg9')

    create_trello = True

    # Find list id
    list_id = None
    for list in lists:
        if list['name'] == 'Requestee Needing Volunteer':
            list_id = list['id']
            break
    if list_id is None:
        raise RuntimeError('Column not found')

    geolocator = Nominatim(user_agent="FindNearestAddr", timeout=1000)
    pc_pattern = re.compile('([wW][dD]3) *([0-9][a-zA-Z]+)')
    #geopy.geocoders.options.default_timeout = 1000

    # Find a workbook by name and open the first sheet
    # Make sure you use the right name here.
    vol_sheet = client.open_by_key("1QfBAkcEi1Sc0dm-coOcP5ewEw_c2qDzasF24pN7Yqcc").sheet1
    #requests_sheet = client.open_by_key("1MTxkW3g-AZSn651E-brruYadG9sllr0EOwdC6CDdFy4").sheet1 # test sheet
    requests_sheet = client.open_by_key("19JrA8_PK_N6SBTy1KO5cmRFCK1TNKtFqpB4eyKOrJuU").sheet1 # real sheet

    # Extract and print all of the volunteer postcodes
    vol_names = vol_sheet.col_values(2)[1:]
    vol_addresses = vol_sheet.col_values(5)[1:]
    vol_requests = vol_sheet.col_values(6)[1:]

    postcodes = []
    pc_exists = []
    for idx, vol in enumerate(vol_addresses):
        result = pc_pattern.search(vol)
        if result is not None:
            pc = f'{result.group(1).upper()} {result.group(2).upper()}'
            postcodes.append(pc)
            pc_exists.append(idx)

    positions, bads = postcodes_data(postcodes)
    if plot_locations:
        if len(bads) > 0:
            print(f'Warning: bad postcodes entered, {bads}, not printed on volunteer distribution')
        plot_locations(positions.longitude, positions.latitude, jitter=30,
                       save_file='volunteer-distribution.pdf', zoom=15)

    vol_locs = [(lng, lat) for lat, lng in zip(positions.latitude, positions.longitude)]
    vol_names = [vol_names[x] for x in pc_exists]
    vol_requests = [vol_requests[x] for x in pc_exists]

    request_pcs = requests_sheet.col_values(4)
    request_names = requests_sheet.col_values(1)
    request_tasks = requests_sheet.col_values(6)
    request_status = requests_sheet.col_values(14)

    for idx, request in enumerate(request_pcs[1:]):
        if request_status[idx+1] == 'TRUE':
            print(f'Skipping request because request completed')
            continue
        # Get postcode and lat/long of request
        location = geolocator.geocode(request)
        request_loc = (location.longitude, location.latitude)

        print(f'Find closest volunteer for {request_names[idx+1]} at {request_loc} '
              'with request type {request_tasks[idx+1]}')

        vols = get_nearest_volunteers(vol_names, vol_locs, vol_requests,
                                      request_loc, request_tasks[idx+1])

        for j, vol in enumerate(vols):
            requests_sheet.update_cell(idx+2, j+8, vol_names[vol])

        if create_trello:
            # Add trello card for this request
            due_date = datetime.now() + timedelta(7)
            trello.lists.new_card(list_id, request_names[idx+1], due_date.isoformat())

        requests_sheet.update_cell(idx+2, 14, 'TRUE')
