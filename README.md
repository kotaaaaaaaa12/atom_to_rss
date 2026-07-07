# AstroArts Atom → RSS 2.0 Converter

[AstroArts Topics](https://www.astroarts.co.jp/article) の Atom フィードを取得して RSS 2.0 形式に変換するツール。

## 仕組み

- GitHub Actions で **6時間おき**に自動実行
- `https://www.astroarts.co.jp/article/feed.atom` を取得
- RSS 2.0 に変換して `docs/feed.rss` に出力
- 差分がある場合のみ自動コミット

## RSS フィードURL

GitHub Pages を有効にすると、以下のURLでRSSフィードにアクセスできる:

```
https://<username>.github.io/<repo>/feed.rss
```

## ローカル実行

```bash
pip install -r requirements.txt
python convert.py
```

## 手動実行

GitHub Actions の「Actions」タブから `Atom to RSS Converter` ワークフローを手動で実行することも可能。
