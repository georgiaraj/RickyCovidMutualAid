import gspread
from datetime import datetime, timedelta
import re, requests
import geopy
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

    distances = [5000, 5000, 5000, 5000, 5000]
    closest_vols = [0, 0, 0, 0, 0]
    for idx, loc in enumerate(vol_locs):
        print(f'Check vol {vol_names[idx]} with loc {loc} and requests {vol_requests[idx]}')
        if requests[request_type] not in vol_requests[idx]:
            print(f'Skipping volunteer {vol_names[idx]} as {vol_requests[idx]}')
            continue
        dist = geodesic(loc, location)
        for j, d in enumerate(distances):
            if dist < d:
                closest_vols = closest_vols[:j] + [idx] + closest_vols[j+1:5]
                distances = distances[:j] + [dist] + distances[j+1:5]
                break

    print(f'Closest volunteers are {[vol_names[x] for x in closest_vols]} who are {distances} away')
    return closest_vols


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
    vol_names = vol_sheet.col_values(2)
    vol_addresses = vol_sheet.col_values(5)
    vol_requests = vol_sheet.col_values(6)
    vol_locs = []
    postcodes = []
    for vol in vol_addresses[1:]:
    # postcodes = []
    # json = { 'postcodes': [] }
    # for addr in addresses[1:]:
        result = pc_pattern.search(vol)
        if result is not None:
            pc = f'{result.group(1).upper()} {result.group(2).upper()}'
            postcodes.append(pc)
            # try:
        #         location = geolocator.geocode(pc)
        #         vol_locs.append((location.latitude, location.longitude))
        #     except:
        #         vol_locs.append(('',''))
        #         print(f'Warning: location for {pc} timed out')
        # else:
        #     vol_locs.append(('',''))
        #     print(f'Warning: postcode missing for {vol}')

    positions, bads = postcodes_data(postcodes)
    if len(bads) > 0:
        print(f'Warning: bad postcodes entered, {bads}, not printed on volunteer distribution')
    plot_locations(positions.longitude, positions.latitude, jitter=30,
                   save_file='volunteer-distribution.pdf', zoom=15)

    vol_locs = zip(positions.latitude, positions.longitude)
    print(vol_locs)

    request_pcs = requests_sheet.col_values(4)
    request_names = requests_sheet.col_values(1)
    request_tasks = requests_sheet.col_values(6)
    request_status = requests_sheet.col_values(13)

    for idx, request in enumerate(request_pcs[1:]):
        if request_status[idx+1] == 'TRUE':
            print(f'Skipping request because request completed')
            continue
        # Get postcode and lat/long of request
        location = geolocator.geocode(request)
        print(f'Find closest volunteer for {(location.latitude, location.longitude)} with request type {request_tasks[idx+1]}')

        vols = get_nearest_volunteers(vol_names[1:], vol_locs, vol_requests[1:], (location.latitude, location.longitude), request_tasks[idx+1])

        for j, vol in enumerate(vols):
            requests_sheet.update_cell(idx+2, j+7, vol_names[vol-1])

        # Add trello card for this request
        due_date = datetime.now() + timedelta(7)
        trello.lists.new_card(list_id, request_names[idx+1], due_date.isoformat())

        requests_sheet.update_cell(idx+2, 13, 'TRUE')
