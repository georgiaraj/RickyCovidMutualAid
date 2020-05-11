import argparse
from trello import TrelloApi
from datetime import datetime, timedelta
import dateutil.parser as date_parser

repeat_opts = {
    'Daily': 1,
    'Weekly': 7,
    '10 day': 10,
    'Fortnightly': 14,
    'Monthly': 28,
    '2 Monthly': 60,
    '3 Monthly': 76
}

pharmacies = [
    'Delite',
    'Tudor',
    'Chiefcornerstone',
    'Dave',
    'Boots',
    'Riverside'
]


def get_args():
    parser = argparse.ArgumentParser('Google sheets trello script')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--process_general', action='store_true',
                        help='If we need to find prescription repeats in the general board')
    return parser.parse_args()


if __name__ == "__main__":

    args = get_args()

    trello = TrelloApi('96ea110307fae0a88aad529ed8f29423',
                       'b9c9b53acc2f7de0972a217366742f905ee7bb7670662e1aa6897df4fd8cfc23')

    output_board_id = 'YD9AW0Hb'
    trello_lists_presc = trello.boards.get_list(output_board_id)

    if args.process_general:
        trello_lists_input = trello.boards.get_list('KKkfsmg9')
    else:
        trello_lists_input = trello_lists_presc

    lists_input = {}

    for l in trello_lists_input:
        if l['name'] == 'Volunteer Reported Back Completion':
            lists_input['completed'] = l['id']
        elif l['name'] == 'Checked with Requestor':
            lists_input['checked'] = l['id']

    lists_output = {}

    for l in trello_lists_presc:
        if l['name'] == 'Longer Term Requests':
            lists_output['long_term'] = l['id']
        elif l['name'] == 'Awaiting Allocation':
            lists_output['allocation'] = l['id']

    old_cards = []
    for lname in lists_input.keys():
        old_cards.extend(trello.lists.get_card(lists_input[lname]))

    reset_list = []

    for card in old_cards:
        if card['due'] is None:
            continue
        due_date = date_parser.isoparse(card['due']).replace(tzinfo=None)
        if 'Prescription' in card['desc'] and \
           any(rep in card['desc'] for rep in repeat_opts) and \
           due_date < datetime.now():
            reset_list.append(card)
        else:
            if args.verbose:
                print(f"Card {card['name']} not moved.")

    # Reset cards by setting new due date and marking as incomplete, and moving to long term list
    for card in reset_list:
        add_days = None
        for rep, interval in repeat_opts.items():
            if rep in card['desc']:
                add_days = timedelta(interval)

        if add_days is None:
            print(f"Warning: No repeat option found for card {card['name']}, not moved")
            continue

        if not args.process_general:
            trello.cards.update_idList(card['id'], lists_output['long_term'])
            print(f"Card {card['name']} moved to longer term list")

        due_date = date_parser.isoparse(card['due']).replace(tzinfo=None) + add_days
        #trello.cards.update_due(card['id'], due_date.isoformat())
        trello.cards.update(card['id'], due=due_date.isoformat(), dueComplete=0)
        trello.cards.new_action_comment(card['id'],
                                        'Repeat prescription - card moved to longer term requests')
        print(f"Due date for card {card['name']} updated to {due_date}")


    # Move any cards in the long term list that are coming soon into awaiting allocation
    long_term = trello.lists.get_card(lists_output['long_term'])

    for card in long_term:
        if date_parser.isoparse(card['due']).replace(tzinfo=None) < datetime.now() + timedelta(5):
            trello.cards.update_idList(card['id'], lists_output['allocation'])
            trello.cards.new_action_comment(card['id'],
                        'Repeat prescription - card moved to awaiting allocation as needed soon')
            print(f"Move card {card['name']} from longer term to awaiting allocation")
