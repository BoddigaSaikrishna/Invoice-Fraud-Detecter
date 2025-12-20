import requests
import sys
URL = 'http://127.0.0.1:5000'
try:
    r = requests.get(URL, timeout=5)
    print('STATUS', r.status_code)
    print('\nBODY START:\n')
    print(r.text[:2000])
    print('\nBODY END')
except Exception as e:
    print('ERROR', e)
    sys.exit(1)
