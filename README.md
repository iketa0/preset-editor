# 交通費プリセット編集アプリ

従業員が自分の交通費プリセット（個別・距離km）を、画面の表で直接編集して保存できるアプリ。
保存先は Google Sheets。

## 構成

```
preset_editor/
├── app.py              # Streamlit メインアプリ
├── sheets_client.py    # Google Sheets 連携 (サービスアカウント認証)
├── requirements.txt
└── README.md
```

## デプロイ手順

### 1. GitHub にリポジトリ作成
新規リポジトリ（例: `preset-editor`）を作成し、このフォルダの中身を全部アップロード。
（Public/Private どちらでも可。Secretsにキーを置くので、コードは公開でも問題なし）

### 2. Streamlit Cloud にデプロイ
1. https://share.streamlit.io → New app
2. リポジトリ・ブランチ・メインファイル（app.py）を選択
3. Deploy

### 3. Streamlit Secrets を設定
Settings → Secrets に以下を貼り付け（サービスアカウントJSONの中身を転記）:

```toml
[spreadsheet]
id = "1-O-uy2dYhk9vpYr1oIsYKlKQizSc818Lm1vdyV7E32o"

[gcp_service_account]
type = "service_account"
project_id = "shift-calendar-496812"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "sheets-editor@shift-calendar-496812.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

※ JSONキーの各フィールドをこの形式に転記する。private_key は改行を `\n` のままにする。

## スプレッドシート構成

各スタッフ・種類ごとにタブを用意:
- 武智伸伍_個別 / 武智伸伍_複数
- 西谷秀明_個別 / 西谷秀明_複数

個別タブの列: No / 利用者名 / 距離km / 備考

## 現バージョンの機能

- 個別プリセットの距離(km)のみ編集可能
- 利用者名は固定（編集不可）
- スタッフはプルダウンで選択（全員分選べる）

## 今後の拡張候補

- 複数プリセットの編集
- 利用者の追加・削除
- 本人限定アクセス（認証）
