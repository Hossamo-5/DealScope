import sys
sys.path.insert(0, '.')
from core.connectors.amazon import AmazonConnector
from core.connectors.generic import detect_currency_from_url
from bot.handlers.user import format_price, CURRENCY_SYMBOLS

urls = [
    'https://www.amazon.eg/dp/B08L5TNJHG',
    'https://www.amazon.sa/dp/B08L5TNJHG',
    'https://www.amazon.ae/dp/B08L5TNJHG',
    'https://www.amazon.com/dp/B08L5TNJHG',
    'https://www.amazon.co.uk/dp/B08L5TNJHG',
    'https://www.amazon.de/dp/B08L5TNJHG',
    'https://www.amazon.ca/dp/B08L5TNJHG',
    'https://www.amazon.co.jp/dp/B08L5TNJHG',
    'https://example.eg/product/123',
    'https://shopify.sa/product/123',
]
print('=== AmazonConnector ===')
for u in urls[:8]:
    print(f'{AmazonConnector.detect_currency(u)}  |  {AmazonConnector.detect_store_name(u)}  |  {u}')
print()
print('=== detect_currency_from_url ===')
for u in urls:
    print(f'{detect_currency_from_url(u)}  |  {u}')
print()
print('=== format_price ===')
print(format_price(1234.56, 'EGP'))
print(format_price(1234.56, 'USD'))
print(format_price(1234.56, 'SAR'))
print(format_price(1234.56, 'GBP'))
