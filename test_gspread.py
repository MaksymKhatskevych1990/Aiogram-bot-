import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('json/service_account.json', scope)
client = gspread.authorize(creds)

print("Авторизация успешна")

sheet = client.open_by_key('1qUhwJPPDJE-NhcHoGQsIRebSCm_gE8H6K7XSKxGVcIo').worksheet('Лист3')
print("Открыли лист успешно")

data = sheet.get_all_records()
print("Прочитали данные:", data)
