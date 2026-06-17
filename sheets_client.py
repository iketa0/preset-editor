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
    """サービスアカウント情報から gspread クライアントを作成"""
    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def open_spreadsheet(client, spreadsheet_id):
    """スプレッドシートを開く"""
    return client.open_by_key(spreadsheet_id)


def read_worksheet(spreadsheet, tab_name):
    """指定タブの全データを2次元リストで取得"""
    ws = spreadsheet.worksheet(tab_name)
    return ws.get_all_values()


# ============================================================
# 個別プリセット
# ============================================================
def read_individual_presets(spreadsheet, tab_name):
    """個別プリセットを読み込む
    Returns:
        [{'no': str, 'name': str, 'km': str, 'note': str}, ...]
    """
    values = read_worksheet(spreadsheet, tab_name)
    if not values or len(values) < 2:
        return []
    rows = []
    for row in values[1:]:
        padded = row + [''] * (4 - len(row))
        no, name, km, note = padded[0], padded[1], padded[2], padded[3]
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
    """個別プリセットの距離(km)を更新（既存の利用者のみ）
    Args:
        updates: [{'name': str, 'km': str}, ...]
    距離(km)はC列。利用者名(B列)が一致する行のC列を更新する。
    Returns:
        更新した件数
    """
    ws = spreadsheet.worksheet(tab_name)
    values = ws.get_all_values()
    if not values:
        return 0
    name_to_row = {}
    for idx, row in enumerate(values):
        if idx == 0:
            continue
        padded = row + [''] * (4 - len(row))
        name = padded[1].strip()
        if name:
            name_to_row[name] = idx + 1
    cells_to_update = []
    count = 0
    for upd in updates:
        name = upd['name']
        km = upd['km']
        if name in name_to_row:
            row_num = name_to_row[name]
            cells_to_update.append(gspread.Cell(row_num, 3, km))
            count += 1
    if cells_to_update:
        ws.update_cells(cells_to_update)
    return count


def add_individual_preset(spreadsheet, tab_name, name, km, note=''):
    """個別プリセットに新規利用者を1件追加（最終行に追記）
    Args:
        name: 利用者名
        km: 距離(文字列でも数値でも可)
        note: 備考
    Returns:
        (成功フラグ, メッセージ)
        既に同名の利用者がいる場合は追加せず (False, 理由) を返す
    """
    ws = spreadsheet.worksheet(tab_name)
    values = ws.get_all_values()

    name = str(name).strip()
    if not name:
        return (False, "利用者名が空です")

    # 既存の利用者名・Noを収集
    existing_names = []
    max_no = 0
    for idx, row in enumerate(values):
        if idx == 0:
            continue
        padded = row + [''] * (4 - len(row))
        ex_no = padded[0].strip()
        ex_name = padded[1].strip()
        if ex_name:
            existing_names.append(ex_name)
        # Noの最大値を拾う(数値として読めるものだけ)
        try:
            n = int(float(ex_no))
            if n > max_no:
                max_no = n
        except (ValueError, TypeError):
            pass

    # 重複チェック(完全一致)
    if name in existing_names:
        return (False, f"「{name}」は既に登録されています")

    # 新しいNo
    new_no = max_no + 1
    km_str = str(km).strip()

    # 最終行に追記 (No / 利用者名 / 距離km / 備考)
    ws.append_row([new_no, name, km_str, note], value_input_option='USER_ENTERED')
    return (True, f"「{name}」を追加しました(No.{new_no})")


def check_surname_overlap(new_name, existing_names):
    """新規利用者名が、既存利用者名と苗字マッチで衝突しないか確認
    build_attendance.py の find_individual_km が「先頭一致」を使うため、
    新規名が既存名で始まる / 既存名が新規名で始まる場合は注意が必要。
    Returns:
        衝突する既存名のリスト(無ければ空)
    """
    new_name = str(new_name).strip()
    overlaps = []
    for ex in existing_names:
        ex = str(ex).strip()
        if not ex or ex == new_name:
            continue
        if new_name.startswith(ex) or ex.startswith(new_name):
            overlaps.append(ex)
    return overlaps


# ============================================================
# 複数プリセット
# ============================================================
# 複数タブの列構成(0-indexed):
#  0:No 1:行A 2:開A 3:終A 4:行B 5:開B 6:終B
#  7:行C 8:開C 9:終C 10:行D 11:開D 12:終D 13:合計距離km 14:備考
MULTI_KM_COL = 14  # 合計距離km は N列 = 14列目(1-indexed)


def read_multiple_presets(spreadsheet, tab_name):
    """複数プリセットを読み込む(15列をそのまま返す)
    Returns:
        {
          'header': [...15列のヘッダ...],
          'rows': [
             {'row_num': int(1-indexed), 'cells': [...15個...]},
             ...
          ]
        }
    """
    values = read_worksheet(spreadsheet, tab_name)
    if not values:
        return {'header': [], 'rows': []}
    header = values[0] + [''] * (15 - len(values[0]))
    header = header[:15]
    rows = []
    for idx, row in enumerate(values):
        if idx == 0:
            continue
        padded = row + [''] * (15 - len(row))
        cells = padded[:15]
        # 行き先Aが空の完全な空行はスキップ
        if not cells[1].strip() and not cells[0].strip():
            continue
        rows.append({
            'row_num': idx + 1,  # gspread 1-indexed
            'cells': cells,
        })
    return {'header': header, 'rows': rows}


def update_multiple_km(spreadsheet, tab_name, updates):
    """複数プリセットの合計距離km(N列)を更新
    Args:
        updates: [{'row_num': int, 'km': str}, ...]
                 row_num は read_multiple_presets が返す 1-indexed の行番号
    Returns:
        更新した件数
    """
    ws = spreadsheet.worksheet(tab_name)
    cells_to_update = []
    count = 0
    for upd in updates:
        row_num = upd['row_num']
        km = str(upd['km']).strip()
        cells_to_update.append(gspread.Cell(row_num, MULTI_KM_COL, km))
        count += 1
    if cells_to_update:
        ws.update_cells(cells_to_update)
    return count
