# Daily 01:00 Auto Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓「12宮格直播監控 V2.0」在程式持續開啟時，每天依 Windows 本機時間於 01:00 自動執行一次既有的「全部重載」，錯過當天 01:00 則不補跑。

**Architecture:** 在 `app/core` 新增不依賴 Qt 或 UI 的單日觸發判斷元件，只在記憶體記住最近觸發日期。`ChromeEmbedWindow` 持有此元件與一個每秒執行的 `QTimer`，透過 `QDateTime.currentDateTime().toPython()` 取得本機時間；判斷到期時直接呼叫現有 `reload_enabled_slots()` 並更新狀態列，關閉視窗時停止計時器。

**Tech Stack:** Python 3、PySide6 `QTimer` / `QDateTime`、標準函式庫 `datetime` / `unittest` / `unittest.mock`、PyInstaller V2.0 建置腳本。

## Global Constraints

- 不得關閉、重啟、聚焦或操作目前電腦上既有的 V1 視窗及其 Chrome 視窗。
- 開發期間只執行隔離工作樹內的測試與建置；不得啟動新建置的 V2 執行檔做煙霧測試，避免與正在使用的監控視窗互相干擾。
- 不加入 Windows 工作排程器、背景服務、磁碟持久化或錯過後補跑。
- 手動按「全部重載」不可改變每日自動排程的去重狀態。
- 所有新行為先寫失敗測試，再寫最少實作使測試通過；每個任務完成後提交一次。

---

### Task 1: 建立純邏輯的每日觸發判斷元件

**Files:**
- Create: `app/core/daily_reload.py`
- Create: `tests/test_daily_reload.py`

- [ ] **Step 1: 先寫五個時間邊界測試**

在 `tests/test_daily_reload.py` 建立固定時間測試，明確覆蓋規格中的五個案例：

```python
from datetime import datetime
import unittest

from app.core.daily_reload import DailyReloadSchedule


class DailyReloadScheduleTests(unittest.TestCase):
    def setUp(self):
        self.schedule = DailyReloadSchedule(hour=1, minute=0)

    def test_does_not_trigger_before_target_minute(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 0, 59, 59)))

    def test_triggers_during_target_minute(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 0)))

    def test_does_not_trigger_twice_on_same_date(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 0)))
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 59)))

    def test_does_not_catch_up_after_target_minute(self):
        self.assertFalse(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 1, 0)))

    def test_triggers_again_on_next_date(self):
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 12, 1, 0, 59)))
        self.assertTrue(self.schedule.should_trigger(datetime(2026, 11, 13, 1, 0, 0)))
```

- [ ] **Step 2: 執行單一測試檔，確認先因模組不存在而失敗**

Run:

```powershell
& 'C:\Users\proedit005\Documents\老馬的影音類專案\.venv\Scripts\python.exe' -m unittest tests.test_daily_reload -v
```

Expected: `ModuleNotFoundError: No module named 'app.core.daily_reload'`，測試結束狀態為失敗。

- [ ] **Step 3: 實作最小排程判斷元件**

在 `app/core/daily_reload.py` 新增：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class DailyReloadSchedule:
    hour: int = 1
    minute: int = 0
    _last_trigger_date: date | None = field(default=None, init=False, repr=False)

    def should_trigger(self, now: datetime) -> bool:
        if now.hour != self.hour or now.minute != self.minute:
            return False
        if self._last_trigger_date == now.date():
            return False
        self._last_trigger_date = now.date()
        return True
