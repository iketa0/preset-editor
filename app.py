"""
交通費プリセット編集アプリ (従業員向け)

従業員が自分の個別プリセットの距離(km)を、画面の表で直接編集して保存できる。
新しい利用者の追加・削除もできる。保存先は Google Sheets。
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import sheets_client as sc


APP_VERSION = "v1.3"
APP_VERSION_DATE = "2026-06-17"

STAFF_LIST = ["武智 伸伍", "西谷 秀明"]


def staff_to_tab(staff_name, kind):
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
except Exception:
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


st.subheader(f"{staff} さんの交通費（個別）")
st.caption("「距離(km)」の数字を直接タップして書き換えられます。書き換えたら下の「保存する」を押してください。")


def to_num(v):
    try:
        s = str(v).strip()
        return float(s) if s != '' and s.lower() != 'none' else None
    except (ValueError, AttributeError):
        return None


if presets:
    df = pd.DataFrame([
        {"利用者": p['name'], "距離(km)": to_num(p['km'])}
        for p in presets
    ])
    df["距離(km)"] = df["距離(km)"].astype("Float64")

    editor_key = f"editor_{tab_name}"

    edited_df = st.data_editor(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "利用者": st.column_config.TextColumn("利用者", disabled=True),
            "距離(km)": st.column_config.NumberColumn(
                "距離(km)", min_value=0, max_value=999, step=0.5, format="%.1f",
            ),
        },
        key=editor_key,
    )

    st.write("")
    if st.button("💾 保存する", type="primary", width="stretch"):
        updates = []
        for _, row in edited_df.iterrows():
            name = row["利用者"]
            km_val = row["距離(km)"]
            if km_val is None or pd.isna(km_val):
                km_str = ""
            else:
                km_val = float(km_val)
                km_str = str(int(km_val)) if km_val == int(km_val) else str(km_val)
            updates.append({"name": name, "km": km_str})
        try:
            with st.spinner("保存中..."):
                count = sc.update_individual_km(spreadsheet, tab_name, updates)
            st.success(f"✅ 保存しました（{count}件）")
            st.caption("変更は出勤簿作成ツールにも反映されます。")
        except Exception as e:
            st.error(f"保存に失敗しました: {e}")
else:
    st.warning("プリセットがまだ登録されていません。下から新規追加できます。")


# ===== 新規利用者の追加 =====
st.divider()
st.subheader("➕ 新しい利用者を追加")
st.caption("プリセットに無い利用者を追加します。利用者名と距離(km)を入れて「追加する」を押してください。")

with st.form(f"add_form_{tab_name}", clear_on_submit=True):
    new_name = st.text_input("利用者名", placeholder="例: 山田")
    new_km = st.number_input("距離(km)", min_value=0.0, max_value=999.0, step=0.5, value=0.0)
    new_note = st.text_input("備考（任意）", placeholder="")
    submitted = st.form_submit_button("この利用者を追加する", type="primary")

if submitted:
    name_clean = new_name.strip()
    if not name_clean:
        st.error("利用者名を入力してください。")
    else:
        km_str = str(int(new_km)) if new_km == int(new_km) else str(new_km)
        existing_names = [p['name'] for p in presets]
        overlaps = sc.check_surname_overlap(name_clean, existing_names)
        try:
            ok, msg = sc.add_individual_preset(
                spreadsheet, tab_name, name_clean, km_str, new_note.strip()
            )
            if ok:
                st.success(f"✅ {msg}")
                if overlaps:
                    st.warning(
                        f"⚠️ 「{name_clean}」は既存の利用者（{', '.join(overlaps)}）と"
                        f"名前の先頭が重なります。出勤簿ツールのマッチングに"
                        f"影響する場合があるので、管理者に確認してください。"
                    )
                st.caption("上の表を最新にするには、ページを再読み込みしてください。")
            else:
                st.error(f"追加できませんでした: {msg}")
        except Exception as e:
            st.error(f"追加に失敗しました: {e}")


# ===== 利用者の削除 =====
st.divider()
st.subheader("🗑️ 利用者を削除")
st.caption("登録されている利用者を削除します。削除すると元に戻せないので、よく確認してください。")

if presets:
    name_options = [p['name'] for p in presets]
    with st.form(f"delete_form_{tab_name}"):
        del_name = st.selectbox("削除する利用者を選んでください", name_options)
        del_confirm = st.checkbox("上記の利用者を削除することを確認しました")
        del_submitted = st.form_submit_button("削除する", type="secondary")

    if del_submitted:
        if not del_confirm:
            st.error("削除するには、確認のチェックを入れてください。")
        else:
            try:
                ok, msg = sc.delete_individual_preset(spreadsheet, tab_name, del_name)
                if ok:
                    st.success(f"✅ {msg}")
                    st.caption("上の表を最新にするには、ページを再読み込みしてください。")
                else:
                    st.error(f"削除できませんでした: {msg}")
            except Exception as e:
                st.error(f"削除に失敗しました: {e}")
else:
    st.caption("（削除できる利用者がいません）")


# ===== フッター =====
st.divider()
st.caption(f"⚙️ バージョン {APP_VERSION} ({APP_VERSION_DATE})")
