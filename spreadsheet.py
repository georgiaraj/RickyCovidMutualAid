import gspread
from datetime import datetime, timedelta
import re, requests
import geopy
import argparse
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from oauth2client.service_account import ServiceAccountCredentials
from trello import TrelloApi

from postcodes import *

r_headings = {
    'Initials (Trello)': 'Initials',
    'Postcode (please make sure you enter this, even if approx!)': 'Postcode',
    'Pharmacy (if applicable)': 'Pharmacy'
}

v_headings = {
    'Full Postcode - needed to match you up to your neighbours': 'Postcode',
    'How are you able to support your neighbours? Tick as many as apply.': 'Request',
    'What is the best way for us to contact you if one of your neighbours gets in touch needing help?': 'Contact Means'
}

requests = {
    'Shopping': 'Picking up shopping and medications',
    'Prescription': 'Picking up shopping and medications',
    'Energy Top-up': 'Topping up electric or gas keys',
    'Post': 'Posting letters',
    'Phone Call': 'A friendly telephone call',
    'Dog Walk': 'Dog walking'
}


def get_args():
    parser = argparse.ArgumentParser('Google sheets trello script')
    parser.add_argument('--create_trello', action='store_true',
                        help='If set, trello cards will be generated for unprocessed rows')
    parser.add_argument('--plot_vol_locations', action='store_true',
                        help='If set, the volunteer locations will be printed')
    parser.add_argument('--test_mode', action='store_true',
                        help='If set, the test spreadsheet will be used')
    return parser.parse_args()


def get_formatted_postcode(row):
    result = pc_pattern.search(row['Postcode'])
    if result is not None:
        pc = f'{result.group(1).upper()} {result.group(2).upper()}'
        row['Postcode'] = pc
        row['Postcode exists'] = True
    else:
        row['Postcode exists'] = False
    return row

def get_nearest_volunteers(vol_df, location, request_type):

    vol_df_pcs = vol_df[vol_df['Postcode exists'] &
                        vol_df['Request'].str.contains(requests[request_type])].copy()

    vol_df_pcs['Distance from'] = distance_between(location, vol_df_pcs['longitude'],
                                                   vol_df_pcs['latitude'])

    vol_df_pcs = vol_df_pcs.sort_values('Distance from')

    return vol_df_pcs.head(5)

def get_df_from_spreadsheet(sheet, headings):
    data = sheet.get_all_values()

    col_headings = dict(zip([headings[x] if x in headings.keys() else x for x
                             in data[0]], [x+1 for x in range(len(data[0]))]))

    df = pd.DataFrame(data[1:], columns=col_headings.keys())

    return df.copy(), col_headings

if __name__ == "__main__":

    args = get_args()

    # use creds to create a client to interact with the Google Drive API
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    client = gspread.authorize(creds)

    if args.create_trello:
        trello = TrelloApi('96ea110307fae0a88aad529ed8f29423',
                           'b9c9b53acc2f7de0972a217366742f905ee7bb7670662e1aa6897df4fd8cfc23')
        lists = trello.boards.get_list('KKkfsmg9')

        # Find list id
        list_id = None
        for list in lists:
            if list['name'] == 'Request Needing Volunteer':
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

    if args.test_mode:
        # test sheet
        requests_sheet = client.open_by_key("1MTxkW3g-AZSn651E-brruYadG9sllr0EOwdC6CDdFy4").sheet1
    else:
        # real sheet
        requests_sheet = client.open_by_key("19JrA8_PK_N6SBTy1KO5cmRFCK1TNKtFqpB4eyKOrJuU").sheet1

    # Extract and print all of the volunteer postcodes
    vol_df, v_col_headings = get_df_from_spreadsheet(vol_sheet, v_headings)

    vol_df['Postcode exists'] = [False] * len(vol_df.index)
    #vol_df['Longitude'] = [(0.0,0.0)] * len(vol_df.index)

    # Format postcodes for volunteers
    vol_df = vol_df.apply(get_formatted_postcode, axis=1)

    print('dataframe now', vol_df)

    positions, bad = postcodes_data(vol_df[vol_df['Postcode exists']]['Postcode'])

    print('pos', positions)

    vol_df = vol_df.join(positions[['longitude', 'latitude']], on='Postcode', how='left')

    #vol_df['Longitude'][vol_df['Postcode exists']] = positions.longitude
    #vol_df['Latitude'][vol_df['Postcode exists']] = positions.latitude

    print('after join', vol_df)

    vol_names = vol_sheet.col_values(2)[1:]
    vol_addresses = vol_sheet.col_values(5)[1:]
    vol_requests = vol_sheet.col_values(6)[1:]

    # postcodes = []
    # pc_exists = []
    # for idx, vol in enumerate(vol_addresses):
    #     result = pc_pattern.search(vol)
    #     if result is not None:
    #         pc = f'{result.group(1).upper()} {result.group(2).upper()}'
    #         postcodes.append(pc)
    #         pc_exists.append(idx)

    if args.plot_vol_locations:
        if len(bads) > 0:
            print(f'Warning: bad postcodes entered, {bads}, not printed on volunteer distribution')
        plot_locations(positions.longitude, positions.latitude, jitter=30,
                       save_file='volunteer-distribution.pdf', zoom=15)

    #vol_locs = [(lng, lat) for lat, lng in zip(positions.latitude, positions.longitude)]
    #vol_names = [vol_names[x] for x in pc_exists]
    #vol_requests = [vol_requests[x] for x in pc_exists]

    request_df, r_col_headings = get_df_from_spreadsheet(requests_sheet, r_headings)

    print(r_col_headings)

    for idx, request in request_df.iterrows():
        if request['Initials'] == '':
            print(f'No further requests found.')
            break

        if request['Trello Status'] == 'TRUE':
            print(f'Skipping request because request completed')
            continue

        try:
            # Get postcode and lat/long of request
            location = geolocator.geocode(request['Postcode'])
            request_loc = (location.longitude, location.latitude)
        except AttributeError:
            print(f'Warning: Request missing postcode, skipping')
            continue

        print(f"Find closest volunteer for {request['Name']} at {request_loc} "
              f"with request type {request['Request']}")

        vols = get_nearest_volunteers(vol_df, request_loc, request['Request'])

        print(vols)

        for j, vol in enumerate(vols['Name'].values):
            print(vol, j)
            requests_sheet.update_cell(idx+2, r_col_headings['Potential Vol 1']+j, vol)

        if args.create_trello:
            # Add trello card for this request
            due_date = datetime.now() + timedelta(7)
            trello.lists.new_card(list_id, request['Initials'], due_date.isoformat(), desc='Test description')
            requests_sheet.update_cell(idx+2, r_col_headings['Trello Status'], 'TRUE')
