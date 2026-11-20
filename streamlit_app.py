"""Serve the project's Arabic interface and FastAPI handlers on Community Cloud."""
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

import streamlit as st
import streamlit.components.v1 as components
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="نظام الإنذار المبكر", layout="wide")


@st.cache_resource
def prepare():
    try:
        password = st.secrets["EWS_ADMIN_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return None
    if len(str(password)) < 12:
        return None
    os.environ["EWS_ADMIN_PASSWORD"] = str(password)
    from app.main import app
    subprocess.run([sys.executable, "run.py", "--setup-only"], cwd=ROOT, check=True)
    dest = Path(tempfile.mkdtemp(prefix="ews-ui-"))
    shutil.copytree(ROOT / "app/frontend", dest, dirs_exist_ok=True)
    for path in [*dest.glob("*.html"), *dest.glob("static/js/*.js")]:
        text = path.read_text().replace('"/static/', '"./static/')
        text = text.replace('location.href = "/app"', 'location.href = "./app.html"')
        text = text.replace('location.href = "/"', 'location.href = "./index.html"')
        text = text.replace('location.href = "/?expired=1"', 'location.href = "./index.html?expired=1"')
        if path.suffix == ".html":
            text = text.replace("</head>", '<script src="./bridge.js"></script></head>')
        path.write_text(text)
    shutil.copy(ROOT / "streamlit_bridge.js", dest / "bridge.js")
    return app, components.declare_component("academic_workspace", path=str(dest))


runtime = prepare()
if runtime is None:
    st.info("لتهيئة حساب المدير، اضبط EWS_ADMIN_PASSWORD في أسرار التطبيق بكلمة مرور من 12 حرفًا على الأقل، ثم أعد تشغيله.")
    st.stop()
app, workspace = runtime
reply = st.session_state.get("reply", {})
message = workspace(reply=reply, key="workspace", default=None)
if isinstance(message, dict) and message.get("id") != reply.get("id"):
    try:
        url = urlsplit(message["path"])
        if url.scheme or url.netloc or not url.path.startswith("/api/") or ".." in url.path:
            raise ValueError("Invalid request")
        body = base64.b64decode(message["body"], validate=True)
        headers = {k:v for k,v in message["headers"].items() if k.lower() in {"authorization","content-type"}}
        with TestClient(app) as client:
            response = client.request(message["method"], message["path"], headers=headers, content=body, follow_redirects=False)
        reply = dict(status=response.status_code, body=base64.b64encode(response.content).decode(), headers={k:v for k,v in response.headers.items() if k in {"content-type","content-disposition"}})
    except Exception:
        reply = dict(status=500,body="",headers={})
    st.session_state.reply = dict(reply, id=message.get("id"))
    st.rerun()
