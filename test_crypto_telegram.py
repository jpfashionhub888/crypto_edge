import requests

token   = '8483995149:AAFm4c9eRSPPb7Fj9A2_vyyXDhTEEPRx89s'
chat_id = '8616636381'

url = f'https://api.telegram.org/bot{token}/sendMessage'
r   = requests.post(url, json={
    'chat_id': chat_id,
    'text'   : 'CryptoEdge test!'
})
print('Status:', r.status_code)
print('Response:', r.text)