import gspread
from oauth2client.service_account import ServiceAccountCredentials


class GoogleSheetManager:
    def __init__(self, credentials_file, sheet_name):
        # Define the scope for Google Sheets and Drive API
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        # Authenticate and initialize the client
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, self.scope)
        self.client = gspread.authorize(self.creds)
        # Open the specific sheet and select the first worksheet
        self.sheet = self.client.open(sheet_name).sheet1

    def get_all_data(self):
        # Retrieve all records as a list of dictionaries
        return self.sheet.get_all_records()

    def get_first_rows(self, count=5):
        # This will fetch all available columns for the first 'count' rows
        # No need to worry about if it's 10, 11 or 100 columns
        range_name = f'1:{count}'
        return self.sheet.get_values(range_name)

    def read_cell(self, row, col):
        # Get a specific cell value by row and column numbers
        return self.sheet.cell(row, col).value

    def update_single_cell(self, row, col, value):
        # Update one specific cell
        self.sheet.update_cell(row, col, value)


    def add_row_headers(self, data_dict):
        first_cell = self.sheet.cell(1, 1).value
        if not first_cell:
            # Extract keys from the dictionary as headers
            headers = list(data_dict.keys())
            self.sheet.append_row(headers)
            print("Headers added to the sheet.")

    def add_row(self, data_dict):
        headers = [
            "Дата додавання", 
            "Лінк", 
            "Заголовок", 
            "Ціна", 
            "Вид об'єкта", 
            "Площа", 
            "Опис", 
            "Хеш заголовку", 
            "Поверх", 
            "Поверховість", 
            "Кількість кімнат",
            "Опалення", 
            "Клас житла", 
            "Район", 
            "Автор", 
            "Площа кухні", 
            "Фото", 
            "Ремонт", 
            "Меблювання", 
            "Тип стін", 
            "Тип планування (llm)", 
            "Кількість фото", 
            "Житловий стан на фото (llm)"
        ]
        row_to_insert = []
        for key in headers:
            value = data_dict.get(key, "")
            if value is None or value == "" or (isinstance(value, list) and not value):
                row_to_insert.append("no data")
            elif isinstance(value, list):
                row_to_insert.append(", ".join(value))
            else:
                row_to_insert.append(str(value) if value is not None else "")
        self.sheet.append_row(row_to_insert, value_input_option='RAW')
        print("Data row added successfully.")

    def overwrite_row_range(self, range_name, values_list):
        # Overwrite a specific range of rows (values_list should be a list of lists)
        self.sheet.update(range_name=range_name, values=values_list)
