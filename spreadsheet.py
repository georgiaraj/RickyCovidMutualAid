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
    'Phone Number/ Email': 'Contact',
    'Pharmacy (if applicable)': 'Pharmacy',
    'Referred to another group': 'Referred',
    'Prescription Needs Payment': 'Needs Payment',
    'Prescription NOT at Pharmacy': 'Not At Pharmacy'
}

v_headings = {
    'Full Postcode': 'Postcode',
    'How are you able to support your neighbours?': 'Request',
    'What is the best way for us to contact you if one of your neighbours gets in touch needing help?': 'Contact Means',
    'What is your availability like? ': 'Availability',
    'Anything you would like to ask or tell us?': 'Notes',
    'Out of Action For General Requests Until': 'Out of Action',
    'Qualified Counsellor/MH Specialist': 'Counsellor'
}

requests = {
    'Shopping': 'shopping',
    'NHS Shopping': 'shopping',
    'Prescription': 'medications',
    'NHS Prescription': 'medications',
    'GP Surgery': 'medications',
    'Energy Top-up': 'Topping up electric or gas keys',
    'Post': 'Posting letters',
    'Phone Call': 'A friendly telephone call',
    'Dog Walk': 'Dog walking',
    'Other': 'urgent supplies'
}

presc_board_requests = [k for k, v in requests.items() if v == 'medications']

required_fields = [
    'Request Date',
    'Name',
    'Address',
    'Postcode',
    'Contact',
    'Request',
    'Due Date',
    'Regularity',
    'Call Taker'
]

num_vols = 10
num_phone_spec_vols = 2

def get_args():
    parser = argparse.ArgumentParser('Google sheets trello script')
    parser.add_argument('--create_trello', action='store_true',
                        help='If set, trello cards will be generated for unprocessed rows')
    parser.add_argument('--plot_vol_locations', action='store_true',
                        help='If set, the volunteer locations will be printed')
    parser.add_argument('--test_mode', action='store_true',
                        help='If set, the test spreadsheet will be used')
    parser.add_argument('--verbose', action='store_true')
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

    if request_type == 'Phone Call':
        vols = vol_df[vol_df['Counsellor']=='TRUE']
        if len(vols.index) < num_phone_spec_vols:
            replace_vols = True
        else:
            replace_vols = False

        vols = vols.sample(n=num_phone_spec_vols, replace=replace_vols).drop_duplicates('Name')


        # TODO filter out the counsellor here!
        vol_df_pcs = vol_df[vol_df['Request'].str.contains(requests[request_type])
                            & ~vol_df['Request'].str.contains(requests['Shopping'])
                            & ~vol_df['Request'].str.contains(requests['Prescription'])]
        return vols.append(vol_df_pcs.sample(n=num_vols-len(vols.index)))
    else:

        vol_df_pcs = vol_df[vol_df['Postcode exists'] &
                            vol_df['Request'].str.contains(requests[request_type]) &
                            (vol_df['Out of Action'].isnull() |
                             (vol_df['Out of Action'] < datetime.now()))].copy()

        vol_df_pcs['Distance from'] = distance_between(location, vol_df_pcs['longitude'],
                                                       vol_df_pcs['latitude'])

        vol_df_pcs = vol_df_pcs.sort_values('Distance from')

        return vol_df_pcs.head(num_vols)

def get_df_from_spreadsheet(sheet, headings):
    data = sheet.get_all_values()

    col_headings = dict(zip([headings[x] if x in headings.keys() else x for x
                             in data[0]], [x+1 for x in range(len(data[0]))]))

    df = pd.DataFrame(data[1:], columns=col_headings.keys())

    return df.copy(), col_headings


def request_outcome(sheet, headings, message):
    print(message)
    sheet.update_cell(idx+2, headings['Trello Outcome'], message)


