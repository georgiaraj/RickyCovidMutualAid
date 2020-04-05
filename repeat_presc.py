import argparse
from trello import TrelloApi
from datetime import datetime, timedelta
import dateutil.parser as date_parser

repeat_opts = {
    'Daily': 1,
    'Weekly': 7,
    'Fortnightly': 14,
    'Monthly': 28,
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
    return parser.parse_args()


if __name__ == "__main__":

    args = get_args()

    trello = TrelloApi('96ea110307fae0a88aad529ed8f29423',
                       'b9c9b53acc2f7de0972a217366742f905ee7bb7670662e1aa6897df4fd8cfc23')
    trello_lists_presc = trello.boards.get_list('YD9AW0Hb')

    lists = {}

    for l in trello_lists_presc:
        for phar in pharmacies:
            if l['name'] == phar+' Queue':
                lists[phar] = l['id']

        if l['name'] == 'Volunteer Reported Back Completion':
            lists['completed'] = l['id']
        elif l['name'] == 'Checked with Requestor':
            lists['checked'] = l['id']

    old_cards = []
    for lname in ['checked']: #, 'completed']:
        old_cards.extend(trello.lists.get_card(lists[lname]))

    reset_list = []

    for card in old_cards:
        due_date = date_parser.isoparse(card['due']).replace(tzinfo=None)
        if any(rep in card['desc'] for rep in repeat_opts) and \
           due_date < datetime.now():
            reset_list.append(card)

    for card in reset_list:
        add_days = None
        for rep, interval in repeat_opts.items():
            if rep in card['desc']:
                add_days = timedelta(interval)

        if add_days is None:
            print(f"Warning: No repeat option found for card {card['name']}, not moved")
            continue

        due_date = date_parser.isoparse(card['due']).replace(tzinfo=None) + add_days
        trello.cards.update_due(card['id'], due_date.isoformat())
        if args.verbose:
            print(f"Due date for card {card['name']} updated to {due_date}")

        for phar in pharmacies:
            if phar in card['name'] or phar in card['desc']:
                trello.cards.update_idList(card['id'], lists[phar])
                if args.verbose:
                    print(f"Card {card['name']} moved to {lists[phar]}")
                break
