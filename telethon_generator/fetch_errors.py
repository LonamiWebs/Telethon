import sys
import json
import urllib.request

OUT = 'data/errors.json'
URL = 'https://rpc.pwrtelegram.xyz/?all'


def fetch_errors(output, url=URL):
    print('Opening a connection to', url, '...')
    r = urllib.request.urlopen(urllib.request.Request(
        url, headers={'User-Agent' : 'Mozilla/5.0'}
    ))
    print('Checking response...')
    data = json.loads(
        r.read().decode(r.info().get_param('charset') or 'utf-8')
    )
    if data.get('ok'):
        print('Response was okay, saving data')
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(data, f, sort_keys=True)
        return True
    else:
        print('The data received was not okay:')
        print(json.dumps(data, indent=4, sort_keys=True))
        return False


if __name__ == '__main__':
    out = OUT if len(sys.argv) < 2 else sys.argv[2]
    url = URL if len(sys.argv) < 3 else sys.argv[3]
    fetch_errors(out, url)