if __name__ == "__main__":

    args = get_args()

    # use creds to create a client to interact with the Google Drive API
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    client = gspread.authorize(creds)

    if args.create_trello:
        trello = TrelloApi('96ea110307fae0a88aad529ed8f29423',
                           'b9c9b53acc2f7de0972a217366742f905ee7bb7670662e1aa6897df4fd8cfc23')
        trello_lists_general = trello.boards.get_list('KKkfsmg9')
        trello_lists_presc = trello.boards.get_list('YD9AW0Hb')
        trello_lists_calls = trello.boards.get_list('zvdFLBVj')

        # Find list id
        lists = {}
        for l in trello_lists_general:
            if l['name'] == 'Request Needing Volunteer':
                lists['main'] = l['id']
            elif l['name'] == 'is with CW/MX/CG/NW':
                lists['referred'] = l['id']

        for l in trello_lists_presc:
            if l['name'] == 'Awaiting Allocation':
                lists['pharmacy'] = l['id']

        for l in trello_lists_calls:
            if l['name'] == 'Request Needs Screening Call':
                lists['calls'] = l['id']

        if not lists:
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

    vol_df['Out of Action'] = pd.to_datetime(vol_df['Out of Action'])

    vol_df['Postcode exists'] = [False] * len(vol_df.index)
    #vol_df['Longitude'] = [(0.0,0.0)] * len(vol_df.index)

    # Format postcodes for volunteers
    vol_df = vol_df.apply(get_formatted_postcode, axis=1)

    postcodes = np.unique(vol_df[vol_df['Postcode exists']]['Postcode'].tolist())

    positions = pd.DataFrame()
    bads = pd.DataFrame()
    chunk_size = 100
    for i in range(0, len(postcodes), chunk_size):
        pos, bad = postcodes_data(postcodes[i:i+chunk_size])
        positions = positions.append(pos)
        bads = bads.append(bads)

    vol_df = vol_df.join(positions[['longitude', 'latitude']], on='Postcode', how='left')

    if args.plot_vol_locations:
        if len(bads) > 0:
            print(f'Warning: bad postcodes entered, {bads}, not printed on volunteer distribution')
        plot_locations(positions.longitude, positions.latitude, jitter=30,
                       save_file='volunteer-distribution.pdf', zoom=15)

    request_df, r_col_headings = get_df_from_spreadsheet(requests_sheet, r_headings)

    for idx, request in request_df.iterrows():
        if request['Initials'] == '':
            print(f'No further requests found.')
            break

        if request['Trello Status'] == 'TRUE':
            if args.verbose:
                print(f'Skipping request because request completed')
            continue

        try:
            # Get postcode and lat/long of request
            #location = geolocator.geocode(request['Postcode'])
            #request_loc = (location.longitude, location.latitude)
            locations, bad = postcodes_data([request['Postcode']])
            request_loc = (locations.iloc[0].longitude, locations.iloc[0].latitude)
        except:
            request_outcome(requests_sheet, r_col_headings,
                          f"Warning: Request {request['Initials']} missing or incorrect postcode, skipping")
            continue

        description = f"Find volunteer to help {request['Name']} with {request['Request']} on a {request['Regularity']} basis.\n"
        if request['Request'] == 'Prescription':
            needs = 'needs payment' if request['Needs Payment'] == 'TRUE' else 'does not need payment'
            p_loc = 'NOT yet at pharmacy' if request['Not At Pharmacy'] == 'TRUE' else 'at pharmacy'
            description += f'This prescription {needs} and is {p_loc}.\n'
        description += f"Address: {request['Address']} {request['Postcode']}\n"
        description += f"Contact details: {request['Contact']} \n"
        if request['Alternative Contact']:
            description += f"Alternative contact: {request['Alternative Contact']}\n"
        description += f"Original call taken by {request['Call Taker']} on "
        description += f"{request['Request Date']}\n\n"

        description += f"Request required by {request['Due Date']}\n\n"

        if request['Important Info']:
            description += f"IMPORTANT INFO: {request['Important Info']}\n"
        if request['Notes']:
            description += f"NOTES: {request['Notes']}\n"

        if request['Request'] == 'Phone Call':
            description += "PHONE CALL PROCESS: Phone calls should first be passed to one of the "
            description += "approved screeners on this list for a screening call. After that, "
            description += "if appropriate, they can be set up with one of the other volunteers "
            description += "for a regular chat.\n"

        elif request['Request'] not in presc_board_requests: # TODO change to if for putting vols back in phone calls
            vols = get_nearest_volunteers(vol_df, request_loc, request['Request'])

            description += f"\nPotential volunteers:\n\n"

            for j, vol in vols.reset_index().iterrows():
                string = f"- Volunteer {j+1} is {vol['Name']}. Postcode {vol['Postcode']}. "
                description += string + f"Prefers contact by {vol['Contact Means']}. "
                description += f"{vol['Phone number']} {vol['Email address']}.\n"
                if vol['Availability']:
                    description += f"Availability: {vol['Availability']}. "
                if vol['Notes']:
                    description += f"Notes: {vol['Notes']}. "
                if vol['Current Important Info']:
                    description += f"IMPORTANT VOLUNTEER INFO: {vol['Current Important Info']}.\n"
                if request['Request'] == 'Phone Call' and vol['Counsellor'] == 'TRUE':
                    description += f"QUALIFIED COUNSELLER - Please use for screening phone calls"
                description += '\n\n'
                requests_sheet.update_cell(idx+2, r_col_headings['Potential Vol 1']+j, vol['Name'])

        if args.verbose:
            print(description)

        if args.create_trello:

            if any(not request[x] for x in required_fields):
                request_outcome(requests_sheet, r_col_headings,
                                f"Warning: Trello card not created for {request['Initials']} "
                                f"as {', '.join(x for x in required_fields if not request[x])} missing")
                continue

            # Add trello card for this request
            if request['Due Date']:
                due_date = datetime.strptime(request['Due Date'], "%d/%m/%y").date()
                if request['Request'] not in presc_board_requests:
                    due_date -= timedelta(1)

            list_id = lists['main']

            card_title = f"{request['Initials']} - {request['Postcode']}"

            if request['Referred']:
                list_id = lists['referred']
            elif request['Request'] == 'Phone Call':
                list_id = lists['calls']
            elif request['Request'] in presc_board_requests:
                if request['Request'] == 'GP Surgery':
                    card_title += f" - GP Surgery"
                else:
                    card_title += f" - {request['Pharmacy']}"
                list_id = lists['pharmacy']

            trello.lists.new_card(list_id, card_title,
                                  due_date.isoformat(), desc=description)
            requests_sheet.update_cell(idx+2, r_col_headings['Trello Status'], 'TRUE')
            request_outcome(requests_sheet, r_col_headings,
                            f"Trello card created for {request['Initials']}.")
