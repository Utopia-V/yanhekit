"""Local sign-in page; it follows the sign-in state over server-sent events."""

import json
import logging
import os
import secrets
import threading
import traceback
import webbrowser
from pathlib import Path

import requests
from flask import Flask, Response, abort, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.serving import make_server

from auth import SignIn, SignInError, saved_password, saved_username

UI = Path(__file__).with_name('ui')  # built from ui/ by `pnpm build`
DEV = os.environ.get('YANHEKIT_DEV')  # a Vite dev server, such as http://localhost:5173, that proxies /api to 5174


class State:
  """JSON-serializable values; every update wakes the event streams."""

  def __init__(self, **values):
    self.values = values
    self.version = self.sent = 0
    self.changed = threading.Condition()

  def update(self, **values):
    with self.changed:
      self.values.update(values)
      self.version += 1
      self.changed.notify_all()

  def events(self):
    version = None
    while True:
      with self.changed:
        fresh = self.changed.wait_for(lambda seen=version: self.version != seen, timeout=15)
        version = self.version
        data = json.dumps(self.values, ensure_ascii=False) if fresh else None
      yield f'data: {data}\n\n' if fresh else ': keep-alive\n\n'  # a write also notices a closed tab
      with self.changed:  # the server asks for the next event once this one is written
        self.sent = max(self.sent, version)
        self.changed.notify_all()

  def flush(self, timeout=5):
    """Wait until a page has received the current values."""
    with self.changed:
      self.changed.wait_for(lambda: self.sent >= self.version, timeout)


def describe(error):
  """Chinese for the page, without URLs, tokens or account data; the terminal gets the traceback."""
  if isinstance(error, SignInError):
    return str(error)
  traceback.print_exception(error)
  if isinstance(error, requests.RequestException):
    return '网络连接失败，请稍后重试'
  return '出错了，详情见终端'


def sign_in(client):
  """Sign in with the remembered SSO session or the saved password, or else through the local page."""
  username = saved_username()
  state = State(
    stage='credentials',  # credentials, verify or done
    username=username,
    saved=bool(saved_password(username)),
    captcha=None,
    phone='',
    sending=False,
    resend_at=0,
    message='',
  )
  signin = SignIn(client, state.update)
  done = threading.Event()
  busy = threading.Lock()

  def step(action):
    if not busy.acquire(blocking=False):
      raise SignInError('请稍候')
    try:
      if action():
        state.update(stage='done', captcha=None)
        done.set()
    finally:
      busy.release()

  try:
    step(signin.start)
  except Exception as error:  # noqa: BLE001 - shown on the page; details stay in the terminal
    state.update(message=describe(error))
  if done.is_set():
    return

  app = Flask(__name__, static_folder=None)
  token = secrets.token_urlsafe(32)

  @app.before_request
  def guard():
    if request.host != f'127.0.0.1:{server.port}':  # refuse DNS rebinding
      abort(403)
    if request.path.startswith('/api/'):
      supplied = request.headers.get('X-Token') or request.args.get('token', '')
      if not secrets.compare_digest(supplied, token):
        abort(403)

  @app.get('/', defaults={'name': 'index.html'})
  @app.get('/<path:name>')
  def static(name):
    return send_from_directory(UI, name, max_age=0)

  @app.get('/api/events')
  def events():
    return Response(state.events(), mimetype='text/event-stream', headers={'Cache-Control': 'no-store'})

  @app.errorhandler(Exception)
  def failed(error):
    return error if isinstance(error, HTTPException) else ({'error': describe(error)}, 400)

  @app.post('/api/login')
  def login():
    data = request.json
    step(lambda: signin.password(data['username'], data['password'], data['captcha'], data['remember']))
    return {}

  @app.post('/api/resend')
  def resend():
    step(signin.send_code)
    return {}

  @app.post('/api/verify')
  def verify():
    step(lambda: signin.verify(request.json['code']))
    return {}

  @app.post('/api/cancel')
  def cancel():
    signin.reset()
    return {}

  logging.getLogger('werkzeug').setLevel(logging.WARNING)
  server = make_server('127.0.0.1', 5174 if DEV else 0, app, threaded=True)
  threading.Thread(target=server.serve_forever, daemon=True).start()
  url = f'{DEV or f"http://127.0.0.1:{server.port}"}/#{token}'
  webbrowser.open(url)
  print(f'Sign-in page: {url}', flush=True)  # for when no browser opens
  try:
    while not done.wait(1):  # a timeout keeps Ctrl-C working on Windows
      pass
    state.flush()
  finally:
    server.shutdown()