```

這個元件只在自動排程檢查命中時記錄日期；手動重載不會呼叫它，因此不會消耗當日自動執行機會。

- [ ] **Step 4: 再跑單一測試檔，確認五個案例全部通過**

Run:

```powershell
& 'C:\Users\proedit005\Documents\老馬的影音類專案\.venv\Scripts\python.exe' -m unittest tests.test_daily_reload -v
```

Expected: `Ran 5 tests`、`OK`。

- [ ] **Step 5: 提交純排程元件與測試**

```powershell
git add app/core/daily_reload.py tests/test_daily_reload.py
git commit -m "feat: add daily reload schedule"
```

---

### Task 2: 將排程接到 ChromeEmbedWindow 的既有全部重載流程

**Files:**
- Modify: `tests/test_embed_window.py`
- Modify: `app/ui/chrome_embed_window.py:9,62-103,238-248,345-368,401-405`

- [ ] **Step 1: 先新增視窗整合測試**

在 `tests/test_embed_window.py`：

1. 加入 `datetime`、`Mock`、`AppConfig`、`ChromeEmbedWindow` 的 import。
2. 新增 `DailyReloadWindowTests`，沿用現有 `QApplication` 建立方式。
3. 用全部停用的 `AppConfig()` 建立實際視窗；不要顯示視窗，也不要處理 Qt 事件佇列，確保建構子排入的首次重載不會啟動 Chrome。
4. 將該實例的 `reload_enabled_slots` 換成 `Mock()`，直接呼叫可注入固定時間的 `_check_daily_reload(datetime(...))`。
5. `finally` 中先停止 `daily_reload_timer`、`launch_timer`、`reveal_timer`，再關閉 `player_host`，不可呼叫會操作外部 Chrome 視窗的測試輔助流程。

核心斷言：

```python
def test_due_schedule_uses_existing_reload_path_and_updates_status(self):
    window = ChromeEmbedWindow(AppConfig())
    try:
        window.reload_enabled_slots = Mock()

        triggered = window._check_daily_reload(datetime(2026, 11, 12, 1, 0, 0))

        self.assertTrue(triggered)
        window.reload_enabled_slots.assert_called_once_with()
        self.assertEqual(window.status_label.text(), "每日 01:00 已自動全部重載")
    finally:
        window.daily_reload_timer.stop()
        window.launch_timer.stop()
        window.reveal_timer.stop()
        window.player_host.close()
```

再加一個非到期案例，確認 `_check_daily_reload(datetime(2026, 11, 12, 1, 1, 0))` 回傳 `False`、不呼叫重載、也不覆寫原有狀態文字。

- [ ] **Step 2: 執行整合測試，確認先因缺少新介面而失敗**

Run:

```powershell
& 'C:\Users\proedit005\Documents\老馬的影音類專案\.venv\Scripts\python.exe' -m unittest tests.test_embed_window.DailyReloadWindowTests -v
```

Expected: 因 `ChromeEmbedWindow` 尚無 `daily_reload_timer` 或 `_check_daily_reload` 而失敗；不得出現或關閉任何 Chrome 視窗。

- [ ] **Step 3: 在視窗建立、啟動並連接每日計時器**

修改 `app/ui/chrome_embed_window.py`：

```python
from datetime import datetime

from PySide6.QtCore import QDateTime, QEvent, QObject, Qt, QTimer, Signal

from app.core.daily_reload import DailyReloadSchedule
```

在 `ChromeEmbedWindow.__init__` 與既有 `launch_timer`、`reveal_timer` 同一區域加入：

```python
self.daily_reload_schedule = DailyReloadSchedule(hour=1, minute=0)
self.daily_reload_timer = QTimer(self)
self.daily_reload_timer.setInterval(1000)
self.daily_reload_timer.timeout.connect(self._check_daily_reload)
```

完成 `_build_layout()`、事件連接、快捷鍵與配色初始化後，在 `QTimer.singleShot(0, self.reload_enabled_slots)` 之前啟動：

```python
self.daily_reload_timer.start()
```

計時器啟動前已完成所有 UI 與狀態列建立，不會在未初始化完成時觸發。

- [ ] **Step 4: 新增到期檢查方法並共用既有 reload_enabled_slots**

在 `# ---------- chrome lifecycle ----------` 區段、`save_and_reload()` 前加入：

```python
def _check_daily_reload(self, now: datetime | None = None) -> bool:
    current = now if now is not None else QDateTime.currentDateTime().toPython()
    if not self.daily_reload_schedule.should_trigger(current):
        return False
    self.reload_enabled_slots()
    self.status_label.setText("每日 01:00 已自動全部重載")
    return True
```

`now` 僅供測試注入固定時間；正式計時器呼叫不帶參數，必定走 `QDateTime.currentDateTime()` 的 Windows 本機時間。不要呼叫 `reload_button.click()`，也不要改動 `reload_enabled_slots()` 本身。

- [ ] **Step 5: 關閉視窗時先停止每日計時器**

把 `closeEvent` 開頭改為：

```python
def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
    self.daily_reload_timer.stop()
    self.reveal_timer.stop()
    self.close_all_chrome()
    self.player_host.close()
    event.accept()
```

