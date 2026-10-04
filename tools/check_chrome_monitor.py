"""Live Chrome smoke check; closes only the monitor windows it creates."""
import json
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.core.config import AppConfig
from app.ui.chrome_embed_window import ChromeEmbedWindow
from app.ui.chrome_embed_window import user32, GWL_STYLE, WS_CAPTION, WS_POPUP, wintypes


EXPRESSION = "JSON.stringify(window.monitorSnapshot ? window.monitorSnapshot() : {})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--report', default='data/monitor-check.json')
    args = parser.parse_args()
    app = QApplication([])
    config = AppConfig.load()
    window = ChromeEmbedWindow(config)
    window.resize(1600, 950)
    results = {}
    samples = []
    connected = set()
    heartbeats = []
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: heartbeats.append(1))
    heartbeat.start(100)

    def receive(index, raw):
        message = json.loads(raw)
        if message.get('id') == 99:
            results[index] = message.get('result', {}).get('result', {}).get('value', message)
            slot = window.slots[index]
            style = user32.GetWindowLongW(wintypes.HWND(slot.chrome.hwnd), GWL_STYLE) if slot.chrome else 0
            samples.append({'slot': index + 1, 'tick': len(heartbeats), 'result': results[index],
                            'borderless': bool(slot.chrome) and not bool(style & (WS_CAPTION | WS_POPUP))})

    def inspect():
        print(json.dumps({'tick': len(heartbeats), 'states': [s.status_label.text() for s in window.slots]}, ensure_ascii=True), flush=True)
        for slot in window.slots:
            if slot.connection:
                if slot.index not in connected:
                    slot.connection.ws.textMessageReceived.connect(
                        lambda raw, index=slot.index: receive(index, raw))
                    connected.add(slot.index)
                slot.connection._send(99, 'Runtime.evaluate', {'expression': EXPRESSION})

    def finish():
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'heartbeats': len(heartbeats), 'results': results,
                          'windows': sum(bool(s.chrome) for s in window.slots)}, ensure_ascii=True), flush=True)
        window.close()
        app.quit()

    window.showFullScreen()
    sample_timer = QTimer()
    sample_timer.timeout.connect(inspect)
    sample_timer.start(15000)
    QTimer.singleShot(args.seconds * 1000, finish)
    app.exec()
    expected = sum(bool(s.get('enabled')) and bool(s.get('url')) for s in config.youtube_slots)
    valid = len(results) == expected and len(heartbeats) > 300
    for index, result in results.items():
        if not isinstance(result, str):
            valid = False
            continue
        value = json.loads(result)
        valid &= value.get('state') == 1 and value.get('error') is None
        rect = value.get('rect', {})
        valid &= [rect.get('width'), rect.get('height')] == value.get('viewport')
        slot_samples = [s for s in samples if s['slot'] == index + 1]
        valid &= len(slot_samples) >= 3 and all(s['borderless'] for s in slot_samples[-3:])
        if len(slot_samples) >= 3:
            earlier = json.loads(slot_samples[-3]['result'])
            valid &= value.get('time', 0) - earlier.get('time', 0) > 5
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
