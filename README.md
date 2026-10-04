# 影音自動化操作軟體

Windows 本地桌面工具，目前版本為「12宮格直播監控 V2.0」，包含兩個獨立入口：

- 監控資料夾並自動把新影片轉成 9:16 短影音 MP4。
- YouTube 12 宮格 Chrome 嵌入播放器，可讀取設定並把啟用的連結用真正 Chrome 嵌入單一 4x3 視窗。

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

YouTube 12 宮格 Chrome 嵌入播放器：

```powershell
.\run-youtube-player.ps1
```

## V2.0 新功能

- **自動復原**：某格 Chrome 視窗消失、啟動逾時或播放器斷線時，會依 10／30／60／120／300 秒自動重開；暫時性播放錯誤在 3 次快速重試後改為每 10 分鐘重試，不再永久停擺；連續正常播放 2 分鐘後重試次數歸零。
- **單格出聲**：每格標題列的「聲音」只讓該格出聲，其他格自動靜音；「全部靜音」或按 M 恢復靜音。
- **放大單格**：雙擊標題列或按「放大」，該格填滿整個宮格；再按一次或 Esc 還原。
- **純影像模式**：按 H 或「純影像」隱藏工具列與標題列；滑鼠移到畫面最上緣會叫出工具列。
- **配色主題**：在「連結與外觀」側邊欄可選 深夜藍／OLED 純黑／石墨灰／劇院紫金／明亮，選擇會保存到 `config.json` 的 `ui_theme`。
- **快捷鍵**：F11 全螢幕、H 純影像、M 全部靜音、Esc 依序退出側邊欄／放大／純影像／全螢幕。快捷鍵只在本程式視窗取得焦點時有效（點進某格影片後，焦點在該格 Chrome 內）。
- **升級保留登入**：V2.0 安裝器會保留原本的 `config.json` 與 `data\`（含 Google 登入狀態），並自動搬移 V1.x 放在 `_internal\data` 的登入資料。

## V2.0 打包與安裝

建立 V2.0 安裝包：

```powershell
.\build-v2.0.ps1
```

產物會輸出到 `release/12宮格直播監控-V2.0`，並同時產生 `release/12宮格直播監控-V2.0.zip`。把整個資料夾交給使用者後，雙擊：

```text
安裝-12宮格直播監控-V2.0.cmd
```

安裝器會複製程式到 `%LOCALAPPDATA%\Programs\12宮格直播監控`，並建立桌面與開始功能表捷徑。安裝前請先關閉正在執行的程式。升級時只替換程式檔，`config.json` 與 `data\`（含 Google 登入狀態）不會被移動或刪除。

### 單一 .exe 安裝程式

先執行 `.\build-v2.0.ps1`，再執行：

```powershell
.\build-installer-v2.0.ps1
```

會產生 `release/12宮格直播監控-V2.0-安裝程式.exe`（內含整個程式，不需系統管理員權限），雙擊即可安裝或升級。

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

1. 雙擊 `run-youtube-player.cmd`，或執行 `.\run-youtube-player.ps1`。
2. 播放器會預設全螢幕開啟；按「連結與外觀」展開隱藏側邊欄。
3. 在 12 個欄位貼上 YouTube 連結、勾選「啟用」、按「保存並重載」。
4. 程式會用共用 Chrome 設定檔開啟啟用的格子，並嵌入單一 4x3 宮格主視窗。
5. 每格使用官方 YouTube iframe 播放器填滿宮格，不載入留言區；播放停滯時會有限次數自動重新連線。
6. 要使用 Google 帳戶，按「Google 登入」完成登入後，再按「全部重載」。登入狀態只保存在本機 `data/chrome_monitor_profile`，不會納入 Git。
7. 預設靜音並自動播放。是否顯示廣告仍由 YouTube 帳戶與影片決定；登入有效的 Premium 帳戶可依 YouTube 規則免廣告。

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
  "telegram_alerts_enabled": false,
  "ui_theme": "midnight"
}
```

## 測試

```powershell
py -m unittest discover tests
```
