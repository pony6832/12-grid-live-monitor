# 影音自動化操作軟體

Windows 本地桌面工具，目前正式版本為「12宮格直播監控 V1.1」，包含兩個獨立入口：

- 監控資料夾並自動把新影片轉成 9:16 短影音 MP4。
- YouTube 12 宮格 mpv 輕量播放器，不載入完整瀏覽器網頁並使用硬體解碼。

## 功能

- 監控指定資料夾的新影片。
- 等待檔案大小穩定後自動加入任務。
- 使用 ffprobe 讀取影片資訊，使用 ffmpeg 轉成 1080x1920 H.264/AAC MP4。
- 以中心裁切方式輸出直式短影音。
- 成功後原始檔移到 `done`，失敗後移到 `failed`。
- SQLite 保留任務狀態，重啟後仍可看到歷史任務，且不會重複處理同一個未變動檔案。

## 安裝

先確認 Windows PATH 內有 `ffmpeg` 和 `ffprobe`。

```powershell
.\install.ps1
```

## 啟動

本地影片轉檔監控器：

```powershell
.\run.ps1
```

YouTube 12 宮格正式播放器：

```powershell
.\run-youtube-player.ps1
```

第一次啟動會透過 winget 安裝 mpv 與 yt-dlp。舊 Chrome 嵌入版保留為相容備援：

```powershell
.\run-chrome-player.ps1
```

正式版不載入 YouTube 網頁，預設靜音、720p、30fps 與硬體解碼，並在上方顯示 12 個 mpv 程序的 RAM 合計。每格可獨立開關聲音、調整 0-100 音量及重載；播放程序異常退出時會在 5 秒後自動重連。紀錄寫入 `data/light_player.log`。

## V1 打包與安裝

建立 V1.1 安裝包：

```powershell
.\build-v1.1.ps1
```

產物會輸出到 `release/12宮格直播監控-V1.1`，並同時產生 `release/12宮格直播監控-V1.1.zip`。把整個資料夾交給使用者後，雙擊：

```text
安裝-12宮格直播監控-V1.1.cmd
```

安裝器會複製程式到 `%LOCALAPPDATA%\Programs\12宮格直播監控`，並建立桌面與開始功能表捷徑。

YouTube 連結編輯器（可選，現在播放器內也有側邊欄可直接改連結）：

```powershell
.\edit-youtube-links.ps1
```

YouTube Chrome grid watchdog 啟動器，會啟動一次 Chrome 宮格並寫入 watchdog log：

```powershell
.\watchdog-youtube-player.ps1
```

第一次啟動會依照 `config.json` 建立預設資料夾：

- `data/incoming`
- `data/output`
- `data/done`
- `data/failed`

## 使用方式

### 本地影片轉檔

1. 開啟 GUI。
2. 確認監控、輸出、完成、失敗資料夾。
3. 按「開始監控」。
4. 把影片放進監控資料夾。
5. 軟體會自動輸出 9:16 MP4 到輸出資料夾。

### YouTube 12 宮格

1. 執行 `.\run-youtube-player.ps1`。
2. 播放器會預設全螢幕開啟；按「連結設定」展開隱藏側邊欄。
3. 在 12 個欄位貼上 YouTube 連結、勾選「啟用」、按「保存並重載」。
4. 程式會以 mpv 原生播放器載入啟用的格子，並嵌入單一 4x3 宮格主視窗。
5. 每格預設靜音，可使用喇叭按鈕開關聲音，使用滑桿調整音量。
6. 上方畫質選單可切換 480p、720p、1080p，切換時會重新載入啟用格。

這一版預設關閉 Telegram 警告，只保留本機 log。之後若要重新開啟，先把 `config.json` 的 `telegram_alerts_enabled` 改成 `true`，再設定環境變數：

```powershell
setx TELEGRAM_BOT_TOKEN "你的 bot token"
setx TELEGRAM_CHAT_ID "你的 chat id"
```

設定後請重新開啟 PowerShell，讓新環境變數生效。

## 設定

主要設定在 `config.json`：

```json
{
  "watch_dir": "data/incoming",
  "output_dir": "data/output",
  "done_dir": "data/done",
  "failed_dir": "data/failed",
  "database_path": "data/jobs.sqlite3",
  "output_width": 1080,
  "output_height": 1920,
  "video_crf": 23,
  "video_preset": "medium",
  "audio_bitrate": "192k",
  "stable_wait_seconds": 10,
  "youtube_slots": [
    {"title": "YouTube 1", "url": "", "enabled": false}
  ],
  "youtube_monitor_interval_seconds": 30,
  "youtube_reload_after_bad_seconds": 90,
  "telegram_alerts_enabled": false
}
```

## 測試

```powershell
py -m unittest discover tests
```
