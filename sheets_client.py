"""
Google Sheets 連携クライアント (サービスアカウント認証)

交通費プリセットのスプレッドシートを読み書きする。
"""
import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
]


def get_client(service_account_info):
    """サービスアカウント情報から gspread クライアントを作成

    Args:
        service_account_info: dict (st.secrets["gcp_service_account"] の中身)

    Returns:
        gspread.Client
    """
    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def open_spreadsheet(client, spreadsheet_id):
    """スプレッドシートを開く"""
    return client.open_by_key(spreadsheet_id)


def read_worksheet(spreadsheet, tab_name):
    """指定タブの全データを2次元リストで取得

    Returns:
        [[header...], [row1...], ...]
    """
    ws = spreadsheet.worksheet(tab_name)
    return ws.get_all_values()


def read_individual_presets(spreadsheet, tab_name):
    """個別プリセットを読み込む

    Returns:
        [{'no': str, 'name': str, 'km': str, 'note': str}, ...]
        (ヘッダ行は除く、空行も除く)
    """
    values = read_worksheet(spreadsheet, tab_name)
    if not values or len(values) < 2:
        return []

    rows = []
    for row in values[1:]:  # ヘッダ行をスキップ
        # 列が足りない場合に備えてパディング
        padded = row + [''] * (4 - len(row))
        no, name, km, note = padded[0], padded[1], padded[2], padded[3]
        # 利用者名が空の行はスキップ
        if not name.strip():
            continue
        rows.append({
            'no': no.strip(),
            'name': name.strip(),
            'km': km.strip(),
            'note': note.strip(),
        })
    return rows


def update_individual_km(spreadsheet, tab_name, updates):
    """個別プリセットの距離(km)を更新

    Args:
        spreadsheet: gspread Spreadsheet
        tab_name: タブ名
        updates: [{'name': str, 'km': str}, ...] 更新したい利用者と新しい距離

    距離(km)はC列。利用者名(B列)が一致する行のC列を更新する。

    Returns:
        更新した件数
    """
    ws = spreadsheet.worksheet(tab_name)
    values = ws.get_all_values()
    if not values:
        return 0

    # 利用者名 → 行番号 (1-indexed) のマップを作る
    name_to_row = {}
    for idx, row in enumerate(values):
        if idx == 0:
            continue  # ヘッダ
        padded = row + [''] * (4 - len(row))
        name = padded[1].strip()
        if name:
            name_to_row[name] = idx + 1  # gspreadは1-indexed

    # バッチ更新用のセルリストを構築
    cells_to_update = []
    count = 0
    for upd in updates:
        name = upd['name']
        km = upd['km']
        if name in name_to_row:
            row_num = name_to_row[name]
            # C列 = 3列目 (距離km)
            cells_to_update.append(gspread.Cell(row_num, 3, km))
            count += 1

    if cells_to_update:
        ws.update_cells(cells_to_update)

    return count
