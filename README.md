# 12宮格直播監控

Windows 桌面工具，目前版本 V04。把最多 12 個 YouTube 直播用真正的 Chrome 嵌入單一 4x3 視窗，適合 24 小時監看。

## 安裝

雙擊 `12宮格直播監控-V04-安裝程式.exe`（不需系統管理員權限）。程式會裝到 `%LOCALAPPDATA%\Programs\12宮格直播監控`，建立桌面與開始功能表捷徑，並登錄到「設定 > 應用程式」，可從那裡解除安裝。

升級時只替換程式檔，`config.json`（頻道連結）與 `data\`（Google 登入狀態、記錄檔）不會被移動或刪除。安裝前請先關閉正在執行的程式。

安裝程式沒有數位簽章，第一次執行時 Windows SmartScreen 會出現警告，按「其他資訊 > 仍要執行」。

## 使用方式

1. 開啟後預設全螢幕。按「連結與外觀」展開側邊欄。
2. 在 12 個欄位貼上 YouTube 連結、勾選「啟用」、按「保存並重載」。網址格式不對時會指出是第幾格，不會保存。
3. 需要 Google 帳戶時按「Google 登入」。程式會關掉監控用的 Chrome，另開一個一般 Chrome 視窗讓你登入；登入後關閉那個視窗，全部頻道會自動重載。登入視窗開著的期間不會啟動任何一格。
4. 預設靜音並自動播放。是否顯示廣告由 YouTube 帳戶與影片決定。

### 可以貼的網址

- 影片或直播：`https://www.youtube.com/watch?v=…`、`https://youtu.be/…`、`https://www.youtube.com/live/…`
- 播放清單：`https://www.youtube.com/playlist?list=…`
- 頻道目前的直播：`https://www.youtube.com/channel/UC…/live`。直播重開、影片 ID 改變時會自動跟上。YouTube 不是每個頻道都提供這種嵌入方式（實測中視可用，民視、三立、中天回傳錯誤 150），該格顯示「無法播放」時請改貼影片網址。
- 不支援 `@帳號` 網址。頻道 ID 可在該頻道頁面「關於 > 分享頻道 > 複製頻道 ID」取得。

### 操作

- **單格出聲**：每格標題列的「聲音」只讓該格出聲；「全部靜音」或按 M 恢復靜音。
- **放大單格**：雙擊標題列或按「放大」；再按一次或 Esc 還原。
- **純影像模式**：按 H 隱藏工具列與標題列；滑鼠移到畫面最上緣會叫出工具列。
- **快捷鍵**：F11 全螢幕、H 純影像、M 全部靜音、Esc 依序退出側邊欄／放大／純影像／全螢幕。快捷鍵只在本程式視窗取得焦點時有效。
- **配色主題**：深夜藍／OLED 純黑／石墨灰／劇院紫金／明亮。

## 自動化

側邊欄「自動化」區塊的設定會立即保存。

- **每日自動全部重載**：預設每天 01:00，可改時間或關閉。電腦當時在睡眠的話，醒來後會補跑一次。程式沒開的時段不補跑。
- **自動復原**：某格 Chrome 視窗消失、啟動逾時或播放器斷線時，依 10／30／60／120／300 秒自動重開。暫時性播放錯誤在 3 次快速重試後改為每 10 分鐘重試。「影片無法播放」這類錯誤（直播結束、需要登入、不開放嵌入）也會每 10 分鐘重新載入一次。
- **登入提示**：多格同時因為需要登入而無法播放時，狀態列會提示按「Google 登入」。
- **Telegram 異常通知**：某格持續異常超過設定的分鐘數時發一則通知，恢復後再發一則。需要先設定環境變數，設定後重新開啟程式：

  ```powershell
  setx TELEGRAM_BOT_TOKEN "你的 bot token"
  setx TELEGRAM_CHAT_ID "你的 chat id"
  ```

- **開機自動啟動**：只有安裝版可以勾選，寫入目前使用者的啟動項目。
- **單一執行個體**：同一時間只能開一個，重複開啟會提示已在執行。

## 記錄檔

- `data\app.log`：啟動與結束、每格狀態變化與錯誤碼、每日重載、登入視窗開關。超過 1 MB 自動輪替，保留 3 份。
- `data\alerts.log`：每一則異常通知，不論 Telegram 是否開啟都會寫。

## 設定檔

`config.json` 放在程式資料夾，和從哪裡啟動無關：

```json
{
  "youtube_slots": [{"title": "YouTube 1", "url": "", "enabled": false}],
  "ui_theme": "midnight",
  "daily_reload_enabled": true,
  "daily_reload_time": "01:00",
  "telegram_alerts_enabled": false,
  "alert_after_minutes": 5
}
```

舊版留下的其他欄位會在第一次保存時移除。設定檔損壞時會改名為 `config.json.broken` 保留，另建一份預設值。

## 開發與打包

```powershell
.\install.ps1          # 建立 .venv 並安裝 PySide6
.\run.ps1              # 從原始碼啟動
.\.venv\Scripts\python.exe -m unittest discover tests
.\build.ps1            # 產生 release\12宮格直播監控-<版本> 與 .zip
.\build-installer.ps1  # 產生 release\12宮格直播監控-<版本>-安裝程式.exe
```

版本號只寫在 `app\version.py`，打包腳本與安裝程式都從那裡讀。打包時會排除 `data\` 與使用者的 `config.json`，登入狀態不會被包進安裝程式。

zip 版解壓後雙擊 `安裝-12宮格直播監控.cmd` 也能安裝，效果與單一安裝程式相同。