- [ ] **Step 6: 重跑視窗整合測試**

Run:

```powershell
& 'C:\Users\proedit005\Documents\老馬的影音類專案\.venv\Scripts\python.exe' -m unittest tests.test_embed_window.DailyReloadWindowTests -v
```

Expected: `Ran 2 tests`、`OK`，且測試過程沒有開啟、關閉或改變現有 V1/Chrome 視窗。

- [ ] **Step 7: 提交視窗整合**

```powershell
git add app/ui/chrome_embed_window.py tests/test_embed_window.py
git commit -m "feat: reload all streams daily at 01:00"
```

---

### Task 3: 補上使用說明並完成回歸驗證

**Files:**
- Modify: `README.md:39-48`

- [ ] **Step 1: 在 V2.0 功能說明加入每日重載行為**

於 `README.md` 的「V2.0 新功能」清單加入：

```markdown
- **每日自動全部重載**：程式保持開啟時，每天依 Windows 本機時間於 01:00 自動執行一次「全部重載」；若當時程式未開啟，當天不補跑，等待隔天 01:00。
```

- [ ] **Step 2: 執行完整單元測試**

Run:

```powershell
& 'C:\Users\proedit005\Documents\老馬的影音類專案\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

Expected: 原有 49 個測試加上本功能 7 個測試，共 `Ran 56 tests`、`OK`；不得有失敗、錯誤或掛起的背景測試程序。

- [ ] **Step 3: 針對規格做原始碼檢查**

Run:

```powershell
rg -n "DailyReloadSchedule|daily_reload_timer|QDateTime.currentDateTime|每日 01:00 已自動全部重載" app tests README.md
rg -n "TODO|FIXME|pass\s*$|NotImplemented" app/core/daily_reload.py app/ui/chrome_embed_window.py tests/test_daily_reload.py tests/test_embed_window.py
```

Expected:

- 第一個搜尋可看到排程元件、每秒計時器、系統本機時間、共用重載流程與狀態文字均有對應實作或測試。
- 第二個搜尋沒有本功能新增的未完成標記。
- `reload_button.clicked.connect(self.reload_enabled_slots)` 保持不變，證明手動重載仍走原路徑且不會寫入排程日期鎖。

- [ ] **Step 4: 提交說明文件**

```powershell
git add README.md
git commit -m "docs: describe daily 01:00 reload"
```

---

### Task 4: 建置 V2.0 交付包但不啟動、不安裝

**Files:**
- Verify only: `build-v2.0.ps1`
- Verify only: `build-installer-v2.0.ps1`
- Generated, untracked: `dist/`, `build/`, `release/`

- [ ] **Step 1: 執行現有 V2.0 建置流程**

Run:

```powershell
.\build-v2.0.ps1
.\build-installer-v2.0.ps1
```

Expected:

- `release\12宮格直播監控-V2.0.zip` 存在。
- `release\12宮格直播監控-V2.0-安裝程式.exe` 存在。
- PowerShell 結束狀態為成功，PyInstaller 沒有 build failure。

- [ ] **Step 2: 只檢查產物，不啟動或安裝**

Run:

```powershell
Get-Item -LiteralPath '.\release\12宮格直播監控-V2.0.zip', '.\release\12宮格直播監控-V2.0-安裝程式.exe' |
    Select-Object Name, Length, LastWriteTime
git status --short
```

Expected: 兩個檔案大小大於 0、時間為本次建置時間；`git status --short` 不得出現意外的受版控檔案修改。不要雙擊、不要執行安裝程式、不要關閉目前任何 V1 或 Chrome 視窗。

- [ ] **Step 3: 最終規格覆蓋自我檢查**

逐項確認：

- 正式路徑使用 `QDateTime.currentDateTime()`，並每 1000 ms 檢查一次。
- 只有 `hour == 1` 且 `minute == 0` 會觸發；01:01 之後不補跑。
- 同日日期鎖避免 01:00 這一分鐘內重複觸發，隔天可再次觸發。
- 自動與手動都呼叫同一個 `reload_enabled_slots()`；手動按鈕不更動日期鎖。
- 自動執行後狀態列文字完全等於「每日 01:00 已自動全部重載」。
- 視窗關閉時停止 `daily_reload_timer`。
- V1 視窗在整個開發、測試、建置過程中保持原狀。

