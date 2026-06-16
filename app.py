"""
交通費プリセット編集アプリ (従業員向け)

従業員が自分の個別プリセットの距離(km)を、画面の表で直接編集して保存できる。
保存先は Google Sheets。
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import sheets_client as sc


APP_VERSION = "v1.1.1"
APP_VERSION_DATE = "2026-06-17"

# スタッフ一覧（タブ名のプレフィックス）
STAFF_LIST = ["武智 伸伍", "西谷 秀明"]

# 表示名 → タブ名 の変換
def staff_to_tab(staff_name, kind):
    """「武智 伸伍」+「個別」→「武智伸伍_個別」"""
    no_space = staff_name.replace(" ", "").replace("\u3000", "")
    return f"{no_space}_{kind}"


st.set_page_config(
    page_title="交通費プリセット編集",
    page_icon="🚗",
    layout="centered",
)

st.title("🚗 交通費プリセット編集")
st.caption("自分の名前を選んで、利用者ごとの距離(km)を編集できます。")


# ===== Google Sheets 接続 =====
try:
    service_account_info = dict(st.secrets["gcp_service_account"])
    spreadsheet_id = st.secrets["spreadsheet"]["id"]
except Exception as e:
    st.error("設定が読み込めませんでした。管理者にお問い合わせください。")
    st.stop()

try:
    client = sc.get_client(service_account_info)
    spreadsheet = sc.open_spreadsheet(client, spreadsheet_id)
except Exception as e:
    st.error(f"スプレッドシートに接続できませんでした: {e}")
    st.stop()


# ===== スタッフ選択 =====
staff = st.selectbox("あなたの名前を選んでください", STAFF_LIST)

tab_name = staff_to_tab(staff, "個別")


# ===== 個別プリセット読み込み =====
try:
    presets = sc.read_individual_presets(spreadsheet, tab_name)
except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.stop()

if not presets:
    st.warning("プリセットが登録されていません。")
    st.stop()


st.subheader(f"{staff} さんの交通費（個別）")
st.caption("「距離(km)」の数字を直接タップして書き換えられます。書き換えたら下の「保存する」を押してください。")


# 距離を数値に変換（空欄は None のまま）
def to_num(v):
    try:
        s = str(v).strip()
        return float(s) if s != '' and s.lower() != 'none' else None
    except (ValueError, AttributeError):
        return None


# データフレーム化（利用者名と距離のみ表示）
df = pd.DataFrame([
    {"利用者": p['name'], "距離(km)": to_num(p['km'])}
    for p in presets
])

# 距離(km)列を、空欄を許容できる数値型(Float64)にする
# → これで None が "None" 文字列にならず、空セルとして表示される
df["距離(km)"] = df["距離(km)"].astype("Float64")


# data_editor の編集状態をスタッフごとに保持するためのキー
# （スタッフを切り替えたら別の編集状態にする）
editor_key = f"editor_{tab_name}"

# 編集可能なテーブル
edited_df = st.data_editor(
    df,
    hide_index=True,
    width="stretch",
    column_config={
        "利用者": st.column_config.TextColumn(
            "利用者",
            disabled=True,  # 名前は編集不可
        ),
        "距離(km)": st.column_config.NumberColumn(
            "距離(km)",
            min_value=0,
            max_value=999,
            step=0.5,
            format="%.1f",
        ),
    },
    key=editor_key,
)


# ===== 保存ボタン =====
st.write("")
if st.button("💾 保存する", type="primary", width="stretch"):
    # 編集後のデータを updates 形式に変換
    updates = []
    for _, row in edited_df.iterrows():
        name = row["利用者"]
        km_val = row["距離(km)"]
        if km_val is None or pd.isna(km_val):
            km_str = ""
        else:
            km_val = float(km_val)
            # 整数なら整数表記、小数なら小数表記
            if km_val == int(km_val):
                km_str = str(int(km_val))
            else:
                km_str = str(km_val)
        updates.append({"name": name, "km": km_str})

    try:
        with st.spinner("保存中..."):
            count = sc.update_individual_km(spreadsheet, tab_name, updates)
        st.success(f"✅ 保存しました（{count}件）")
        st.caption("変更は出勤簿作成ツールにも反映されます。")
    except Exception as e:
        st.error(f"保存に失敗しました: {e}")


# ===== フッター =====
st.divider()
st.caption(f"⚙️ バージョン {APP_VERSION} ({APP_VERSION_DATE})")
