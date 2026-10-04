"""Loopback pages provide a real Referer for the official YouTube iframe API."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit
import json
import re

from app.core.youtube import parse_youtube_url


PAGE = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>Live monitor</title><style>
html,body,#player { margin:0; padding:0; width:100%; height:100%; overflow:hidden; background:#000; }
iframe { position:fixed; inset:0; width:100%; height:100%; border:0; }
</style></head><body><div id="player"></div><script>
const config = __CONFIG__;
let player, errorCode = null, ready = false;
window.monitorSnapshot = () => ({
  state: ready ? player.getPlayerState() : -1,
  time: ready ? player.getCurrentTime() : 0,
  duration: ready ? player.getDuration() : 0,
  videoId: ready ? player.getVideoData().video_id : config.videoId,
  error: errorCode,
  chromeTop: Math.max(0, outerHeight - innerHeight),
  viewport: [innerWidth, innerHeight],
  rect: document.querySelector('iframe')?.getBoundingClientRect().toJSON(),
});
window.onYouTubeIframeAPIReady = () => {
  player = new YT.Player('player', {
    width:'100%', height:'100%', videoId:config.videoId,
    playerVars:{autoplay:1,mute:1,playsinline:1,controls:1,rel:0,
      origin:location.origin, ...(config.playlistId ? {listType:'playlist',list:config.playlistId} : {})},
    events:{
      onReady:e=>{ready=true; e.target.mute(); e.target.playVideo();},
      onError:e=>{errorCode=e.data;},
      onStateChange:e=>{if(e.data===1) errorCode=null;}
    }
  });
};
</script><script src="https://www.youtube.com/iframe_api"></script></body></html>'''


class PlayerHost:
    def __init__(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)
                video = query.get('v', [''])[0]
                playlist = query.get('list', [''])[0]
                if urlsplit(self.path).path != '/player' or (not video and not playlist):
                    self.send_error(404)
                    return
                if video and not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
                    self.send_error(400)
                    return
                if playlist and not re.fullmatch(r'[A-Za-z0-9_-]+', playlist):
                    self.send_error(400)
                    return
                config = json.dumps({'videoId': video, 'playlistId': playlist})
                data = PAGE.replace('__CONFIG__', config).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def player_url(self, url: str) -> str:
        target = parse_youtube_url(url)
        return self.origin + '/player?' + urlencode({'v': target.video_id or '', 'list': target.playlist_id or ''})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


if __name__ == '__main__':
    host = PlayerHost()
    print(host.origin, flush=True)
    try:
        host.thread.join()
    except KeyboardInterrupt:
        host.close()
