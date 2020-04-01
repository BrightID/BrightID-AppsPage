from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import requests
import datetime
import os.path
import pickle
import config
import json
import time


def read_googl_sheet():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.credentials_file, config.scopes)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    results = {}
    for sheet_name in ['Applications', 'Nodes']:
        r = sheet.values().get(spreadsheetId=config.spreadsheet_id,
                               range=sheet_name).execute()
        rows = r.get('values', [])
        results[sheet_name] = [dict(zip(rows[0], row)) for row in rows[1:]]
        for d in results[sheet_name]:
            for key in d:
                if key in ['Images', 'Links']:
                    d[key] = d[key].split('\n')
    return results


def main():
    print('Updating the application page data')
    result = read_googl_sheet()
    cs = requests.get(config.contexts_url).json()['data']['contexts']
    sponsereds = sum([c['assignedSponsorships'] -
                      c['unusedSponsorships'] for c in cs])
    contexts = {c['name']: c for c in cs}
    for app in result['Applications']:
        app['Assigned Sponsorships'] = '_'
        app['Unused Sponsorships'] = '_'
        if not app.get('Context'):
            continue
        context_name = app.get('Context')
        if not contexts.get(context_name):
            print('Cannot find "{}" in the node contexts'.format(context_name))
            continue
        context = contexts.get(context_name)
        app['Assigned Sponsorships'] = context.get('assignedSponsorships')
        app['Unused Sponsorships'] = context.get('unusedSponsorships')

    # sponsored users chart data
    now = int(time.time() * 1000)
    if os.path.exists(config.data_file_addr):
        with open(config.data_file_addr, 'r') as f:
            odata = json.loads(f.read().replace('result = ', ''))
        uchart = odata['Charts'][0]
        if (now - uchart['timestamps'][-1]) > 604800000:  # update weekly
            uchart['timestamps'].append(now)
            uchart['values'].append(sponsereds)
    else:
        uchart = {'title': 'Sponsored Uers'}
        uchart['timestamps'] = [now]
        uchart['values'] = [sponsereds]
    result['Charts'] = [uchart]

    # applications chart data
    achart = {'title': 'Applications'}
    achart['timestamps'] = sorted([time.mktime(datetime.datetime.strptime(
        r['Joined At'], "%m/%d/%Y").timetuple()) for r in result['Applications']])
    achart['values'] = [i + 1 for i, t in enumerate(achart['timestamps'])]
    result['Charts'].append(achart)

    # nodes chart data
    nchart = {'title': 'Nodes'}
    nchart['timestamps'] = sorted([time.mktime(datetime.datetime.strptime(
        r['Joined At'], "%m/%d/%Y").timetuple()) for r in result['Nodes']])
    nchart['values'] = [i + 1 for i, t in enumerate(nchart['timestamps'])]
    result['Charts'].append(nchart)

    with open(config.data_file_addr, 'w') as f:
        f.write('result = {}'.format(json.dumps(result, indent=2)))


if __name__ == '__main__':
    main()
