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
        row_to_insert = []
        for value in data_dict.values():
            if isinstance(value, list):
                row_to_insert.append(", ".join(value)) # Convert list to comma-separated string
            else:
                row_to_insert.append(value)
        # 3. Append the actual data
        self.sheet.append_row(row_to_insert)
        print("Data row added successfully.")

    def overwrite_row_range(self, range_name, values_list):
        # Overwrite a specific range of rows (values_list should be a list of lists)
        self.sheet.update(range_name=range_name, values=values_list)
