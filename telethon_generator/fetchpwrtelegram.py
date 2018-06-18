import sys
import json
import urllib.request

FILES = (
    ('data/errors.json', 'https://rpc.pwrtelegram.xyz/?all'),
    ('data/invalid_bot_methods.json', 'https://rpc.pwrtelegram.xyz/?bot')
)


def fetch_json(output, url):
    r = urllib.request.urlopen(urllib.request.Request(
        url, headers={'User-Agent' : 'Mozilla/5.0'}
    ))
    data = json.loads(
        r.read().decode(r.info().get_param('charset') or 'utf-8')
    )
    if data.get('ok'):
        del data['ok']
        if len(data) == 1:
            data = data[next(iter(data.keys()))]
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(data, f, sort_keys=True)
    else:
        print(json.dumps(data, indent=4, sort_keys=True), file=sys.stderr)


if __name__ == '__main__':
    for output, url in FILES:
        fetch_json(output, url)
