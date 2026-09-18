import shutil
import sys

import os
import re
import sqlite3
import subprocess
import threading
import time
import hashlib
import hmac
import json
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import urllib.parse
import urllib.request
import urllib.error
import ssl
import certifi
from collections import Counter
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
from pathlib import Path
from datetime import datetime, timedelta

APP_VERSION = "1.2.14"
APP_NAME = f"The iPhone Guy - Android Cleaner v{APP_VERSION}"
ADMIN_PIN_SALT = "aabbccddeeff00112233445566778899"
ADMIN_PIN_HASH = "08b7fd69a6b5494a1773f3c9ce89bc9b7f7f33c38e71ffb5e5d0a844e2ec950c"
ADMIN_PIN_ITERATIONS = 200000
ADMIN_SESSION_SECONDS = 15 * 60
BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
# Runtime application directory. Kept as an explicit alias because the icon helper
# pipeline historically referenced APP_DIR while the packaged app uses BASE_DIR.
APP_DIR = BASE_DIR

def bundled_asset(*parts):
    return APP_DIR.joinpath("assets", *parts)

def make_ui_icon(kind, color="#ffffff", size=22):
    """Create a crisp supersampled line icon without relying on Windows emoji fonts."""
    scale = 4
    S = size * scale
    img = Image.new("RGBA", (S, S), (0,0,0,0))
    d = ImageDraw.Draw(img)
    c = color
    W = max(5, int(2.1*scale))
    def line(points, width=W):
        d.line([(int(x*scale),int(y*scale)) for x,y in points], fill=c, width=width, joint="curve")
    def ellipse(box, width=W, fill=None):
        d.ellipse(tuple(int(v*scale) for v in box), outline=c if fill is None else None,
                  fill=c if fill else None, width=width)
    def rect(box, radius=2, width=W, fill=None):
        b=tuple(int(v*scale) for v in box)
        d.rounded_rectangle(b, radius=int(radius*scale), outline=c if fill is None else None,
                            fill=c if fill else None, width=width)
    if kind == "rescan":
        d.arc((3*scale,3*scale,19*scale,19*scale), 35, 305, fill=c, width=W)
        d.polygon([(18*scale,3*scale),(21*scale,8*scale),(15*scale,8*scale)], fill=c)
    elif kind == "cleanup":
        line([(5,18),(17,6)]); line([(9,20),(20,9)])
        d.polygon([(3*scale,17*scale),(8*scale,22*scale),(12*scale,18*scale),(7*scale,13*scale)], fill=c)
    elif kind == "review":
        rect((5,3,17,20),2); line([(8,8),(14,8)]); line([(8,12),(14,12)]); line([(8,16),(12,16)])
    elif kind == "games":
        d.rounded_rectangle((2*scale,7*scale,20*scale,18*scale), radius=5*scale, outline=c, width=W)
        line([(7,10),(7,15)]); line([(4.5,12.5),(9.5,12.5)])
        ellipse((14,10,16,12),fill=True); ellipse((17,13,19,15),fill=True)
    elif kind == "unused":
        rect((5,6,17,20),2); line([(3,6),(19,6)]); line([(8,3),(14,3)]); line([(9,10),(9,17)]); line([(13,10),(13,17)])
    elif kind == "all":
        for yy in (4,10,16):
            for xx in (4,10,16):
                d.rounded_rectangle((xx*scale,yy*scale,(xx+3)*scale,(yy+3)*scale), radius=scale, fill=c)
    elif kind == "help":
        ellipse((3,3,19,19)); 
        d.text((9*scale,4*scale), "?", fill=c, anchor="ma")
    elif kind == "settings":
        ellipse((7,7,15,15), width=W); ellipse((10,10,12,12), fill=True)
        for a,b in [((11,2),(11,6)),((11,16),(11,20)),((2,11),(6,11)),((16,11),(20,11))]: line([a,b])
    elif kind == "remove":
        rect((6,7,16,20),2); line([(4,6),(18,6)]); line([(8,3),(14,3)]); line([(9,10),(9,17)]); line([(13,10),(13,17)])
    elif kind == "safe":
        d.polygon([(11*scale,2*scale),(19*scale,5*scale),(18*scale,13*scale),(11*scale,21*scale),(4*scale,13*scale),(3*scale,5*scale)], outline=c, fill=None)
        line([(7,11),(10,14),(15,8)])
    elif kind == "warning":
        d.polygon([(11*scale,2*scale),(21*scale,20*scale),(1*scale,20*scale)], outline=c, fill=None)
        line([(11,7),(11,13)]); ellipse((10,16,12,18),fill=True)
    elif kind == "repair":
        line([(4,18),(17,5)]); ellipse((2,16,7,21)); ellipse((15,2,20,7))
    elif kind == "check":
        line([(4,12),(9,17),(19,6)], width=max(W,7))
    else:
        ellipse((4,4,18,18))
    img = img.resize((size,size), Image.Resampling.LANCZOS)
    return img


PRODUCTION_CONFIG_PATH = BASE_DIR / "production_config.json"
DATA_DIR = Path(os.getenv("LOCALAPPDATA", BASE_DIR)) / "TheiPhoneGuyAndroidCleaner"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ICON_DIR = DATA_DIR / "AppIcons"
ICON_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "cleaner.db"
REAL_DB_PATH = DB_PATH
TEST_DB_PATH = DATA_DIR / "cross_pc_test.db"
CROSS_PC_TEST_MODE = False
DB_SCHEMA_VERSION = 8
BACKUP_DIR = DATA_DIR / "Backups"
SEED_PATH = BASE_DIR / "knowledge_seed.json"

KNOWLEDGE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_apps(
 package_name TEXT PRIMARY KEY, canonical_name TEXT, manufacturer TEXT,
 app_type TEXT, reputation TEXT NOT NULL DEFAULT 'UNKNOWN',
 confidence INTEGER NOT NULL DEFAULT 0, knowledge_source TEXT, notes TEXT,
 first_seen TEXT, last_seen TEXT, times_seen INTEGER NOT NULL DEFAULT 0,
 times_removed INTEGER NOT NULL DEFAULT 0, times_fix_yes INTEGER NOT NULL DEFAULT 0,
 times_fix_no INTEGER NOT NULL DEFAULT 0, times_fix_unsure INTEGER NOT NULL DEFAULT 0,
 signing_cert_sha256 TEXT, last_apk_sha256 TEXT, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_hashes(
 sha256 TEXT PRIMARY KEY, package_name TEXT NOT NULL, app_name TEXT,
 classification TEXT, confidence INTEGER NOT NULL DEFAULT 0, source TEXT,
 first_seen TEXT, last_seen TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS knowledge_observations(
 id INTEGER PRIMARY KEY AUTOINCREMENT, observed_at TEXT NOT NULL,
 package_name TEXT NOT NULL, app_name TEXT, app_type TEXT, manufacturer TEXT,
 model TEXT, android_version TEXT, installer TEXT, version_name TEXT,
 apk_sha256 TEXT, signing_cert_sha256 TEXT, classification TEXT,
 source TEXT NOT NULL DEFAULT 'device_scan'
);
CREATE INDEX IF NOT EXISTS idx_knowledge_obs_pkg ON knowledge_observations(package_name);
CREATE INDEX IF NOT EXISTS idx_knowledge_obs_hash ON knowledge_observations(apk_sha256);
CREATE TABLE IF NOT EXISTS repair_outcomes(
 id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
 package_name TEXT NOT NULL, app_name TEXT, apk_sha256 TEXT, action TEXT,
 fixed_problem TEXT, reason_tag TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS repair_groups(
 id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, manufacturer TEXT, model TEXT,
 android_version TEXT, problem_tag TEXT, fixed_problem TEXT NOT NULL DEFAULT 'Pending',
 notes TEXT, app_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS db_meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS knowledge_sources(
 source_id TEXT PRIMARY KEY, source_name TEXT NOT NULL, source_url TEXT, authority TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS knowledge_seed_entries(
 package_name TEXT PRIMARY KEY, canonical_name TEXT, vendor TEXT, app_type TEXT,
 trust_status TEXT, protection_level TEXT, confidence INTEGER NOT NULL DEFAULT 0,
 source_id TEXT, notes TEXT, seed_version INTEGER NOT NULL DEFAULT 1, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS scan_sessions(
 scan_id TEXT PRIMARY KEY, scanned_at TEXT NOT NULL, manufacturer TEXT, model TEXT, android_version TEXT
);
CREATE TABLE IF NOT EXISTS system_observations(
 id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT NOT NULL, observed_at TEXT NOT NULL,
 package_name TEXT NOT NULL, app_type TEXT NOT NULL, manufacturer TEXT, model TEXT,
 android_version TEXT, apk_path TEXT, source TEXT NOT NULL DEFAULT 'adb_pm_system'
);
CREATE INDEX IF NOT EXISTS idx_system_obs_pkg ON system_observations(package_name);
CREATE TABLE IF NOT EXISTS shared_knowledge(
 package_name TEXT PRIMARY KEY, canonical_name TEXT, reputation TEXT NOT NULL DEFAULT 'UNKNOWN',
 safe_votes INTEGER NOT NULL DEFAULT 0, malware_votes INTEGER NOT NULL DEFAULT 0,
 repair_yes INTEGER NOT NULL DEFAULT 0, repair_no INTEGER NOT NULL DEFAULT 0, repair_unsure INTEGER NOT NULL DEFAULT 0,
 removals INTEGER NOT NULL DEFAULT 0, observations INTEGER NOT NULL DEFAULT 0,
 last_seen TEXT, source TEXT NOT NULL DEFAULT 'shared', updated_at TEXT
);

"""
SETTINGS_PATH = DATA_DIR / "settings.json"
RESOLVER_LOG = DATA_DIR / "resolver.log"
ADB_AUDIT_LOG = DATA_DIR / "adb_audit.log"
MALWAREBAZAAR_URL = "https://mb-api.abuse.ch/api/v1/"

ADB_CANDIDATES = [
    BASE_DIR / "platform-tools" / "adb.exe",
    BASE_DIR / "adb.exe",
    Path("adb"),
]

AAPT_CANDIDATES = [
    BASE_DIR / "aapt2-tool" / "aapt2.exe",
    BASE_DIR / "build-tools" / "aapt2.exe",
    BASE_DIR / "aapt2.exe",
]

RECOGNISED_INSTALLERS = {
    "com.android.vending": "Google Play",
    "com.sec.android.app.samsungapps": "Galaxy Store",
    "com.google.android.packageinstaller": "Package Installer",
    "com.android.packageinstaller": "Package Installer",
    "com.samsung.android.packageinstaller": "Package Installer",
}

PROTECTED_PREFIXES = (
    "com.android.",
    "android",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.google.android.packageinstaller",
    "com.samsung.android.",
    "com.sec.android.",
)

ONSET_OPTIONS = (
    "Unknown",
    "Today",
    "Last 3 days",
    "About a week",
    "Few weeks",
    "About a month",
)


def resolver_log(message):
    try:
        stamp = datetime.now().isoformat(timespec="seconds")
        with RESOLVER_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{stamp}  {message}\n")
    except Exception:
        pass

def load_settings():
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_settings(settings):
    try:
        SETTINGS_PATH.write_text(
            json.dumps(settings, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

def production_config():
    try:
        if PRODUCTION_CONFIG_PATH.exists():
            return json.loads(PRODUCTION_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def apply_production_defaults():
    """Seed deploy-time defaults without overwriting this PC's identity/settings."""
    cfg=production_config(); st=load_settings(); changed=False
    mapping={
        "shared_knowledge_url":"shared_knowledge_url",
        "shared_knowledge_api_key":"shared_knowledge_api_key",
        "update_manifest_url":"update_manifest_url",
    }
    for sk, ck in mapping.items():
        if not st.get(sk) and cfg.get(ck):
            st[sk]=str(cfg.get(ck)).strip(); changed=True
    if changed: save_settings(st)
    return st

def shared_config():
    st = load_settings()
    return {
        "url": st.get("shared_knowledge_url", "").strip(),
        "api_key": st.get("shared_knowledge_api_key", "").strip(),
        "store_id": st.get("shared_knowledge_store_id", "").strip(),
    }

def shared_configured():
    c=shared_config()
    return bool(c["url"] and c["api_key"] and c["store_id"])

def shared_request(payload, timeout=15):
    c=shared_config()
    if not (c["url"] and c["api_key"]):
        raise RuntimeError("Shared Knowledge is not configured")
    body=dict(payload)
    body["api_key"]=c["api_key"]
    body["store_id"]="TEST-PC-2" if CROSS_PC_TEST_MODE else c["store_id"]
    req=urllib.request.Request(c["url"], data=json.dumps(body).encode("utf-8"),
                               headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        result=json.loads(r.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "Shared Knowledge request failed")
    return result

def shared_push_classification(app, classification, note=""):
    if CROSS_PC_TEST_MODE: return
    if not shared_configured(): return
    payload={"op":"classification","package":app.get("package"),
             "app_name":app.get("app_name") or app.get("package"),
             "classification":classification.lower(),"note":note or "",
             "sha256":app.get("sha256") or ""}
    threading.Thread(target=lambda: _shared_quiet(payload), daemon=True).start()

def shared_push_repair(apps, fixed, reason, note, group_id):
    if CROSS_PC_TEST_MODE: return
    if not shared_configured(): return
    payload={"op":"repair","group_id":group_id,"fixed":fixed,"reason":reason,"note":note or "",
             "apps":[{"package":a.get("package"),"app_name":a.get("app_name") or a.get("package"),
                      "sha256":a.get("sha256") or ""} for a in apps]}
    threading.Thread(target=lambda: _shared_quiet(payload), daemon=True).start()

def _shared_quiet(payload):
    try: shared_request(payload)
    except Exception as e: resolver_log("Shared Knowledge: "+str(e))

def shared_push_local_snapshot():
    if CROSS_PC_TEST_MODE: return 0
    if not shared_configured(): return 0
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    try:
        rows=con.execute("""SELECT package_name,canonical_name,reputation,times_seen,times_removed,times_fix_yes,times_fix_no,times_fix_unsure,last_apk_sha256
                            FROM knowledge_apps
                            WHERE reputation<>'UNKNOWN' OR times_removed>0 OR times_fix_yes>0 OR times_fix_no>0 OR times_fix_unsure>0""").fetchall()
        apps=[]
        for r in rows:
            d=dict(r)
            pkg=d.get("package_name") or ""
            if not pkg:
                continue
            ev=repair_evidence_stats(pkg)
            apps.append({
                "package": pkg,
                "app_name": d.get("canonical_name") or pkg,
                "reputation": d.get("reputation") or "UNKNOWN",
                "observations": int(d.get("times_seen") or 0),
                "removals": int(d.get("times_removed") or 0),
                "repair_yes": int(d.get("times_fix_yes") or 0),
                "repair_no": int(d.get("times_fix_no") or 0),
                "repair_unsure": int(d.get("times_fix_unsure") or 0),
                "solo_yes": int(ev.get("solo_yes") or 0),
                "solo_no": int(ev.get("solo_no") or 0),
                "solo_unsure": int(ev.get("solo_unsure") or 0),
                "group_yes": int(ev.get("group_yes") or 0),
                "group_no": int(ev.get("group_no") or 0),
                "group_unsure": int(ev.get("group_unsure") or 0),
                "popup_solo_yes": int(ev.get("popup_solo_yes") or 0),
                "popup_group_yes": int(ev.get("popup_group_yes") or 0),
                "sha256": d.get("last_apk_sha256") or "",
            })
    finally: con.close()
    if apps: shared_request({"op":"snapshot","apps":apps}, timeout=30)
    return len(apps)

def shared_pull():
    result=shared_request({"op":"pull"}, timeout=20)
    rows=result.get("apps",[])
    con=sqlite3.connect(DB_PATH)
    try:
        for r in rows:
            pkg=str(r.get("package") or "").strip()
            if not pkg: continue
            con.execute("""INSERT INTO shared_knowledge(package_name,canonical_name,reputation,safe_votes,malware_votes,repair_yes,repair_no,repair_unsure,removals,observations,last_seen,source,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(package_name) DO UPDATE SET canonical_name=excluded.canonical_name,reputation=excluded.reputation,
                         safe_votes=excluded.safe_votes,malware_votes=excluded.malware_votes,repair_yes=excluded.repair_yes,repair_no=excluded.repair_no,
                         repair_unsure=excluded.repair_unsure,removals=excluded.removals,observations=excluded.observations,last_seen=excluded.last_seen,updated_at=excluded.updated_at""",
                        (pkg,r.get("app_name"),r.get("reputation") or "UNKNOWN",int(r.get("safe_votes") or 0),int(r.get("malware_votes") or 0),
                         int(r.get("repair_yes") or 0),int(r.get("repair_no") or 0),int(r.get("repair_unsure") or 0),int(r.get("removals") or 0),
                         int(r.get("observations") or 0),r.get("last_seen"),"shared",datetime.now().isoformat(timespec="seconds")))
        con.commit()
    finally: con.close()
    return len(rows)

def shared_info(package):
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    try:
        r=con.execute("SELECT * FROM shared_knowledge WHERE package_name=?",(package,)).fetchone()
        return dict(r) if r else {}
    finally: con.close()

def shared_malware_info_by_name(app_name):
    """Conservative cross-PC fallback for known-malware records.

    Package name remains the primary identity.  If a store has learned a junk app
    under a package variant, allow an *exact normalised resolved label* to recover
    the shared KNOWN MALWARE verdict, but only when that label identifies exactly
    one shared malware record.  Safe reputation never uses name fallback.
    """
    name = re.sub(r"[^a-z0-9]+", " ", str(app_name or "").lower()).strip()
    if not name or len(name) < 5:
        return {}
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    try:
        rows=con.execute("SELECT * FROM shared_knowledge WHERE UPPER(reputation)='KNOWN MALWARE'").fetchall()
        matches=[]
        for row in rows:
            canonical=re.sub(r"[^a-z0-9]+", " ", str(row["canonical_name"] or "").lower()).strip()
            if canonical and canonical == name:
                matches.append(dict(row))
        return matches[0] if len(matches) == 1 else {}
    finally:
        con.close()

def get_malwarebazaar_key():
    return load_settings().get("malwarebazaar_auth_key", "").strip()

def set_malwarebazaar_key(key):
    settings = load_settings()
    settings["malwarebazaar_auth_key"] = key.strip()
    save_settings(settings)

def malwarebazaar_lookup(sha256_hex, auth_key):
    """
    Query MalwareBazaar by exact file hash.
    No sample is uploaded. Only the SHA-256 hash is sent.
    """
    payload = urllib.parse.urlencode({
        "query": "get_info",
        "hash": sha256_hex
    }).encode("ascii")

    req = urllib.request.Request(
        MALWAREBAZAAR_URL,
        data=payload,
        method="POST",
        headers={
            "Auth-Key": auth_key,
            "User-Agent": "The-iPhone-Guy-Android-Cleaner/0.7"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MalwareBazaar HTTP {e.code}: {detail[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Online reputation lookup failed: {e.reason}")

def pull_apk_and_hash(serial, app):
    cached = identity_get(app)
    if cached and cached.get("sha256"):
        if cached.get("app_label"):
            app["app_name"] = cached["app_label"]
            app["identity_state"] = "Resolved"
        app["sha256"] = cached["sha256"]
        return cached["sha256"], 0

    label, sha256_hex, size = pull_apk_identity(serial, app)
    identity_set(app, label, sha256_hex)
    app["sha256"] = sha256_hex

    if label:
        app["app_name"] = label
        app["identity_state"] = "Resolved"

    return sha256_hex, size


def _flags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

def find_adb():
    for candidate in ADB_CANDIDATES:
        try:
            r = subprocess.run(
                [str(candidate), "version"],
                capture_output=True, text=True, timeout=5,
                creationflags=_flags()
            )
            if r.returncode == 0:
                return str(candidate)
        except Exception:
            pass
    return None

def run_adb(args, timeout=20):
    adb = find_adb()
    if not adb:
        raise RuntimeError("ADB tools are missing from this Android Cleaner installation. Reinstall or update Android Cleaner.")
    try:
        stamp = datetime.now().isoformat(timespec="seconds")
        with open(ADB_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(stamp + " | adb " + " ".join(str(x) for x in args) + "\n")
    except Exception:
        pass
    r = subprocess.run(
        [adb] + args,
        capture_output=True, text=True, timeout=timeout,
        creationflags=_flags()
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def adb_run(args, timeout=20):
    """CompletedProcess-compatible wrapper around the app's normal ADB runner."""
    code, out, err = run_adb(args, timeout=timeout)
    return subprocess.CompletedProcess(args=args, returncode=code, stdout=out, stderr=err)

def shell(serial, args, timeout=20):
    return run_adb(["-s", serial, "shell"] + args, timeout=timeout)

def find_aapt2():
    resolver_log("AAPT2 locator: explicit local paths only")
    for candidate in AAPT_CANDIDATES:
        try:
            p = Path(candidate)
            resolver_log(f"AAPT2 checking: {p}")
            if p.is_file():
                resolver_log(f"AAPT2 found: {p}")
                return str(p)
        except Exception as exc:
            resolver_log(f"AAPT2 path error: {exc!r}")
    resolver_log("AAPT2 not found")
    return None


def apk_path_for_package(serial, app):
    package = app["package"]
    apk_path = app.get("apk_path", "").strip()
    code_, out, _ = shell(serial, ["pm", "path", package], timeout=20)
    if code_ == 0 and out:
        paths = [
            line[len("package:"):].strip()
            for line in out.splitlines()
            if line.startswith("package:")
        ]
        if paths:
            bases = [p for p in paths if p.endswith("/base.apk")]
            apk_path = bases[0] if bases else paths[0]
    return apk_path

def extract_real_label(apk_path):
    aapt2 = find_aapt2()
    if not aapt2:
        raise RuntimeError("AAPT2 was not found.")

    resolver_log(f"AAPT2 EXEC: {aapt2} dump badging {apk_path}")

    try:
        r = subprocess.run(
            [aapt2, "dump", "badging", str(apk_path)],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=_flags()
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("AAPT2 timed out after 20 seconds reading the APK.")

    resolver_log(f"AAPT2 EXIT: code {r.returncode}")

    stdout = r.stdout or ""
    stderr = r.stderr or ""

    if r.returncode != 0:
        raise RuntimeError(
            stderr.strip()
            or stdout.strip()
            or f"AAPT2 exited with code {r.returncode}"
        )

    out = stdout if isinstance(stdout, str) else str(stdout or "")

    # Prefer the default label, then English/Australian variants.
    patterns = [
        r"^application-label:'(.*)'$",
        r"^application-label-en-AU:'(.*)'$",
        r"^application-label-en-GB:'(.*)'$",
        r"^application-label-en:'(.*)'$",
        r"^application-label-[^:]+:'(.*)'$",
        r"^application: label='([^']*)'",
    ]

    for pattern in patterns:
        m = re.search(pattern, out, re.MULTILINE)
        if m:
            value = m.group(1)
            if value is not None:
                value = str(value).strip()
                if value:
                    return value

    # Some APKs can expose an empty/default label but still contain
    # localized labels in the badging text. Fall back to collecting them.
    localized = re.findall(
        r"^application-label-[^:]+:'(.*)'$",
        out,
        re.MULTILINE
    )
    for value in localized:
        if value is not None:
            value = str(value).strip()
            if value:
                return value

    return ""

def icon_cache_path(sha256_hex):
    if not sha256_hex:
        return ""
    return str(ICON_DIR / f"{sha256_hex}.png")


def extract_app_icon(apk_path, sha256_hex):
    """Extract/render a launcher icon from an APK and cache it as PNG.

    Handles ordinary raster icons plus common adaptive-icon XML where the
    foreground/background resolve to raster drawables or simple color resources.
    Falls back safely when a package uses a drawable we cannot render.
    """
    if not sha256_hex:
        return ""
    target = Path(icon_cache_path(sha256_hex))

    # AAPT2 reported launcher icon is the most authoritative resource. Resolve
    # the resource name to matching density files in the APK before heuristics.
    try:
        aapt2 = find_aapt2()
        if aapt2:
            rr = subprocess.run([str(aapt2), "dump", "badging", str(apk_path)],
                                capture_output=True, text=True, timeout=15,
                                creationflags=_flags())
            badging = (rr.stdout or "") + "\n" + (rr.stderr or "")
            reported = []
            for mm in re.finditer(r"application-icon-[^:]+:'([^']+)'", badging):
                reported.append(mm.group(1))
            mm = re.search(r"application:.*?icon='([^']+)'", badging)
            if mm: reported.append(mm.group(1))
            with zipfile.ZipFile(apk_path, "r") as zf:
                for resource in reported:
                    candidates=[n for n in zf.namelist()
                                if n == resource or n.endswith("/"+Path(resource).name)]
                    for name in candidates:
                        if name.lower().endswith((".png",".webp",".jpg",".jpeg")):
                            try:
                                with zf.open(name) as fh:
                                    im=Image.open(fh).convert("RGBA")
                                    if im.width >= 24 and im.height >= 24:
                                        im.thumbnail((96,96),Image.Resampling.LANCZOS)
                                        im.save(target,"PNG")
                                        resolver_log(f"ICON extracted via AAPT2: {name}")
                                        return str(target)
                            except Exception:
                                continue
    except Exception as exc:
        resolver_log(f"ICON AAPT2 badging fallback failed: {exc!r}")

    # Fast archive fallback: many APKs expose launcher PNG/WebP resources even
    # when compiled adaptive-icon XML cannot be decoded cleanly.
    try:
        with zipfile.ZipFile(apk_path, "r") as zf:
            launcher_candidates = []
            for name in zf.namelist():
                low = name.lower()
                if not low.startswith("res/"):
                    continue
                if not low.endswith((".png", ".webp", ".jpg", ".jpeg")):
                    continue
                score = 0
                if "mipmap" in low: score += 40
                if any(k in low for k in ("ic_launcher", "launcher", "app_icon", "icon")): score += 50
                if any(k in low for k in ("xxxhdpi", "xxhdpi", "xhdpi")): score += 10
                if "foreground" in low or "background" in low: score -= 20
                if score > 40:
                    launcher_candidates.append((score, name))
            launcher_candidates.sort(reverse=True)
            for _, name in launcher_candidates[:12]:
                try:
                    with zf.open(name) as fh:
                        im = Image.open(fh).convert("RGBA")
                        if im.width >= 32 and im.height >= 32:
                            im.thumbnail((96, 96), Image.Resampling.LANCZOS)
                            im.save(target, "PNG")
                            return str(target)
                except Exception:
                    continue
    except Exception as exc:
        resolver_log(f"ICON archive fallback failed: {exc!r}")
    if target.is_file() and target.stat().st_size > 0:
        return str(target)

    aapt2 = find_aapt2()
    if not aapt2:
        return ""

    try:
        r = subprocess.run(
            [aapt2, "dump", "badging", str(apk_path)],
            capture_output=True, text=True, timeout=20,
            creationflags=_flags()
        )
        if r.returncode != 0:
            return ""
        out = r.stdout or ""

        candidates = []
        for density, resource in re.findall(
            r"^application-icon-(\d+):'([^']+)'$", out, re.MULTILINE
        ):
            candidates.append((int(density), resource))
        m = re.search(r"^application: .*?\bicon='([^']+)'", out, re.MULTILINE)
        if m:
            candidates.append((0, m.group(1)))
        candidates.sort(key=lambda x: x[0], reverse=True)

        ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

        def save_image(im):
            im = im.convert("RGBA")
            im.thumbnail((96, 96), Image.Resampling.LANCZOS)
            im.save(target, "PNG")
            return str(target)

        def open_raster(zf, resource):
            if resource not in zf.namelist():
                return None
            if not resource.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
                return None
            from io import BytesIO
            with Image.open(BytesIO(zf.read(resource))) as im:
                return im.convert("RGBA").copy()

        def drawable_candidates(zf, ref):
            # @drawable/name, @mipmap/name, or a direct res/... path.
            if not ref:
                return []
            ref = ref.strip()
            if ref.startswith("res/"):
                return [ref] if ref in zf.namelist() else []
            m = re.match(r"@(?:[A-Za-z0-9_.]+:)?(drawable|mipmap)/([A-Za-z0-9_.]+)", ref)
            if not m:
                return []
            kind, name = m.groups()
            found = []
            for n in zf.namelist():
                if not n.startswith("res/"):
                    continue
                leaf = n.rsplit("/", 1)[-1]
                folder = n.split("/", 2)[1]
                if not (folder == kind or folder.startswith(kind + "-")):
                    continue
                if leaf.rsplit(".", 1)[0] == name:
                    found.append(n)
            # Prefer raster and higher-density folders; XML last.
            def score(n):
                folder = n.split("/", 2)[1]
                density = {
                    "xxxhdpi": 640, "xxhdpi": 480, "xhdpi": 320,
                    "hdpi": 240, "mdpi": 160, "ldpi": 120
                }
                d = max((v for k, v in density.items() if k in folder), default=0)
                raster = 10000 if n.lower().endswith((".png",".webp",".jpg",".jpeg")) else 0
                return raster + d
            return sorted(found, key=score, reverse=True)

        def parse_xml_text(zf, resource):
            if resource not in zf.namelist():
                return None
            raw = zf.read(resource)
            # Compiled binary XML cannot be parsed by ElementTree. Ask AAPT2 to
            # emit the XML tree, which preserves the resource references we need.
            try:
                return raw.decode("utf-8")
            except Exception:
                pass
            try:
                rr = subprocess.run(
                    [aapt2, "dump", "xmltree", str(apk_path), "--file", resource],
                    capture_output=True, text=True, timeout=20,
                    creationflags=_flags()
                )
                if rr.returncode == 0:
                    return rr.stdout or ""
            except Exception:
                return None
            return None

        def refs_from_adaptive_xml(zf, resource):
            text = parse_xml_text(zf, resource)
            if not text:
                return "", ""
            # Plain XML path (occasionally present in unpacked/test APKs).
            try:
                root = ET.fromstring(text)
                bg = root.find("background")
                fg = root.find("foreground")
                bgref = bg.get(ANDROID_NS + "drawable", "") if bg is not None else ""
                fgref = fg.get(ANDROID_NS + "drawable", "") if fg is not None else ""
                if bgref or fgref:
                    return bgref, fgref
            except Exception:
                pass

            # AAPT2 xmltree output. Capture the drawable attribute following each
            # background/foreground element.
            bgref = fgref = ""
            current = None
            for line in text.splitlines():
                stripped = line.strip()
                if "E: background" in stripped:
                    current = "bg"
                elif "E: foreground" in stripped:
                    current = "fg"
                elif stripped.startswith("E: ") and "background" not in stripped and "foreground" not in stripped:
                    current = None
                if current and "A: android:drawable" in stripped:
                    m = re.search(r'="([^"]+)"', stripped)
                    if m:
                        if current == "bg":
                            bgref = m.group(1)
                        else:
                            fgref = m.group(1)
            return bgref, fgref

        def render_ref(zf, ref):
            for res in drawable_candidates(zf, ref):
                im = open_raster(zf, res)
                if im is not None:
                    return im
            return None

        with zipfile.ZipFile(apk_path, "r") as zf:
            names = set(zf.namelist())

            # 1. Ordinary raster launcher icon.
            for _density, resource in candidates:
                try:
                    im = open_raster(zf, resource)
                    if im is not None:
                        resolver_log(f"ICON raster: {resource}")
                        return save_image(im)
                except Exception as exc:
                    resolver_log(f"ICON raster decode failed {resource}: {exc!r}")

            # 2. Adaptive icon XML. Common case: XML launcher icon references
            # raster foreground/background resources.
            xml_candidates = []
            for _density, resource in candidates:
                if resource.lower().endswith(".xml") and resource in names:
                    xml_candidates.append(resource)

            # Badging can point at a legacy fallback while adaptive resources sit
            # in mipmap-anydpi-v26. Look for likely launcher XML names too.
            for n in names:
                low = n.lower()
                if ("/mipmap-anydpi" in low or "/drawable-anydpi" in low) and low.endswith(".xml"):
                    if any(k in low for k in ("ic_launcher", "launcher", "app_icon", "/icon")):
                        xml_candidates.append(n)

            seen = set()
            for resource in xml_candidates:
                if resource in seen:
                    continue
                seen.add(resource)
                try:
                    bgref, fgref = refs_from_adaptive_xml(zf, resource)
                    if not (bgref or fgref):
                        continue
                    bg = render_ref(zf, bgref)
                    fg = render_ref(zf, fgref)
                    if bg is None and fg is None:
                        continue

                    size = 192
                    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                    if bg is not None:
                        bg.thumbnail((size, size), Image.Resampling.LANCZOS)
                        bx = (size - bg.width)//2
                        by = (size - bg.height)//2
                        canvas.alpha_composite(bg, (bx, by))
                    if fg is not None:
                        # Android adaptive foreground has safe-zone padding; keep
                        # some breathing room rather than cropping the artwork.
                        max_fg = int(size * 0.82)
                        fg.thumbnail((max_fg, max_fg), Image.Resampling.LANCZOS)
                        fx = (size - fg.width)//2
                        fy = (size - fg.height)//2
                        canvas.alpha_composite(fg, (fx, fy))

                    resolver_log(f"ICON adaptive: {resource} bg={bgref!r} fg={fgref!r}")
                    return save_image(canvas)
                except Exception as exc:
                    resolver_log(f"ICON adaptive failed {resource}: {exc!r}")

    except Exception as exc:
        resolver_log(f"ICON extraction failed: {exc!r}")

    resolver_log(f"ICON no usable launcher image in {Path(apk_path).name}")
    return ""



_ICON_HELPER_READY = set()

def find_icon_helper():
    candidates = [
        APP_DIR / "icon-helper.jar",
        Path(__file__).resolve().parent / "icon-helper.jar",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def pull_device_rendered_icon(serial, app):
    """Ask Android itself to resolve and rasterize the installed app icon."""
    package = str(app.get("package") or "").strip()
    if not package:
        return ""

    helper = find_icon_helper()
    if not helper:
        resolver_log(f"ICON DEVICE {package}: bundled icon-helper.jar missing; APP_DIR={APP_DIR}")
        return ""
    resolver_log(f"ICON DEVICE {package}: helper found {helper}")

    # Stable cache without pulling the APK. Updating/reinstalling the app changes
    # version/update identity and therefore creates a fresh cache entry.
    identity = "|".join([
        package,
        str(app.get("version_name") or ""),
        str(app.get("last_update") or ""),
    ])
    cache_key = hashlib.sha256(identity.encode("utf-8", errors="ignore")).hexdigest()
    cached = icon_cache_path(cache_key)
    if cached and Path(cached).is_file() and Path(cached).stat().st_size > 100:
        app["icon_path"] = cached
        return cached

    remote_jar = "/data/local/tmp/tig-icon-helper.jar"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", package)
    remote_png = f"/data/local/tmp/tig-icon-{safe}.png"
    local_tmp = Path(tempfile.gettempdir()) / f"tig_device_icon_{safe}.png"

    try:
        if serial not in _ICON_HELPER_READY:
            resolver_log(f"ICON DEVICE {package}: pushing helper to {remote_jar}")
            push = adb_run(["-s", serial, "push", str(helper), remote_jar], timeout=30)
            if push.returncode != 0:
                resolver_log(f"ICON DEVICE {package}: helper push failed rc={push.returncode}: {(push.stderr or push.stdout or '').strip()}")
                return ""
            resolver_log(f"ICON DEVICE {package}: helper push OK")
            _ICON_HELPER_READY.add(serial)
        else:
            # The phone may have rebooted or /data/local/tmp may have been cleaned
            # while this desktop process stayed open. Verify the helper still exists.
            check = adb_run(["-s", serial, "shell", "test", "-s", remote_jar], timeout=5)
            if check.returncode != 0:
                _ICON_HELPER_READY.discard(serial)
                resolver_log(f"ICON DEVICE {package}: remote helper missing; re-pushing")
                push = adb_run(["-s", serial, "push", str(helper), remote_jar], timeout=30)
                if push.returncode != 0:
                    resolver_log(f"ICON DEVICE {package}: helper re-push failed rc={push.returncode}: {(push.stderr or push.stdout or '').strip()}")
                    return ""
                _ICON_HELPER_READY.add(serial)

        # app_process runs as the shell user. The helper obtains Android's system
        # Context and PackageManager, so adaptive/vector icons are rendered by the
        # same framework that renders them in the launcher.
        resolver_log(f"ICON DEVICE {package}: starting app_process renderer")
        run = adb_run([
            "-s", serial, "shell",
            f"CLASSPATH={remote_jar}",
            "app_process", "/system/bin", "IconFetcher",
            package, remote_png, "192"
        ], timeout=20)
        output = ((run.stdout or "") + " " + (run.stderr or "")).strip()
        resolver_log(f"ICON DEVICE {package}: app_process rc={run.returncode} output={output[:500]!r}")
        if run.returncode != 0:
            return ""

        stat = adb_run(["-s", serial, "shell", "stat", "-c", "%s", remote_png], timeout=5)
        resolver_log(f"ICON DEVICE {package}: remote PNG size={(stat.stdout or '').strip()!r} stat_rc={stat.returncode}")

        pull = adb_run(["-s", serial, "pull", remote_png, str(local_tmp)], timeout=20)
        local_size = local_tmp.stat().st_size if local_tmp.is_file() else 0
        resolver_log(f"ICON DEVICE {package}: PNG pull rc={pull.returncode} bytes={local_size}")
        if pull.returncode != 0 or local_size <= 100:
            resolver_log(f"ICON DEVICE {package}: PNG pull failed: {(pull.stderr or pull.stdout or '').strip()}")
            return ""

        # Validate and normalize before caching.
        with Image.open(local_tmp) as im:
            im = im.convert("RGBA")
            if im.width < 24 or im.height < 24:
                raise RuntimeError(f"rendered icon too small: {im.size}")
            target = Path(icon_cache_path(cache_key))
            target.parent.mkdir(parents=True, exist_ok=True)
            im.save(target, "PNG")

        app["icon_path"] = str(target)
        resolver_log(f"ICON DEVICE {package}: success {target.name}")
        return str(target)

    except Exception as exc:
        resolver_log(f"ICON DEVICE {package}: {exc!r}")
        return ""
    finally:
        try:
            local_tmp.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            adb_run(["-s", serial, "shell", "rm", "-f", remote_png], timeout=5)
        except Exception:
            pass


def pull_apk_icon(serial, app):
    """Primary: Android framework renderer. Fallback: host-side APK parsing."""
    icon = pull_device_rendered_icon(serial, app)
    if icon:
        return icon
    resolver_log(f"ICON {app.get('package','')}: device renderer unavailable; trying APK fallback")
    return pull_apk_icon_fallback(serial, app)


def pull_apk_icon_fallback(serial, app):
    """Populate a cached launcher icon for a flagged app.

    Modern Play installs are commonly split APKs. Density-specific launcher
    artwork can live outside base.apk, so inspect density splits before base.
    """
    package = str(app.get("package") or "").strip()
    if not package:
        return ""
    existing = str(app.get("icon_path") or "")
    if existing and Path(existing).is_file():
        return existing
    if not find_adb():
        return ""

    pulled=[]
    try:
        sha = str(app.get("sha256") or "").strip()
        if sha:
            cached=icon_cache_path(sha)
            if cached and Path(cached).is_file():
                app["icon_path"]=cached
                return cached

        r=adb_run(["-s",serial,"shell","pm","path",package],timeout=12)
        paths=[]
        for line in (r.stdout or "").splitlines():
            line=line.strip().replace("\r","")
            if line.startswith("package:"):
                path=line.split("package:",1)[1].strip()
                if path and path not in paths:
                    paths.append(path)
        if not paths:
            resolver_log(f"ICON {package}: no APK paths returned")
            return ""

        safe=re.sub(r"[^A-Za-z0-9_.-]+","_",package)
        # Pull base first to establish stable package hash.
        base=next((x for x in paths if x.endswith("/base.apk")),paths[0])
        base_local=Path(tempfile.gettempdir())/f"tig_icon_{safe}_base.apk"
        pr=adb_run(["-s",serial,"pull",base,str(base_local)],timeout=45)
        if pr.returncode != 0 or not base_local.is_file() or base_local.stat().st_size <= 0:
            resolver_log(f"ICON {package}: base pull failed: {(pr.stderr or pr.stdout or '').strip()}")
            return ""
        pulled.append(base_local)
        h=hashlib.sha256()
        with open(base_local,"rb") as fh:
            for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
        sha=h.hexdigest()
        app["sha256"]=sha

        # Density splits are most likely to contain a directly renderable launcher
        # PNG/WebP. Search them first, then other splits, then base.
        def rank(path):
            low=path.lower()
            if any(x in low for x in ("xxxhdpi","xxhdpi","xhdpi","hdpi")): return 0
            if "dpi" in low: return 1
            if path == base: return 3
            return 2
        ordered=sorted(paths,key=rank)

        for n,remote in enumerate(ordered):
            local = base_local if remote == base else Path(tempfile.gettempdir())/f"tig_icon_{safe}_{n}.apk"
            if remote != base:
                pr=adb_run(["-s",serial,"pull",remote,str(local)],timeout=45)
                if pr.returncode != 0 or not local.is_file() or local.stat().st_size <= 0:
                    continue
                pulled.append(local)
            resolver_log(f"ICON {package}: inspecting {Path(remote).name}")
            icon=extract_app_icon(local,sha)
            if icon:
                app["icon_path"]=icon
                resolver_log(f"ICON {package}: success from {Path(remote).name}")
                return icon

        resolver_log(f"ICON {package}: no usable icon across {len(ordered)} APK split(s)")
        return ""
    except Exception as exc:
        resolver_log(f"ICON background {package}: {exc!r}")
        return ""
    finally:
        for local in pulled:
            try: local.unlink(missing_ok=True)
            except Exception: pass



def pull_apk_identity(serial, app):
    package = app["package"]
    resolver_log(f"IDENTITY {package}: locating APK path")

    apk_path = apk_path_for_package(serial, app)
    if not apk_path:
        raise RuntimeError("Could not determine APK path for this app.")

    resolver_log(f"IDENTITY {package}: APK path={apk_path!r}")

    adb = find_adb()
    if not adb:
        raise RuntimeError("ADB was not found.")

    aapt2 = find_aapt2()
    if not aapt2:
        raise RuntimeError(
            "AAPT2 tools are missing from this Android Cleaner installation. Reinstall or update Android Cleaner."
        )

    resolver_log(f"IDENTITY {package}: AAPT2 found {aapt2}")

    def do_pull(local_path, attempt):
        resolver_log(
            f"IDENTITY {package}: ADB pull attempt {attempt} start"
        )
        try:
            r = subprocess.run(
                [adb, "-s", serial, "pull", apk_path, str(local_path)],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=_flags()
            )
        except subprocess.TimeoutExpired:
            resolver_log(
                f"IDENTITY {package}: ADB pull attempt {attempt} timeout"
            )
            return False, "ADB pull timed out"

        stdout = (r.stdout or "").strip()
        stderr = (r.stderr or "").strip()

        resolver_log(
            f"IDENTITY {package}: ADB pull attempt {attempt} "
            f"returncode={r.returncode} stdout={stdout[:300]!r} "
            f"stderr={stderr[:300]!r}"
        )

        # adb pull may emit progress text to stderr even on success.
        # Treat the filesystem result + return code as authoritative.
        success = (
            r.returncode == 0
            and local_path.exists()
            and local_path.is_file()
            and local_path.stat().st_size > 0
        )

        if success:
            return True, ""

        # If adb returned success but the file wasn't there yet, give Windows
        # a brief retry opportunity before declaring failure.
        if r.returncode == 0 and local_path.exists():
            try:
                if local_path.stat().st_size > 0:
                    return True, ""
            except Exception:
                pass

        detail = stderr or stdout or f"ADB pull exited with code {r.returncode}"
        return False, detail

    with tempfile.TemporaryDirectory(prefix="tig_identity_") as td:
        local = Path(td) / "base.apk"

        ok, detail = do_pull(local, 1)
        if not ok:
            resolver_log(
                f"IDENTITY {package}: first pull failed, retrying once: {detail}"
            )
            try:
                if local.exists():
                    local.unlink()
            except Exception:
                pass

            ok, detail = do_pull(local, 2)

        if not ok:
            raise RuntimeError(f"APK pull failed: {detail}")

        resolver_log(
            f"IDENTITY {package}: pulled {local.stat().st_size} bytes; hashing"
        )

        h = hashlib.sha256()
        with local.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)

        sha256_hex = h.hexdigest()
        resolver_log(f"IDENTITY {package}: starting AAPT2 label extraction")
        label = extract_real_label(local)
        label = str(label or "").strip()
        resolver_log(f"IDENTITY {package}: label={label!r}")
        extract_app_icon(local, sha256_hex)

        return label, sha256_hex, local.stat().st_size



def db_backup(reason="manual"):
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / (
        f"cleaner_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{reason}.db"
    )
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def table_exists(con, name):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def migrate_legacy_reputation(con):
    if not table_exists(con, "app_reputation"):
        return
    names = [r[1] for r in con.execute("PRAGMA table_info(app_reputation)")]
    now = datetime.now().isoformat(timespec="seconds")
    for row in con.execute("SELECT * FROM app_reputation").fetchall():
        d = dict(zip(names, row))
        pkg = d.get("package_name")
        if not pkg:
            continue
        cls = (d.get("classification") or "").lower()
        rep = {"safe":"KNOWN SAFE","suspicious":"SUSPICIOUS",
               "malware":"KNOWN MALWARE"}.get(cls,"UNKNOWN")
        con.execute("""
          INSERT INTO knowledge_apps(
            package_name,canonical_name,reputation,confidence,knowledge_source,
            notes,first_seen,last_seen,times_seen,times_removed,created_at,updated_at
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(package_name) DO UPDATE SET
            canonical_name=COALESCE(excluded.canonical_name,canonical_name),
            reputation=CASE WHEN excluded.reputation<>'UNKNOWN'
                       THEN excluded.reputation ELSE reputation END,
            confidence=MAX(confidence,excluded.confidence),
            notes=COALESCE(excluded.notes,notes),
            first_seen=COALESCE(first_seen,excluded.first_seen),
            last_seen=COALESCE(excluded.last_seen,last_seen),
            times_seen=MAX(times_seen,excluded.times_seen),
            times_removed=MAX(times_removed,excluded.times_removed),
            updated_at=excluded.updated_at
        """,(pkg,d.get("app_name"),rep,100 if rep!="UNKNOWN" else 0,
             "technician" if rep!="UNKNOWN" else "legacy observation",d.get("notes"),
             d.get("first_seen"),d.get("last_seen"),int(d.get("times_seen") or 0),
             int(d.get("times_removed") or 0),now,now))


def migrate_knowledge_quality_v4(con):
    """
    v4 database-quality cleanup:
    - UNKNOWN legacy rows were observations, not technician classifications.
    - Rebuild times_seen from distinct recorded scan sessions where possible.
      This prevents resolver/promote/classification DB touches from inflating it.
    """
    con.execute("""
        UPDATE knowledge_apps
           SET knowledge_source='legacy observation'
         WHERE reputation='UNKNOWN'
           AND knowledge_source='legacy technician classification'
    """)

    # Count each package at most once per actual scan. knowledge_observations
    # stores scan ids as source='device_scan:<scan_id>'; system_observations
    # stores scan_id directly.
    packages = [
        r[0] for r in con.execute(
            "SELECT package_name FROM knowledge_apps"
        ).fetchall()
    ]
    for pkg in packages:
        scan_ids = set()

        for (source,) in con.execute(
            """SELECT source FROM knowledge_observations
               WHERE package_name=? AND source LIKE 'device_scan:%'""",
            (pkg,),
        ).fetchall():
            if source:
                scan_ids.add(source.split("device_scan:", 1)[1])

        for (scan_id,) in con.execute(
            "SELECT scan_id FROM system_observations WHERE package_name=?",
            (pkg,),
        ).fetchall():
            if scan_id:
                scan_ids.add(scan_id)

        # Only replace historical counters where scan-level evidence exists.
        # Otherwise preserve old information rather than inventing a value.
        if scan_ids:
            con.execute(
                "UPDATE knowledge_apps SET times_seen=? WHERE package_name=?",
                (len(scan_ids), pkg),
            )

    con.execute(
        "INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",
        ("times_seen_semantics", "distinct scan sessions"),
    )


def migrate_system_observations_v5(con):
    rows = con.execute(
        """SELECT id,scan_id,observed_at,package_name,app_type,manufacturer,
                  model,android_version,apk_path,source
           FROM system_observations
           ORDER BY observed_at DESC,id DESC"""
    ).fetchall()
    seen = set()
    delete_ids = []
    for r in rows:
        key = (
            r[3] or "", r[4] or "", r[5] or "", r[6] or "",
            r[7] or "", r[8] or ""
        )
        if key in seen:
            delete_ids.append(r[0])
        else:
            seen.add(key)
    if delete_ids:
        con.executemany(
            "DELETE FROM system_observations WHERE id=?",
            [(x,) for x in delete_ids]
        )
    con.execute(
        "INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",
        ("system_observation_semantics", "one row per package/device state")
    )


def migrate_repair_intelligence_v6(con):
    cols={r[1] for r in con.execute("PRAGMA table_info(repair_outcomes)").fetchall()}
    for col, decl in (("repair_group_id","TEXT"),("classification_after","TEXT"),("manufacturer","TEXT"),("model","TEXT"),("android_version","TEXT")):
        if col not in cols:
            con.execute(f"ALTER TABLE repair_outcomes ADD COLUMN {col} {decl}")
    con.execute("""CREATE TABLE IF NOT EXISTS repair_groups(
        id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, manufacturer TEXT, model TEXT,
        android_version TEXT, problem_tag TEXT, fixed_problem TEXT NOT NULL DEFAULT 'Pending',
        notes TEXT, app_count INTEGER NOT NULL DEFAULT 0)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_repair_outcomes_group ON repair_outcomes(repair_group_id)")

def knowledge_stats(package):
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    try:
        r=con.execute("SELECT times_seen,times_removed,times_fix_yes,times_fix_no,times_fix_unsure,reputation,knowledge_source,updated_at FROM knowledge_apps WHERE package_name=?",(package,)).fetchone()
        return dict(r) if r else {}
    finally: con.close()

def repair_evidence_stats(package):
    """Return outcome evidence split by solo removals vs group-associated removals.

    A successful outcome after removing several apps is useful evidence, but it does
    not prove which member of the group caused the symptom.  Keep that evidence
    separate from an app removed on its own.
    """
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    try:
        rows=con.execute("""
            SELECT ro.fixed_problem, ro.reason_tag, COALESCE(rg.app_count,1) AS app_count
            FROM repair_outcomes ro
            LEFT JOIN repair_groups rg ON rg.id=ro.repair_group_id
            WHERE ro.package_name=? AND ro.action='Removed'
              AND ro.fixed_problem IN ('Yes','No','Unsure')
        """,(package,)).fetchall()
        out={
            'solo_yes':0,'solo_no':0,'solo_unsure':0,
            'group_yes':0,'group_no':0,'group_unsure':0,
            'popup_solo_yes':0,'popup_group_yes':0,
        }
        for r in rows:
            scope='solo' if int(r['app_count'] or 1)==1 else 'group'
            result=(r['fixed_problem'] or 'Unsure').lower()
            if result not in ('yes','no','unsure'): result='unsure'
            out[f'{scope}_{result}'] += 1
            if r['fixed_problem']=='Yes' and (r['reason_tag'] or '').lower()=='pop-up ads':
                out[f'popup_{scope}_yes'] += 1
        return out
    finally:
        con.close()

def record_removal_group(apps, manufacturer='', model='', android_version=''):
    now=datetime.now().isoformat(timespec="seconds")
    gid="repair_"+datetime.now().strftime("%Y%m%d%H%M%S%f")
    con=sqlite3.connect(DB_PATH)
    try:
        con.execute("INSERT INTO repair_groups(id,recorded_at,manufacturer,model,android_version,app_count) VALUES(?,?,?,?,?,?)",
                    (gid,now,manufacturer,model,android_version,len(apps)))
        for app in apps:
            pkg=app.get("package"); name=app.get("app_name") or pkg
            con.execute("""INSERT INTO repair_outcomes(recorded_at,package_name,app_name,apk_sha256,action,fixed_problem,reason_tag,notes,repair_group_id,manufacturer,model,android_version)
                         VALUES(?,?,?,?,?,'Pending','','',?,?,?,?)""",
                        (now,pkg,name,app.get("sha256"),"Removed",gid,manufacturer,model,android_version))
            con.execute("UPDATE knowledge_apps SET times_removed=times_removed+1,updated_at=? WHERE package_name=?",(now,pkg))
        con.commit()
    finally: con.close()
    return gid

def ensure_knowledge_database():
    """Forward-only, backed-up schema migration. Never recreates cleaner.db."""
    existing = DB_PATH.exists() and DB_PATH.stat().st_size > 0
    con = sqlite3.connect(DB_PATH)
    try:
        current = int(con.execute("PRAGMA user_version").fetchone()[0])
    finally:
        con.close()
    if current > DB_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema {current} is newer than supported "
            f"schema {DB_SCHEMA_VERSION}. It was not modified."
        )
    if existing and current < DB_SCHEMA_VERSION:
        db_backup(f"pre_migration_v{current}_to_v{DB_SCHEMA_VERSION}")
    con=sqlite3.connect(DB_PATH)
    try:
        con.executescript(KNOWLEDGE_SCHEMA_SQL)
        if current < 1:
            migrate_legacy_reputation(con)
            con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",
                        ("knowledge_foundation","v0.9.1"))
        if current < 2:
            con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",("knowledge_observations","v0.9.3"))
        if current < 3:
            con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",("system_inventory","v0.9.4"))
        if current < 4:
            migrate_knowledge_quality_v4(con)
            con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",("knowledge_quality","v0.9.5"))
        if current < 5:
            migrate_system_observations_v5(con)
        if current < 6:
            migrate_repair_intelligence_v6(con)
            con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",("system_observation_dedupe","v0.9.8"))
        if current < 7:
            con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES(?,?)",("repair_evidence_semantics","solo_vs_group_association"))
        apply_knowledge_seed(con)
        con.execute(f"PRAGMA user_version={DB_SCHEMA_VERSION}")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def apply_knowledge_seed(con):
    if not SEED_PATH.exists():
        return
    data=json.loads(SEED_PATH.read_text(encoding="utf-8"))
    version=int(data.get("seed_version",1))
    old=int((con.execute("SELECT value FROM db_meta WHERE key='seed_version'").fetchone() or ["0"])[0])
    if version <= old:
        return
    now=datetime.now().isoformat(timespec="seconds")
    for s in data.get("sources",[]):
        con.execute("""INSERT INTO knowledge_sources(source_id,source_name,source_url,authority,updated_at)
                       VALUES(?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
                       source_name=excluded.source_name,source_url=excluded.source_url,
                       authority=excluded.authority,updated_at=excluded.updated_at""",
                    (s["id"],s["name"],s.get("url"),s.get("authority"),now))
    for e in data.get("entries",[]):
        con.execute("""INSERT INTO knowledge_seed_entries(package_name,canonical_name,vendor,app_type,
                    trust_status,protection_level,confidence,source_id,notes,seed_version,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(package_name) DO UPDATE SET
                    canonical_name=excluded.canonical_name,vendor=excluded.vendor,app_type=excluded.app_type,
                    trust_status=excluded.trust_status,protection_level=excluded.protection_level,
                    confidence=excluded.confidence,source_id=excluded.source_id,notes=excluded.notes,
                    seed_version=excluded.seed_version,updated_at=excluded.updated_at""",
                    (e["package"],e.get("name"),e.get("vendor"),e.get("app_type"),e.get("trust_status","VERIFIED"),
                     e.get("protection_level","SYSTEM"),int(e.get("confidence",100)),e.get("source_id"),e.get("notes"),version,now))
        # Seed identity/type, but NEVER overwrite technician malware reputation/notes.
        con.execute("""INSERT INTO knowledge_apps(package_name,canonical_name,manufacturer,app_type,reputation,
                    confidence,knowledge_source,first_seen,last_seen,times_seen,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(package_name) DO UPDATE SET
                    canonical_name=COALESCE(knowledge_apps.canonical_name,excluded.canonical_name),
                    manufacturer=COALESCE(knowledge_apps.manufacturer,excluded.manufacturer),
                    app_type=CASE WHEN knowledge_apps.app_type IS NULL OR knowledge_apps.app_type='' THEN excluded.app_type ELSE knowledge_apps.app_type END,
                    confidence=MAX(knowledge_apps.confidence,excluded.confidence),
                    knowledge_source=CASE WHEN knowledge_apps.knowledge_source='technician' THEN knowledge_apps.knowledge_source ELSE excluded.knowledge_source END,
                    updated_at=excluded.updated_at""",
                    (e["package"],e.get("name"),e.get("vendor"),e.get("app_type"),"UNKNOWN",int(e.get("confidence",100)),
                     "authoritative seed",None,None,0,now,now))
    con.execute("INSERT OR REPLACE INTO db_meta(key,value) VALUES('seed_version',?)",(str(version),))


def seed_entry(package):
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    try:
        row=con.execute("SELECT * FROM knowledge_seed_entries WHERE package_name=?",(package,)).fetchone()
        return dict(row) if row else None
    finally: con.close()


def knowledge_record_scan(rows, manufacturer, model, android_version):
    now=datetime.now().isoformat(timespec="seconds")
    scan_id=datetime.now().strftime("%Y%m%d%H%M%S%f")
    con=sqlite3.connect(DB_PATH)
    try:
        con.execute("INSERT INTO scan_sessions(scan_id,scanned_at,manufacturer,model,android_version) VALUES(?,?,?,?,?)",
                    (scan_id,now,manufacturer,model,android_version))
        for app in rows:
            pkg=app.get("package"); name=app.get("app_name")
            if not pkg: continue
            con.execute("""INSERT INTO knowledge_apps(package_name,canonical_name,manufacturer,app_type,reputation,
                        confidence,knowledge_source,first_seen,last_seen,times_seen,last_apk_sha256,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(package_name) DO UPDATE SET
                        canonical_name=CASE WHEN excluded.canonical_name<>excluded.package_name THEN excluded.canonical_name ELSE knowledge_apps.canonical_name END,
                        manufacturer=COALESCE(knowledge_apps.manufacturer,excluded.manufacturer),
                        app_type=excluded.app_type,last_seen=excluded.last_seen,times_seen=knowledge_apps.times_seen+1,
                        last_apk_sha256=COALESCE(NULLIF(excluded.last_apk_sha256,''),knowledge_apps.last_apk_sha256),updated_at=excluded.updated_at""",
                        (pkg,name,manufacturer,app.get("app_type"),"UNKNOWN",0,"device observation",now,now,1,
                         app.get("sha256","") or None,now,now))
            con.execute("""INSERT INTO knowledge_observations(observed_at,package_name,app_name,app_type,manufacturer,
                        model,android_version,installer,version_name,apk_sha256,classification,source)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (now,pkg,name,app.get("app_type"),manufacturer,model,android_version,app.get("installer"),
                         app.get("version_name"),app.get("sha256") or None,app.get("classification"),"device_scan:"+scan_id))
        con.commit()
    finally: con.close()


def knowledge_promote_identity(app):
    now=datetime.now().isoformat(timespec="seconds"); pkg=app.get("package"); name=app.get("app_name"); sha=app.get("sha256")
    if not pkg: return
    con=sqlite3.connect(DB_PATH)
    try:
        con.execute("""INSERT INTO knowledge_apps(package_name,canonical_name,app_type,reputation,confidence,knowledge_source,
                    first_seen,last_seen,times_seen,last_apk_sha256,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(package_name) DO UPDATE SET canonical_name=COALESCE(NULLIF(excluded.canonical_name,excluded.package_name),knowledge_apps.canonical_name),
                    app_type=COALESCE(excluded.app_type,knowledge_apps.app_type),last_apk_sha256=COALESCE(NULLIF(excluded.last_apk_sha256,''),knowledge_apps.last_apk_sha256),updated_at=excluded.updated_at""",
                    (pkg,name,app.get("app_type"),"UNKNOWN",0,"resolved identity",now,now,0,sha or None,now,now))
        if name and name != pkg:
            con.execute("""UPDATE knowledge_observations SET app_name=?, apk_sha256=COALESCE(NULLIF(?,''),apk_sha256)
                         WHERE id=(SELECT id FROM knowledge_observations WHERE package_name=? ORDER BY id DESC LIMIT 1)""",
                        (name,sha or "",pkg))
        con.commit()
    finally: con.close()

def knowledge_classify(app, classification, notes=""):
    now=datetime.now().isoformat(timespec="seconds")
    rep={"safe":"KNOWN SAFE","suspicious":"SUSPICIOUS",
         "malware":"KNOWN MALWARE"}.get(classification,"UNKNOWN")
    sha=app.get("sha256") or app.get("apk_sha256")
    con=sqlite3.connect(DB_PATH)
    try:
        con.execute("""
          INSERT INTO knowledge_apps(
            package_name,canonical_name,app_type,reputation,confidence,
            knowledge_source,notes,first_seen,last_seen,times_seen,created_at,updated_at
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(package_name) DO UPDATE SET
            canonical_name=COALESCE(excluded.canonical_name,canonical_name),
            app_type=COALESCE(excluded.app_type,app_type),
            reputation=excluded.reputation,confidence=100,
            knowledge_source='technician',notes=excluded.notes,
            last_seen=excluded.last_seen,updated_at=excluded.updated_at
        """,(app["package"],app.get("app_name"),classify_app_type(app),rep,100,
             "technician",notes,now,now,1,now,now))
        if sha:
            con.execute("""
              INSERT INTO knowledge_hashes(
                sha256,package_name,app_name,classification,confidence,
                source,first_seen,last_seen,notes
              ) VALUES(?,?,?,?,?,?,?,?,?)
              ON CONFLICT(sha256) DO UPDATE SET
                classification=excluded.classification,confidence=100,
                source='technician',last_seen=excluded.last_seen,notes=excluded.notes
            """,(sha,app["package"],app.get("app_name"),classification,100,
                 "technician",now,now,notes))
        con.commit()
    finally:
        con.close()


def export_knowledge_database(destination):
    src=sqlite3.connect(DB_PATH); dst=sqlite3.connect(destination)
    try: src.backup(dst)
    finally: dst.close(); src.close()


def import_knowledge_database(source):
    test=sqlite3.connect(source)
    try:
        ok=test.execute("PRAGMA integrity_check").fetchone()[0]
        ver=int(test.execute("PRAGMA user_version").fetchone()[0])
    finally: test.close()
    if ok!="ok": raise RuntimeError("Selected database failed SQLite integrity check.")
    if ver>DB_SCHEMA_VERSION:
        raise RuntimeError(f"Database schema {ver} is newer than supported.")
    db_backup("pre_import")
    shutil.copy2(source,DB_PATH)
    ensure_knowledge_database()


def init_db():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS app_reputation(
            package_name TEXT PRIMARY KEY,
            app_name TEXT,
            classification TEXT NOT NULL DEFAULT 'unknown',
            notes TEXT,
            first_seen TEXT,
            last_seen TEXT,
            times_seen INTEGER NOT NULL DEFAULT 0,
            times_removed INTEGER NOT NULL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS online_cache(
            sha256 TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            checked_at TEXT NOT NULL
        )
    """)

    # v0.8 identity-cache migration.
    # Earlier experimental builds may already have an identity_cache table
    # with a different schema. CREATE TABLE IF NOT EXISTS will not upgrade it,
    # so inspect the columns and rebuild only this cache table when needed.
    expected_identity_columns = {
        "identity_key",
        "package_name",
        "version_name",
        "last_update",
        "app_label",
        "sha256",
        "resolved_at",
    }

    existing_cols = {
        row[1]
        for row in c.execute("PRAGMA table_info(identity_cache)").fetchall()
    }

    if existing_cols and existing_cols != expected_identity_columns:
        # This table contains only derived/cache data, so it is safe to rebuild.
        c.execute("DROP TABLE IF EXISTS identity_cache")

    c.execute("""
        CREATE TABLE IF NOT EXISTS identity_cache(
            identity_key TEXT PRIMARY KEY,
            package_name TEXT NOT NULL,
            version_name TEXT,
            last_update TEXT,
            app_label TEXT,
            sha256 TEXT,
            resolved_at TEXT NOT NULL
        )
    """)

    con.commit()
    con.close()
    ensure_knowledge_database()


def identity_key_for(app):
    return "|".join([
        app.get("package", ""),
        app.get("version_name", ""),
        app.get("last_update", "")
    ])

def identity_get(app):
    key = identity_key_for(app)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM identity_cache WHERE identity_key=?",
        (key,)
    ).fetchone()
    con.close()
    return dict(row) if row else None

def identity_set(app, app_label, sha256_hex):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO identity_cache(
            identity_key, package_name, version_name, last_update,
            app_label, sha256, resolved_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(identity_key) DO UPDATE SET
            app_label=excluded.app_label,
            sha256=excluded.sha256,
            resolved_at=excluded.resolved_at
    """, (
        identity_key_for(app),
        app.get("package", ""),
        app.get("version_name", ""),
        app.get("last_update", ""),
        app_label or "",
        sha256_hex or "",
        datetime.now().isoformat(timespec="seconds")
    ))
    con.commit()
    con.close()

def cache_get(sha256_hex):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM online_cache WHERE sha256=?",
        (sha256_hex,)
    ).fetchone()
    con.close()
    return dict(row) if row else None

def cache_set(sha256_hex, source, status, details=""):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO online_cache(sha256, source, status, details, checked_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(sha256) DO UPDATE SET
            source=excluded.source,
            status=excluded.status,
            details=excluded.details,
            checked_at=excluded.checked_at
    """, (
        sha256_hex,
        source,
        status,
        details,
        datetime.now().isoformat(timespec="seconds")
    ))
    con.commit()
    con.close()

def db_rep(package):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM app_reputation WHERE package_name=?", (package,)
    ).fetchone()
    con.close()
    return dict(row) if row else None

def db_seen(package, app_name):
    now = datetime.now().isoformat(timespec="seconds")
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO app_reputation(
            package_name, app_name, classification, notes,
            first_seen, last_seen, times_seen, times_removed
        )
        VALUES (?, ?, 'unknown', '', ?, ?, 1, 0)
        ON CONFLICT(package_name) DO UPDATE SET
            app_name=COALESCE(NULLIF(excluded.app_name,''), app_reputation.app_name),
            last_seen=excluded.last_seen,
            times_seen=app_reputation.times_seen+1
    """, (package, app_name, now, now))
    con.commit()
    con.close()

def db_classify(package, classification, notes, app_name):
    now = datetime.now().isoformat(timespec="seconds")
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO app_reputation(
            package_name, app_name, classification, notes,
            first_seen, last_seen, times_seen, times_removed
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        ON CONFLICT(package_name) DO UPDATE SET
            app_name=COALESCE(NULLIF(excluded.app_name,''), app_reputation.app_name),
            classification=excluded.classification,
            notes=excluded.notes,
            last_seen=excluded.last_seen
    """, (package, app_name, classification, notes, now, now))
    con.commit()
    con.close()

def db_removed(package):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE app_reputation SET times_removed=times_removed+1 WHERE package_name=?",
        (package,)
    )
    con.commit()
    con.close()

def friendly_device_name(serial):
    vals={}
    for key in ("ro.product.marketname","ro.product.vendor.marketname","ro.product.odm.marketname",
                "ro.product.model","ro.product.vendor.model","ro.product.manufacturer"):
        try:
            rc,out,err=run_adb(["-s",serial,"shell","getprop",key],timeout=8)
            if rc==0 and out.strip(): vals[key]=out.strip()
        except Exception: pass
    friendly=(vals.get("ro.product.marketname") or vals.get("ro.product.vendor.marketname") or
              vals.get("ro.product.odm.marketname") or vals.get("ro.product.model") or
              vals.get("ro.product.vendor.model") or "Android device")
    model=vals.get("ro.product.model") or vals.get("ro.product.vendor.model") or ""
    maker=vals.get("ro.product.manufacturer","").strip()
    # Some Android builds expose only the engineering model code. Use our
    # conservative local model map before falling back to that code.
    try:
        model_map=json.loads((BASE_DIR / "device_models.json").read_text(encoding="utf-8"))
    except Exception:
        model_map={}
    if model and (not friendly or friendly == model) and model in model_map:
        friendly=model_map[model]
    if maker and maker.lower() not in friendly.lower(): friendly=maker.title()+" "+friendly
    return friendly,model

def get_devices():
    code, out, err = run_adb(["devices"])
    if code:
        raise RuntimeError(err or out)
    result = []
    for line in out.splitlines()[1:]:
        if "\t" in line:
            result.append(tuple(line.split("\t", 1)))
    return result

def get_prop(serial, prop):
    code, out, _ = shell(serial, ["getprop", prop])
    return out.strip() if code == 0 else ""

def _package_name_set(serial, flag):
    code, out, _ = shell(
        serial, ["pm", "list", "packages", flag], timeout=40
    )
    if code:
        return set()
    return {
        line[len("package:"):].strip()
        for line in out.splitlines()
        if line.startswith("package:")
    }


def list_packages_fast(serial):
    # Complete installed-package inventory. Views decide what the technician sees.
    code, out, err = shell(
        serial, ["pm", "list", "packages", "-i", "-f"], timeout=60
    )
    if code:
        raise RuntimeError(err or out)

    system_packages = _package_name_set(serial, "-s")
    third_party_packages = _package_name_set(serial, "-3")

    result = []
    for line in out.splitlines():
        if not line.startswith("package:"):
            continue
        raw = line[len("package:"):]
        installer = ""
        if " installer=" in raw:
            raw, installer = raw.rsplit(" installer=", 1)
        apk_path, package = raw.rsplit("=", 1) if "=" in raw else ("", raw)
        package = package.strip()
        result.append({
            "package": package,
            "apk_path": apk_path.strip(),
            "installer": installer.strip(),
            "is_system": package in system_packages,
            "is_third_party": package in third_party_packages,
        })
    return result

def list_system_packages_fast(serial):
    """Silent system inventory. Android pm -s is the source of truth for system status."""
    code, out, err = shell(serial, ["pm", "list", "packages", "-s", "-f"], timeout=40)
    if code:
        raise RuntimeError(err or out)
    result=[]
    for line in out.splitlines():
        if not line.startswith("package:"):
            continue
        raw=line[len("package:"):]
        apk_path, package = raw.rsplit("=",1) if "=" in raw else ("",raw)
        pkg=package.strip(); path=apk_path.strip()
        low=pkg.lower()
        if low == "android" or low.startswith("com.android.") or low.startswith("com.google.android.gms") or low.startswith("com.google.android.gsf"):
            app_type="SYSTEM"
        else:
            app_type="OEM / SYSTEM"
        result.append({"package":pkg,"apk_path":path,"app_type":app_type})
    return result


def knowledge_record_system_inventory(system_rows, manufacturer, model, android_version):
    now=datetime.now().isoformat(timespec="seconds")
    scan_id="SYS"+datetime.now().strftime("%Y%m%d%H%M%S%f")
    con=sqlite3.connect(DB_PATH)
    try:
        for app in system_rows:
            pkg=app.get("package")
            if not pkg: continue
            seeded=con.execute("SELECT canonical_name,vendor,app_type,confidence FROM knowledge_seed_entries WHERE package_name=?",(pkg,)).fetchone()
            name=seeded[0] if seeded and seeded[0] else pkg
            vendor=seeded[1] if seeded and seeded[1] else manufacturer
            atype=seeded[2] if seeded and seeded[2] else app.get("app_type","OEM / SYSTEM")
            conf=int(seeded[3]) if seeded else 90
            con.execute("""INSERT INTO knowledge_apps(package_name,canonical_name,manufacturer,app_type,reputation,confidence,knowledge_source,first_seen,last_seen,times_seen,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(package_name) DO UPDATE SET
                canonical_name=CASE WHEN knowledge_apps.canonical_name IS NULL OR knowledge_apps.canonical_name=knowledge_apps.package_name THEN excluded.canonical_name ELSE knowledge_apps.canonical_name END,
                manufacturer=COALESCE(knowledge_apps.manufacturer,excluded.manufacturer), app_type=excluded.app_type,
                confidence=MAX(knowledge_apps.confidence,excluded.confidence),
                knowledge_source=CASE WHEN knowledge_apps.knowledge_source='technician' THEN knowledge_apps.knowledge_source ELSE 'device system inventory' END,
                last_seen=excluded.last_seen,updated_at=excluded.updated_at""",
                (pkg,name,vendor,atype,"UNKNOWN",conf,"device system inventory",now,now,1,now,now))
            state = con.execute(
                """SELECT id FROM system_observations
                   WHERE package_name=?
                     AND COALESCE(app_type,'')=COALESCE(?,'')
                     AND COALESCE(manufacturer,'')=COALESCE(?,'')
                     AND COALESCE(model,'')=COALESCE(?,'')
                     AND COALESCE(android_version,'')=COALESCE(?,'')
                     AND COALESCE(apk_path,'')=COALESCE(?,'')
                   ORDER BY id DESC LIMIT 1""",
                (pkg,atype,manufacturer,model,android_version,app.get("apk_path"))
            ).fetchone()
            if state:
                con.execute(
                    """UPDATE system_observations
                       SET scan_id=?, observed_at=?, source=? WHERE id=?""",
                    (scan_id,now,"adb pm list packages -s -f",state[0])
                )
            else:
                con.execute(
                    """INSERT INTO system_observations
                       (scan_id,observed_at,package_name,app_type,manufacturer,
                        model,android_version,apk_path,source)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (scan_id,now,pkg,atype,manufacturer,model,android_version,
                     app.get("apk_path"),"adb pm list packages -s -f")
                )
        con.commit()
    finally: con.close()


def knowledge_database_stats():
    con=sqlite3.connect(DB_PATH)
    try:
        apps=con.execute("SELECT COUNT(*) FROM knowledge_apps").fetchone()[0]
        obs=con.execute("SELECT COUNT(*) FROM knowledge_observations").fetchone()[0]
        sysobs=con.execute("SELECT COUNT(*) FROM system_observations").fetchone()[0]
        tech=con.execute("SELECT COUNT(*) FROM knowledge_apps WHERE knowledge_source='technician' OR reputation<>'UNKNOWN'").fetchone()[0]
        return apps,obs,sysobs,tech
    finally: con.close()

def package_details(serial, package):
    code, out, _ = shell(serial, ["dumpsys", "package", package], timeout=15)
    if code:
        return {}
    d = {}

    m = re.search(r"firstInstallTime=([^\r\n]+)", out)
    if m:
        val = m.group(1).strip()
        d["first_install"] = "Preloaded / unknown" if val.startswith("1970-") else val

    m = re.search(r"lastUpdateTime=([^\r\n]+)", out)
    if m:
        d["last_update"] = m.group(1).strip()

    m = re.search(r"versionName=([^\r\n]+)", out)
    if m:
        d["version_name"] = m.group(1).strip()

    # Popup-ad capability signals from package manifest/dumpsys output.
    # Capability is not proof that the app is malicious.
    d["requests_overlay"] = "android.permission.SYSTEM_ALERT_WINDOW" in out
    d["requests_fullscreen"] = "android.permission.USE_FULL_SCREEN_INTENT" in out
    d["requests_notifications"] = "android.permission.POST_NOTIFICATIONS" in out

    # Android ApplicationInfo category. CATEGORY_GAME is 0. Not every app sets a
    # category, so this is supporting evidence only.
    m = re.search(r"\bcategory=(-?\d+)", out)
    if m:
        try:
            d["android_category"] = int(m.group(1))
            d["is_game"] = int(m.group(1)) == 0
        except Exception:
            pass

    return d

def disabled_packages(serial):
    """Return packages Android currently reports disabled for the current user."""
    try:
        code, out, _ = shell(serial, ["pm", "list", "packages", "-d"], timeout=20)
        if code:
            return set()
        return {line.split("package:",1)[1].strip() for line in out.splitlines()
                if line.strip().startswith("package:")}
    except Exception:
        return set()

def hibernated_packages(serial, packages, android_version):
    """Best-effort Android 12+ hibernation check, batched to avoid one ADB process/app."""
    try:
        major = int(str(android_version).split(".",1)[0])
    except Exception:
        major = 0
    if major < 12 or not packages:
        return set(), False
    result=set()
    supported=False
    # The platform command requires one package at a time, but we execute many
    # remote commands inside each ADB shell to keep workshop scans responsive.
    safe=[p for p in packages if re.fullmatch(r"[A-Za-z0-9_.$-]+", p or "")]
    for start in range(0, len(safe), 60):
        batch=safe[start:start+60]
        command="; ".join(f"echo -n '{pkg} '; cmd app_hibernation get-state '{pkg}'" for pkg in batch)
        try:
            code,out,err=run_adb(["-s",serial,"shell",command], timeout=35)
        except Exception:
            continue
        text=(out+"\n"+err).lower()
        if "unknown command" in text or "can't find service" in text or "not found" in text:
            continue
        if out.strip():
            supported=True
        for line in out.splitlines():
            parts=line.strip().split()
            if len(parts)>=2 and parts[-1].lower()=="true":
                result.add(parts[0])
    return result, supported

def unused_cleanup_signal(app):
    """Describe an unused/junk-cleanup signal without calling it malware."""
    if app.get("hibernated"):
        return "HIBERNATED", "Android has hibernated this app after extended non-use"
    if app.get("disabled_by_system") and classify_app_type(app) not in ("SYSTEM","OEM / SYSTEM","UPDATED SYSTEM"):
        return "DISABLED", "App is currently disabled"
    return "", ""

def enabled_component_packages(serial, setting_key):
    code, out, _ = shell(serial, ["settings", "get", "secure", setting_key])
    if code or out in ("", "null"):
        return set()

    pkgs = set()
    for comp in out.split(":"):
        comp = comp.strip()
        if "/" in comp:
            pkgs.add(comp.split("/", 1)[0])
    return pkgs

def active_device_admin(serial):
    code, out, _ = shell(serial, ["dumpsys", "device_policy"], timeout=25)
    if code:
        return set()
    return set(re.findall(r"ComponentInfo\{([^/]+)/[^}]+\}", out))

def appops_allowed(serial, op):
    code, out, _ = shell(serial, ["appops", "query-op", op, "allow"], timeout=25)
    if code:
        return set()

    pkgs = set()
    for line in out.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        if "." in token:
            pkgs.add(token)
    return pkgs

def parse_dt(text):
    if not text or text == "Preloaded / unknown":
        return None

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    return None

def package_display_name(package):
    # v0.8 deliberately avoids invented package-tail names such as
    # "Barcelona", "Orca" or "Buyermob". Until the genuine Android label has
    # been resolved, show the technical package name instead.
    return package


def installer_name(installer):
    return RECOGNISED_INSTALLERS.get(
        installer,
        "Sideloaded / unknown"
        if installer in ("", "null", "none")
        else installer
    )

def symptom_window_days():
    return {
        "Today": 1,
        "Last 3 days": 3,
        "About a week": 10,
        "Few weeks": 30,
        "About a month": 45,
        "Unknown": 30,
    }

def find_baseline_date(apps):
    """
    Detect a likely migration/setup cluster.
    If at least 8 third-party apps were first installed on the same day,
    treat the largest cluster as the phone's baseline setup day.
    """
    dates = []
    for app in apps:
        dt = parse_dt(app.get("first_install"))
        if dt:
            dates.append(dt.date())
    if not dates:
        return None, 0

    counts = Counter(dates)
    day, count = counts.most_common(1)[0]
    if count >= 8:
        return day, count
    return None, count

def days_since(dt):
    if not dt:
        return None
    return (datetime.now() - dt).days


def learned_system_app_type(package):
    if not package:
        return None
    try:
        con=sqlite3.connect(DB_PATH)
        row=con.execute("SELECT app_type,confidence,knowledge_source FROM knowledge_apps WHERE package_name=?",(package,)).fetchone()
        con.close()
        if not row: return None
        t=(row[0] or "").strip().upper(); conf=int(row[1] or 0); src=(row[2] or "").lower()
        if t in {"SYSTEM","OEM / SYSTEM","OEM SYSTEM","UPDATED SYSTEM"} and conf>=80 and ("system inventory" in src or "authoritative" in src):
            return "OEM / SYSTEM" if t in {"OEM / SYSTEM","OEM SYSTEM"} else t
    except Exception:
        pass
    return None

def learned_oem_app_type(app):
    """Vendor identity only: OEM APP is neither a safety verdict nor system protection."""
    package=(app.get("package") or "").lower()
    installer=(app.get("installer") or "").lower()
    manufacturer=(app.get("manufacturer") or "").lower()
    samsung_pkg=package.startswith(("com.samsung.", "com.sec.", "com.samsungandroid."))
    samsung_evidence=(manufacturer=="samsung" or "samsung" in installer or "galaxy" in installer)
    return "OEM APP" if samsung_pkg and samsung_evidence else None


def classify_app_type(app):
    learned_type=learned_system_app_type(app.get("package"))
    if learned_type:
        return learned_type
    oem_type=learned_oem_app_type(app)
    if oem_type:
        return oem_type
    """Classify provenance/type independently from malware reputation."""
    pkg = (app.get("package") or "").lower()
    installer = (app.get("installer") or "").lower()
    path = (app.get("apk_path") or "").lower()
    first = app.get("first_install") or ""

    if pkg.startswith("org.chromium.webapk."):
        return "WEB APP"

    seeded = seed_entry(app.get("package") or "")
    if seeded and app.get("is_system"):
        return seeded.get("app_type") or "OEM / SYSTEM"

    # pm's system-package set is authoritative when available.
    if app.get("is_system"):
        if app.get("is_third_party"):
            return "UPDATED SYSTEM"
        core = (
            pkg == "android"
            or pkg.startswith("com.android.")
            or pkg.startswith("com.google.android.gms")
            or pkg.startswith("com.google.android.gsf")
        )
        return "SYSTEM" if core else "OEM / SYSTEM"

    preloaded = (
        first == "Preloaded / unknown"
        or path.startswith("/system/")
        or path.startswith("/product/")
        or path.startswith("/vendor/")
        or path.startswith("/system_ext/")
        or path.startswith("/apex/")
    )
    if preloaded:
        return "FACTORY PRELOAD"

    if installer in (
        "com.android.vending",
        "com.sec.android.app.samsungapps",
        "com.amazon.venezia",
    ):
        return "USER"

    if installer in (
        "",
        "null",
        "none",
        "com.google.android.packageinstaller",
        "com.android.packageinstaller",
        "com.samsung.android.packageinstaller",
    ):
        return "SIDELOADED"

    return "USER"


def reputation_label(app):
    cls = (app.get("classification") or "unknown").strip().lower()
    return {
        "safe": "KNOWN SAFE",
        "suspicious": "SUSPICIOUS",
        "malware": "KNOWN MALWARE",
    }.get(cls, "UNKNOWN")


def effective_reputation_label(app):
    """Return local technician reputation first, then shared cross-store reputation.

    Shared Knowledge is deliberately read-only evidence here: it changes the
    effective reputation shown/triaged on this PC without pretending the local
    technician classified the app.
    """
    local = reputation_label(app)
    if local != "UNKNOWN":
        return local
    net = shared_info(app.get("package") or "")
    shared = str(net.get("reputation") or "UNKNOWN").strip().upper()
    if shared in ("KNOWN SAFE", "SUSPICIOUS", "KNOWN MALWARE"):
        app["shared_reputation"] = shared
        app["shared_match"] = "package"
        return shared

    # Cross-store malware can also be recovered after AAPT2 resolves the real
    # label. This fixes package-variant cases such as Smart Clean Pro without
    # ever declaring an app Safe from a name-only match.
    by_name = shared_malware_info_by_name(app.get("app_name"))
    if by_name:
        app["shared_reputation"] = "KNOWN MALWARE"
        app["shared_match"] = "resolved app name"
        app["shared_matched_package"] = by_name.get("package_name", "")
        return "KNOWN MALWARE"

    app["shared_reputation"] = "UNKNOWN"
    app["shared_match"] = ""
    return "UNKNOWN"


def protected_app_type(app):
    return classify_app_type(app) in (
        "SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM"
    )

RISK_RULES_PATH = BASE_DIR / "risk_rules.json"

def load_risk_rules():
    try:
        return json.loads(RISK_RULES_PATH.read_text(encoding="utf-8")).get("categories", [])
    except Exception:
        return []

def package_prefilter_signals(app):
    """Cheap package-name hints used only to decide which APK labels to resolve.

    These hints NEVER classify an app or put it into Cleanup by themselves. They
    break the chicken-and-egg problem where a suspicious category is only obvious
    after AAPT2 resolves the human-visible app label.
    """
    pkg = str(app.get("package") or "").lower()
    if not pkg:
        return []
    terms = (
        "clean", "cleaner", "cleanup", "boost", "booster", "optimizer", "optimiser",
        "antivirus", "virus", "securityclean", "qrscan", "qrscanner", "qrcode",
        "barcode", "pdfreader", "pdfviewer", "documentreader", "flashlight",
        "torchlight", "photorecovery", "filerecovery", "datarecovery", "launcher",
        "recoverphoto", "junkclean", "cacheclean", "phonemaster"
    )
    return [t for t in terms if t in pkg]



def discovery_resolution_candidates(apps, baseline_date, limit=100):
    """Choose app labels that must be resolved before final Cleanup triage.

    v0.13.7 makes *new installs deterministic*: every non-system app genuinely
    installed in the last 14 days is resolved, regardless of package name or the
    normal discovery cap. This closes the Smart Clean Pro hole where an innocent-
    looking developer package hid a risky human-visible label.

    Older discovery candidates are still bounded. Membership here is discovery
    only and never makes an app suspicious by itself.
    """
    now = datetime.now()
    mandatory = []
    ranked = []
    for app in apps:
        if app.get("app_type") in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM"):
            continue

        installed = parse_dt(app.get("first_install"))
        in_baseline = bool(baseline_date and installed and installed.date() == baseline_date)
        if in_baseline:
            continue

        age = (now - installed) if installed else None
        # New installs are the highest-value discovery set and are NEVER allowed
        # to be crowded out by 100 older package-name hints.
        if age is not None and timedelta(0) <= age <= timedelta(days=14):
            mandatory.append(app)
            continue

        pkg_hint = bool(package_prefilter_signals(app))
        candidate = bool(app.get("cleanup_candidate"))
        special = bool(app.get("active_special"))
        sideload = app.get("app_type") == "SIDELOADED"
        recent = bool(age is not None and timedelta(0) <= age <= timedelta(days=45))
        post_baseline = bool(baseline_date and installed and installed.date() > baseline_date)

        if not (candidate or pkg_hint or special or sideload or recent or post_baseline):
            continue

        # For the bounded secondary set, favour newest installs before generic
        # package hints so recent customer-installed apps cannot be starved.
        rank = (
            installed or datetime.min,
            1 if candidate else 0,
            1 if special else 0,
            1 if sideload else 0,
            1 if pkg_hint else 0,
        )
        ranked.append((rank, app))

    mandatory.sort(key=lambda a: parse_dt(a.get("first_install")) or datetime.min, reverse=True)
    ranked.sort(key=lambda x: x[0], reverse=True)

    seen = set()
    result = []
    for app in mandatory + [app for _, app in ranked[:limit]]:
        pkg = app.get("package")
        if pkg and pkg not in seen:
            seen.add(pkg)
            result.append(app)
    return result

def high_risk_signals(app):
    """Return [(label, score)] workshop review signals. Never changes reputation.

    Prefer the resolved Android label for category matching. Package-name matching is
    deliberately conservative because innocent packages often contain generic words.
    """
    name = str(app.get("app_name") or "")
    pkg = str(app.get("package") or "")
    name_l = name.lower()
    pkg_l = pkg.lower()
    found = []

    # Names padded/punctuated to sort conspicuously at the top of Android's app list.
    # Keep this separate from ordinary category matching because it is a useful PUP/adware clue.
    if name:
        if name[:1].isspace():
            found.append(("App name starts with a space", 40))
        elif name.startswith("#"):
            found.append(("App name starts with #", 40))
        elif name[0] in ("!", ".", "_", "-"):
            found.append(("App name starts with sorting punctuation", 32))

    for rule in load_risk_rules():
        label = rule.get("label", "High-risk category")
        score = int(rule.get("score", 25))
        # Human-visible label is the strongest category evidence.
        name_terms = rule.get("name_terms", rule.get("terms", []))
        package_terms = rule.get("package_terms", [])
        name_hit = any(str(t).lower() in name_l for t in name_terms)
        # Some junk cleaners deliberately use a generic standalone "Clean" token
        # (for example "Smart Clean Pro") rather than "Cleaner". Match CLEAN
        # only as a whole word in the human-visible label; never use this broad
        # token against package names, where it would create false positives.
        if str(rule.get("id", "")) == "cleaner" and re.search(r"(?i)(?:^|[^a-z0-9])clean(?:$|[^a-z0-9])", name):
            name_hit = True
        if name_hit:
            found.append((label, score))
        elif any(str(t).lower() in pkg_l for t in package_terms):
            found.append((label, max(18, score - 6)))

    out = {}
    for label, score in found:
        out[label] = max(score, out.get(label, 0))
    return list(out.items())

def is_cleanup_candidate(app, onset_label="Unknown"):
    """Conservative main Cleanup gate; broad signals remain in Deep Triage."""
    classification = str(app.get("classification", "unknown")).strip().lower()
    reputation = str(app.get("reputation", "UNKNOWN")).strip().upper()
    online = str(app.get("online_status", "")).strip().upper()
    app_type = str(app.get("app_type", "")).strip().upper()
    priority = str(app.get("priority", "INFO")).strip().upper()
    reason = str(app.get("reason", "")).lower()

    # Explicit technician Suspicious/Malware decisions remain actionable.
    if classification in ("suspicious", "malware"):
        return True

    # Exact external malware evidence is allowed to override an earlier Safe decision.
    if online.startswith("MATCH"):
        return True

    # Effective reputation is authoritative for the action queue.  This includes
    # Shared Knowledge downloaded on a fresh/cross-PC database.  Previously a
    # shared KNOWN MALWARE row could correctly retriage to CRITICAL, but then
    # fall back out of Cleanup because this gate only looked for heuristic
    # reasons.  Keep the reputation decision explicit here.
    if reputation == "KNOWN MALWARE":
        return True
    if reputation == "SUSPICIOUS":
        return True

    # Learned Safe is an absolute heuristic exclusion.
    if classification == "safe" or reputation == "KNOWN SAFE":
        return False

    # System/OEM and non-actionable priority rows never leak into Cleanup.
    if app_type in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM"):
        return False
    # Main Cleanup is intentionally action-oriented: only CRITICAL/HIGH rows
    # appear here. CHECK is a separate Review queue so staff cannot accidentally
    # bulk-remove ordinary user-installed apps that merely deserve a look.
    if priority not in ("CRITICAL", "HIGH"):
        return False

    # Unknown sideloaded user apps are useful workshop evidence.
    # Sideloading is not a malware verdict: surface it as CHECK for technician
    # review. Learned Safe was already excluded above.
    if app_type == "SIDELOADED" and "sideloaded / installer unknown" in reason:
        return True

    # Concrete powerful-access evidence.
    privilege_terms = (
        "accessibility", "notification access", "device admin",
        "overlay", "unknown apps", "install packages"
    )
    if any(x in reason for x in privilege_terms):
        return True

    # Deliberately configured workshop high-risk categories / naming tricks.
    category_terms = (
        "qr code", "qr scanner", "cleaner", "antivirus", "anti-virus",
        "pdf reader", "flashlight", "photo recovery", "launcher",
        "leading #", "leading space", "starts with #", "starts with space",
        "high-risk category", "high risk category"
    )
    if any(x in reason for x in category_terms):
        return True

    # Timing only becomes Cleanup evidence when the technician supplied onset.
    if onset_label != "Unknown":
        # Only a genuine INSTALL in the selected problem window can create a
        # timing-only Cleanup finding. Recent updates are supporting evidence only.
        if "installed during reported problem window" in reason:
            return True

    return False


def popup_ad_assessment(app, special):
    """Assess *meaningful* popup-ad capability; this is not a malware verdict.

    Declared permissions are deliberately weak evidence. Many legitimate apps
    declare overlay/full-screen capabilities without having active access.
    MEDIUM/HIGH therefore require active access or correlated evidence.
    """
    pkg = app.get("package", "")
    if classify_app_type(app) in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM"):
        return "SYSTEM", []

    active_overlay = pkg in special.get("overlay", set())
    active_accessibility = pkg in special.get("accessibility", set())
    active_notification = pkg in special.get("notification", set())
    declared_overlay = bool(app.get("requests_overlay"))
    declared_fullscreen = bool(app.get("requests_fullscreen"))
    risky_category = bool(high_risk_signals(app))

    reasons = []

    # Active draw-over-apps is the clearest direct popup capability we can see.
    if active_overlay:
        reasons.append("Draw-over-apps access is active")
        if active_accessibility:
            reasons.append("Accessibility is also active")
        if risky_category:
            reasons.append("High-risk app category")
        return "HIGH", reasons

    # Accessibility is extremely powerful. It becomes HIGH for an app that also
    # has popup/full-screen capability or belongs to a risky junk/adware class.
    if active_accessibility:
        reasons.append("Accessibility is active")
        if declared_overlay:
            reasons.append("Declares draw-over-apps capability")
        if declared_fullscreen:
            reasons.append("Declares full-screen intent")
        if risky_category:
            reasons.append("High-risk app category")
        if declared_overlay or declared_fullscreen or risky_category:
            return "HIGH", reasons
        return "MEDIUM", reasons

    # Notification-listener access alone is not popup evidence. Correlate it
    # with a popup capability/category before surfacing it to technicians.
    if active_notification and (declared_overlay or declared_fullscreen or risky_category):
        reasons.append("Notification access is active")
        if declared_overlay:
            reasons.append("Declares draw-over-apps capability")
        if declared_fullscreen:
            reasons.append("Declares full-screen intent")
        if risky_category:
            reasons.append("High-risk app category")
        return "MEDIUM", reasons

    # Two independent static signals are worth a LOW note, but never MEDIUM.
    if declared_overlay and declared_fullscreen:
        return "LOW", ["Declares draw-over-apps capability", "Declares full-screen intent"]
    if declared_overlay and risky_category:
        return "LOW", ["Declares draw-over-apps capability", "High-risk app category"]
    if declared_fullscreen and risky_category:
        return "LOW", ["Declares full-screen intent", "High-risk app category"]

    # A single declared permission is too common to be useful in the workshop UI.
    return "NONE", []

def triage_app(app, rep, special, baseline_date, onset_label):
    """
    Technician-oriented triage.
    Returns:
      priority: CRITICAL / HIGH / CHECK / INFO / BASELINE
      score: internal ranking score only
      reasons: list of human-readable reasons
    """
    if rep and rep.get("classification") == "malware":
        return "CRITICAL", 100, ["Known malware from local reputation database"]

    if rep and rep.get("classification") == "suspicious":
        return "HIGH", 80, ["Previously flagged suspicious"]

    if rep and rep.get("classification") == "safe":
        return "INFO", 0, ["Known safe"]

    # Cross-store Shared Knowledge is effective reputation evidence, but does
    # not masquerade as a local technician decision. This is what lets a fresh
    # shop PC immediately recognise an app learned by another store.
    effective_rep = str(app.get("reputation", "UNKNOWN")).strip().upper()
    if effective_rep == "KNOWN MALWARE":
        source = "shared knowledge database" if app.get("shared_reputation") == "KNOWN MALWARE" else "knowledge database"
        if app.get("shared_match") == "resolved app name":
            return "CRITICAL", 100, [f"Known malware from {source} (matched resolved app name)"]
        return "CRITICAL", 100, [f"Known malware from {source}"]
    if effective_rep == "SUSPICIOUS":
        source = "shared knowledge database" if app.get("shared_reputation") == "SUSPICIOUS" else "knowledge database"
        return "HIGH", 80, [f"Previously flagged suspicious in {source}"]

    # Permanent knowledge can know an app is safe even when a legacy/local
    # reputation row is absent (for example after importing a knowledge DB).
    if str(app.get("reputation", "")).strip().upper() == "KNOWN SAFE":
        if app.get("shared_reputation") == "KNOWN SAFE":
            return "INFO", 0, ["Known safe from shared knowledge database"]
        return "INFO", 0, ["Known safe"]

    online_status = app.get("online_status", "")
    if online_status.startswith("MATCH"):
        family = online_status.partition(":")[2].strip()
        detail = "Exact APK hash found in MalwareBazaar"
        if family:
            detail += f" ({family})"
        return "CRITICAL", 95, [detail]

    pkg = app["package"]
    installer = app.get("installer", "")
    app_type = classify_app_type(app)
    name_blob = (app.get("app_name", "") + " " + pkg).lower()

    score = 0
    reasons = []

    system_trusted = app_type in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM")
    if system_trusted:
        # Device-confirmed system/OEM packages are outside ordinary cleanup
        # heuristics. Their platform-granted privileges are expected and must
        # not create Cleanup candidates.
        app["risk_signals"] = []

        # Preserve explicit learned malware/suspicious intelligence as the only
        # reason a system package can be elevated automatically.
        rep_value = (rep or {}).get("classification", "") if isinstance(rep, dict) else ""
        rep_norm = str(rep_value).strip().upper()
        if rep_norm in ("MALWARE", "KNOWN MALWARE"):
            return "CRITICAL", 100, ["Known malware reputation on system/OEM package"]
        if rep_norm == "SUSPICIOUS":
            return "CHECK", 60, ["Technician-classified suspicious system/OEM package"]

        return "INFO", 0, ["System/OEM package"]

    # Workshop high-risk categories are review signals only. Known-safe
    # technician reputation has already returned above and therefore suppresses them.
    risk_signals = [] if system_trusted else high_risk_signals(app)
    app["risk_signals"] = [label for label, _pts in risk_signals]
    for label, pts in risk_signals:
        score += pts
        reasons.append("High-risk category: " + label)

    popup_level, popup_reasons = popup_ad_assessment(app, special)
    app["popup_risk"] = popup_level
    app["popup_reasons"] = popup_reasons
    if popup_level == "HIGH":
        score += 25
        reasons.append("High popup-ad risk: " + ", ".join(popup_reasons))
    elif popup_level == "MEDIUM":
        score += 10
        reasons.append("Popup-ad capability: " + ", ".join(popup_reasons))

    # Active powerful access.
    if pkg in special["accessibility"]:
        score += 55
        reasons.append("Accessibility service is enabled")

    if pkg in special["device_admin"]:
        score += 50
        reasons.append("Device administrator is active")

    if pkg in special["notification"]:
        score += 20
        reasons.append("Notification access is enabled")

    if pkg in special["overlay"]:
        score += 18
        reasons.append("Can draw over other apps")

    if pkg in special["install_unknown"]:
        score += 18
        reasons.append("Can install unknown apps")

    # Installation provenance.
    sideloaded = installer in (
        "", "null", "none",
        "com.google.android.packageinstaller",
        "com.android.packageinstaller",
        "com.samsung.android.packageinstaller",
    )

    if sideloaded and app_type == "SIDELOADED":
        score += 30
        reasons.append("Sideloaded / installer unknown")

    # Category/name patterns. These do not mean malware by themselves,
    # but are useful workshop triage signals.
    category_rules = [
        (("mining", "crypto", "bitcoin", "coin", "gold"),
         18, "Mining/crypto/reward style app"),
        (("wallpaper", "browser"),
         10, "Category commonly seen in adware cases"),
        (("update", "updater"),
         10, "Generic updater naming"),
    ]

    if not system_trusted:
        for terms, pts, reason in category_rules:
            if any(term in name_blob for term in terms):
                score += pts
                reasons.append(reason)
                break

    # Installation timing relative to technician-selected symptom onset.
    installed_dt = parse_dt(app.get("first_install"))
    window = symptom_window_days()[onset_label]

    if installed_dt and not system_trusted:
        age_days = max(0, (datetime.now() - installed_dt).days)

        if onset_label != "Unknown" and age_days <= window:
            score += 30
            reasons.append(
                f"Installed during reported problem window ({onset_label.lower()})"
            )
        elif onset_label == "Unknown" and age_days <= 30:
            score += 12
            reasons.append("Installed within the last 30 days")

        # Apps installed well after the detected setup/migration cluster are outliers.
        if baseline_date and installed_dt.date() > baseline_date:
            delta = (installed_dt.date() - baseline_date).days
            if delta >= 7:
                score += 10
                reasons.append("Installed after the phone's main setup/migration cluster")

    # Update timing is SUPPORTING evidence only. Play Store auto-updates are far
    # too common to make an ordinary old app enter Cleanup just because the
    # technician selected "Last 3 days". A recent update only adds weight when
    # the app already has an independent concern (risky category, sideload,
    # active powerful access, or learned bad reputation).
    updated_dt = parse_dt(app.get("last_update"))
    independent_concern = bool(risk_signals) or sideloaded or any(
        x in reasons for x in (
            "Accessibility service is enabled", "Device administrator is active",
            "Notification access is enabled", "Can draw over other apps",
            "Can install unknown apps"
        )
    ) or str((rep or {}).get("classification", "")).strip().lower() in ("suspicious", "malware")
    if updated_dt and not system_trusted and independent_concern:
        update_age = max(0, (datetime.now() - updated_dt).days)
        if onset_label != "Unknown" and update_age <= window:
            score += 10
            reasons.append(
                f"Recently updated during reported problem window ({onset_label.lower()})"
            )
        elif onset_label == "Unknown" and update_age <= 7:
            score += 5
            reasons.append("Recently updated (supporting evidence)")

    # Correlated evidence matters more than any single generic clue. For example,
    # a cleaner installed during the reported problem window, or a sideloaded app
    # holding Accessibility, deserves stronger review than either fact alone.
    if onset_label != "Unknown" and not system_trusted:
        timing_hit = any("reported problem window" in r.lower() for r in reasons)
        category_hit = bool(risk_signals)
        powerful_hit = any(x in reasons for x in (
            "Accessibility service is enabled", "Device administrator is active",
            "Notification access is enabled", "Can draw over other apps",
            "Can install unknown apps"
        ))
        if timing_hit and (category_hit or sideloaded):
            score += 15
            reasons.append("Multiple indicators line up with the reported start time")
        if sideloaded and powerful_hit:
            score += 15
            reasons.append("Sideloaded app also has powerful access")

    # Store provenance is context only. It should not erase other evidence.
    if installer == "com.android.vending":
        reasons.append("Installed from Google Play")
    elif installer == "com.sec.android.app.samsungapps":
        reasons.append("Installed from Galaxy Store")

    # Baseline cluster itself should generally be deprioritised unless other signals exist.
    in_baseline = bool(
        baseline_date and installed_dt and installed_dt.date() == baseline_date
    )

    if in_baseline and score < 25:
        return "BASELINE", score, ["Part of the phone's main setup/migration cluster"]

    if score >= 70:
        priority = "CRITICAL"
    elif score >= 45:
        priority = "HIGH"
    elif score >= 20:
        priority = "CHECK"
    else:
        priority = "INFO"

    if not reasons:
        reasons.append("No strong indicators")

    return priority, score, reasons

class Cleaner(ctk.CTk):
    def __init__(self):
        resolver_log("BUILD MARKER Android Cleaner v1.2.14 Scanner Icons UI Polish loaded")
        self.appearance_mode = "Dark"
        self.checked_packages = set()
        super().__init__()
        self.title(APP_NAME)
        self.option_add("*Font", ("Segoe UI", 9))
        style=ttk.Style(self)
        try: style.theme_use("vista")
        except Exception: pass
        style.configure("Treeview", rowheight=40)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TButton", padding=(8,5))
        style.configure("TMenubutton", padding=(8,5))
        self.geometry("1550x850")
        self.minsize(1150, 680)
        init_db()
        apply_production_defaults()

        self.all_apps = []
        self.rows = {}
        self.device_serial = None
        self.pending_repair_group = None
        self.pending_repair_apps = []
        self._open_repair_outcome_after_scan = False
        self.baseline_date = None
        self.baseline_count = 0
        self._device_refresh_running = False
        self._known_ready_serials = set()
        self._selected_serial = None
        self._scan_generation = 0
        self._auto_scan_pending = False
        self._last_shared_sync = None
        self._shared_sync_running = False
        self._shared_sync_pending_force = False

        self.view_var = tk.StringVar(value="Cleanup")
        self.count_var = tk.StringVar(value="Showing 0 apps • 0 selected")
        self.onset_var = tk.StringVar(value="Unknown")

        self.build()
        self.after(100, self.ensure_first_run_configuration)
        self.after(350, self.refresh_devices)
        self.after(2500, self._device_poll)
        if shared_configured():
            self.after(700, lambda: self.production_sync("startup"))
        self.after(1800, self.check_for_updates)
        self.after(50, self.apply_theme)

    def _startup_shared_sync(self):
        self.production_sync("startup")

    def production_sync(self, reason="manual", force=False):
        """Offline-first production sync. Upload local evidence, then pull shared verdicts.
        Rate-limited so the device poll never hammers Apps Script."""
        if not shared_configured() or CROSS_PC_TEST_MODE:
            return
        now=datetime.now()
        if self._shared_sync_running:
            # Repair outcomes/removals are important transaction boundaries. If a
            # normal sync is already in flight, remember that a forced sync is
            # required immediately afterwards instead of silently dropping it.
            if force:
                self._shared_sync_pending_force = True
            return
        if not force and self._last_shared_sync and (now-self._last_shared_sync).total_seconds() < 300:
            return
        self._shared_sync_running=True
        def worker():
            try:
                up=shared_push_local_snapshot()
                n=shared_pull()
                self._last_shared_sync=datetime.now()
                resolver_log(f"Shared Knowledge production sync ({reason}): {up} uploaded, {n} downloaded")
                if self.all_apps:
                    self.after(0, self.retriage)
            except Exception as e:
                resolver_log(f"Shared Knowledge production sync failed ({reason}): {e}")
            finally:
                self._shared_sync_running=False
                if self._shared_sync_pending_force:
                    self._shared_sync_pending_force=False
                    self.after(0, lambda: self.production_sync("queued-important-event", force=True))
        threading.Thread(target=worker,daemon=True).start()

    def ensure_first_run_configuration(self):
        st=load_settings()
        if st.get("first_run_complete") and st.get("shared_knowledge_store_id"):
            return
        win=tk.Toplevel(self); win.title("Android Cleaner - Initial Setup"); win.geometry("560x430"); win.transient(self); win.grab_set()
        ttk.Label(win,text="Set up this workshop PC",font=("Segoe UI",14,"bold")).pack(anchor="w",padx=18,pady=(18,5))
        ttk.Label(win,text="This is a one-time setup. Give this PC a clear identity. The company Admin PIN is already built in; Shared Knowledge and Android tools are checked automatically.",wraplength=520).pack(anchor="w",padx=18,pady=(0,15))
        form=ttk.Frame(win); form.pack(fill="x",padx=18)
        ttk.Label(form,text="Store").grid(row=0,column=0,sticky="w",pady=6)
        store=tk.StringVar(value=st.get("store_name") or "Belmont")
        ttk.Combobox(form,textvariable=store,state="readonly",values=("Belmont","Ballarat","Lara","Drysdale","Home / Test"),width=24).grid(row=0,column=1,sticky="w",pady=6)
        ttk.Label(form,text="Computer name").grid(row=1,column=0,sticky="w",pady=6)
        pc=tk.StringVar(value=st.get("computer_name") or "Front Counter")
        ttk.Entry(form,textvariable=pc,width=28).grid(row=1,column=1,sticky="w",pady=6)
        cfg=production_config()
        api=tk.StringVar(value=st.get("shared_knowledge_api_key") or cfg.get("shared_knowledge_api_key") or "")
        if not api.get():
            ttk.Label(form,text="Shared API key").grid(row=2,column=0,sticky="w",pady=6)
            ttk.Entry(form,textvariable=api,width=36,show="•").grid(row=2,column=1,sticky="w",pady=6)
        adb_ok=any(x.exists() for x in ADB_CANDIDATES if isinstance(x,Path))
        aapt_ok=any(x.exists() for x in AAPT_CANDIDATES if isinstance(x,Path))
        dep=tk.StringVar(value=f"Android tools: {'Ready' if adb_ok and aapt_ok else 'Setup required'}")
        shared=tk.StringVar(value="Shared Knowledge: ready to test" if (st.get("shared_knowledge_url") or cfg.get("shared_knowledge_url")) else "Shared Knowledge: configuration missing")
        ttk.Separator(win).pack(fill="x",padx=18,pady=14)
        ttk.Label(win,textvariable=dep).pack(anchor="w",padx=18,pady=3)
        ttk.Label(win,textvariable=shared).pack(anchor="w",padx=18,pady=3)
        msg=tk.StringVar(value="")
        ttk.Label(win,textvariable=msg,wraplength=520).pack(anchor="w",padx=18,pady=8)
        def finish():
            name=pc.get().strip(); location=store.get().strip()
            if not name: msg.set("Enter a computer name."); return
            st2=load_settings(); st2["store_name"]=location; st2["computer_name"]=name
            st2["shared_knowledge_store_id"]=f"{location} - {name}"
            if api.get().strip(): st2["shared_knowledge_api_key"]=api.get().strip()
            st2["first_run_complete"]=True; save_settings(st2)
            win.destroy()
            if shared_configured(): self.production_sync("first-run",force=True)
        ttk.Button(win,text="Finish Setup",command=finish,style="Primary.TButton").pack(side="bottom",fill="x",padx=18,pady=18)
        win.protocol("WM_DELETE_WINDOW", finish)


    @staticmethod
    def _update_ssl_context():
        """Verified TLS context for GitHub update traffic in frozen Windows builds."""
        return ssl.create_default_context(cafile=certifi.where())

    @staticmethod
    def _update_error_text(exc):
        if isinstance(exc, urllib.error.HTTPError):
            return f"GitHub returned HTTP {exc.code} ({exc.reason})."
        if isinstance(exc, urllib.error.URLError):
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ssl.SSLCertVerificationError):
                return "SSL certificate verification failed while connecting to GitHub."
            return f"Could not connect to GitHub: {reason}"
        if isinstance(exc, ssl.SSLCertVerificationError):
            return "SSL certificate verification failed while connecting to GitHub."
        return str(exc) or exc.__class__.__name__

    def _github_release_api(self, channel="Production"):
        repo = "simonchunk/androidcleaner"
        headers = {"Accept":"application/vnd.github+json", "User-Agent":f"The-iPhone-Guy-Android-Cleaner/{APP_VERSION}"}
        if str(channel).lower() == "test":
            req=urllib.request.Request(f"https://api.github.com/repos/{repo}/releases?per_page=20", headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=self._update_ssl_context()) as r:
                releases=json.loads(r.read().decode("utf-8"))
            releases=[x for x in releases if not x.get("draft")]
            return releases[0] if releases else None
        req=urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10, context=self._update_ssl_context()) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    @staticmethod
    def _version_tuple(v):
        nums=[int(x) for x in re.findall(r"\d+", str(v))[:4]]
        return tuple(nums + [0] * (4-len(nums)))

    def _show_update_release(self, release, manual=False):
        if not release:
            if manual:
                messagebox.showinfo("Updates", "No published GitHub release is available on this update channel yet.")
            return
        tag=str(release.get("tag_name") or release.get("name") or "").strip()
        latest=tag.lstrip("vV")
        if not latest or self._version_tuple(latest) <= self._version_tuple(APP_VERSION):
            if manual:
                messagebox.showinfo("Updates", f"Android Cleaner {APP_VERSION} is up to date.")
            return
        notes=str(release.get("body") or "Update available.").strip()
        if len(notes) > 900:
            notes=notes[:897]+"..."
        required="[required]" in notes.lower()
        notes=re.sub(r"(?i)\[required\]", "", notes).strip()
        assets=release.get("assets") or []
        installer=next((a for a in assets if str(a.get("name","")).lower().endswith(".exe")), None)
        zip_asset=next((a for a in assets if str(a.get("name","")).lower().endswith(".zip")), None)
        asset=installer or zip_asset
        prompt=(f"Android Cleaner {latest} is available{' and is marked REQUIRED' if required else ''}.\n\n{notes or 'Update available.'}")
        if asset:
            prompt += f"\n\nDownload {asset.get('name')} now?"
            if messagebox.askyesno("Android Cleaner Update", prompt):
                self._download_github_update(release, asset)
        else:
            prompt += "\n\nThis release has no Windows installer/ZIP asset attached yet."
            messagebox.showinfo("Android Cleaner Update", prompt)

    def _download_github_update(self, release, asset):
        url=str(asset.get("browser_download_url") or "")
        name=Path(str(asset.get("name") or "AndroidCleanerUpdate.bin")).name
        if not url:
            messagebox.showerror("Update", "The GitHub release does not contain a valid download URL.")
            return
        def worker():
            try:
                update_dir=DATA_DIR / "Updates"
                update_dir.mkdir(parents=True, exist_ok=True)
                dest=update_dir / name
                req=urllib.request.Request(url, headers={"User-Agent":f"The-iPhone-Guy-Android-Cleaner/{APP_VERSION}"})
                with urllib.request.urlopen(req, timeout=30, context=self._update_ssl_context()) as r, open(dest,"wb") as f:
                    shutil.copyfileobj(r,f)
                assets=release.get("assets") or []
                sha_asset=next((a for a in assets if str(a.get("name","")).lower() in (name.lower()+".sha256", "sha256sums.txt")), None)
                verified=False
                if sha_asset and sha_asset.get("browser_download_url"):
                    sr=urllib.request.Request(sha_asset["browser_download_url"], headers={"User-Agent":f"The-iPhone-Guy-Android-Cleaner/{APP_VERSION}"})
                    with urllib.request.urlopen(sr, timeout=15, context=self._update_ssl_context()) as r:
                        txt=r.read().decode("utf-8",errors="replace")
                    actual=hashlib.sha256(dest.read_bytes()).hexdigest().lower()
                    expected=None
                    for line in txt.splitlines():
                        if name.lower() in line.lower() or len(txt.splitlines()) == 1:
                            m=re.search(r"\b[a-fA-F0-9]{64}\b", line)
                            if m: expected=m.group(0).lower(); break
                    if not expected or not hmac.compare_digest(actual, expected):
                        try: dest.unlink()
                        except Exception: pass
                        raise RuntimeError("SHA-256 verification failed. The downloaded update was deleted.")
                    verified=True
                self.after(0, lambda:self._update_download_complete(dest, verified))
            except Exception as e:
                resolver_log("Update download failed: "+str(e))
                self.after(0, lambda e=e: messagebox.showerror("Update Failed", str(e)))
        threading.Thread(target=worker,daemon=True).start()

    def _update_download_complete(self, dest, verified):
        suffix=dest.suffix.lower()
        verify_text="SHA-256 verified." if verified else "No SHA-256 file was attached to this GitHub release, so it will not be executed automatically."
        if suffix == ".exe" and verified:
            if messagebox.askyesno("Update Downloaded", f"Update downloaded successfully.\n\n{verify_text}\n\nInstall now? Android Cleaner will close."):
                try:
                    # Hand the verified installer to Windows as a separate process, then
                    # terminate this PyInstaller process completely.  The installer does
                    # not auto-launch the new EXE; this avoids a transient _MEI/Python DLL
                    # collision seen when upgrading a running one-file build.
                    subprocess.Popen([str(dest)], cwd=str(dest.parent), close_fds=True)
                    self.destroy()
                    self.after_idle(lambda: None)
                except Exception as e:
                    messagebox.showerror("Update", f"Could not start installer: {e}")
        else:
            messagebox.showinfo("Update Downloaded", f"Saved to:\n{dest}\n\n{verify_text}\n\nZIP/development builds are not installed automatically. Production EXE installers with SHA-256 verification will be one-click.")

    def check_for_updates(self, manual=False):
        st=load_settings()
        channel=str(st.get("update_channel") or "Production").strip().title()
        if channel not in ("Production","Test"):
            channel="Production"
        def worker():
            try:
                release=self._github_release_api(channel)
                self.after(0, lambda:self._show_update_release(release, manual))
            except Exception as e:
                detail=self._update_error_text(e)
                resolver_log("Update check failed: "+repr(e))
                if manual:
                    self.after(0, lambda detail=detail: messagebox.showwarning("Updates", f"Could not check GitHub for updates.\n\n{detail}\n\nAndroid Cleaner will continue to work offline."))
        threading.Thread(target=worker,daemon=True).start()

    def set_update_channel(self):
        if not self.admin_is_unlocked():
            return
        st=load_settings(); current=str(st.get("update_channel") or "Production").title()
        choice=simpledialog.askstring("Update Channel", "Enter Production or Test:\n\nProduction = store-approved releases\nTest = newest non-draft release, including prereleases", initialvalue=current, parent=self)
        if choice is None: return
        choice=choice.strip().title()
        if choice not in ("Production","Test"):
            messagebox.showerror("Update Channel", "Choose Production or Test."); return
        st["update_channel"]=choice; save_settings(st)
        messagebox.showinfo("Update Channel", f"This PC now uses the {choice} update channel.")

    def admin_is_unlocked(self):
        return time.time() < getattr(self, "_admin_unlocked_until", 0)

    def verify_admin_pin(self, pin):
        try:
            candidate = hashlib.pbkdf2_hmac(
                "sha256", str(pin).encode("utf-8"), bytes.fromhex(ADMIN_PIN_SALT), ADMIN_PIN_ITERATIONS
            ).hex()
            return hmac.compare_digest(candidate, ADMIN_PIN_HASH)
        except Exception:
            return False

    def request_admin_mode(self):
        if self.admin_is_unlocked():
            self._admin_unlocked_until = time.time() + ADMIN_SESSION_SECONDS
            self.rebuild_advanced_menu()
            return True
        pin = simpledialog.askstring("Admin Mode", "Enter company admin PIN:", show="•", parent=self)
        if pin is None:
            return False
        if not self.verify_admin_pin(pin.strip()):
            messagebox.showerror("Admin Mode", "Incorrect admin PIN.")
            return False
        self._admin_unlocked_until = time.time() + ADMIN_SESSION_SECONDS
        self.rebuild_advanced_menu()
        messagebox.showinfo("Admin Mode", "Admin Mode unlocked for 15 minutes on this PC.")
        return True

    def lock_admin_mode(self):
        self._admin_unlocked_until = 0
        self.rebuild_advanced_menu()

    def rebuild_advanced_menu(self):
        menu = getattr(self, "advanced_menu", None)
        if menu is None:
            return
        menu.delete(0, "end")
        menu.add_command(label="Check for Updates", command=lambda:self.check_for_updates(manual=True))
        menu.add_separator()
        if not self.admin_is_unlocked():
            menu.add_command(label="Admin Mode…", command=self.request_admin_mode)
            return
        menu.add_command(label="Lock Admin Mode", command=self.lock_admin_mode)
        menu.add_separator()
        menu.add_command(label="Refresh Devices", command=self.refresh_devices)
        menu.add_command(label="Scan Device", command=self.scan)
        menu.add_separator()
        menu.add_command(label="Deep Triage", command=lambda:self.set_view("Deep Triage"))
        menu.add_command(label="Recent Installs", command=lambda:self.set_view("Recent Installs"))
        menu.add_command(label="All Apps", command=lambda:self.set_view("All Apps"))
        menu.add_separator()
        menu.add_command(label="Resolve All App Names", command=self.resolve_all_names)
        menu.add_command(label="Resolver Log", command=self.open_resolver_log)
        menu.add_command(label="ADB Audit Log", command=self.open_adb_log)
        menu.add_command(label="Record Repair Outcome (manual)", command=self.record_repair_outcome)
        menu.add_separator()
        menu.add_command(label="Knowledge Database", command=self.open_knowledge_db)
        menu.add_command(label="Shared Knowledge", command=self.open_shared_knowledge)
        menu.add_command(label="Update Channel (Production/Test)", command=self.set_update_channel)
        menu.add_command(label="Export Knowledge DB", command=self.export_knowledge_db_ui)
        menu.add_command(label="Import Knowledge DB", command=self.import_knowledge_db_ui)

    def _windows_dark_mode(self):
        if os.name != "nt":
            return False
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return int(value) == 0
        except Exception:
            return False

    def effective_theme(self):
        # v1.2.12: production UI is intentionally dark-only.
        return "Dark"

    def _apply_tree_palette(self):
        if not hasattr(self, "tree"):
            return
        dark = ctk.get_appearance_mode() == "Dark"
        style = ttk.Style(self)
        if dark:
            bg, fg, head, sel = "#0d1e2e", "#f4f7fb", "#102438", "#164d82"
            crit, high, check, prot = "#2c1820", "#261f17", "#222216", "#0a1722"
        else:
            bg, fg, head, sel = "#f8fafc", "#102030", "#dfe8f0", "#b9d9f7"
            crit, high, check, prot = "#f7dfe3", "#f5ead5", "#f4efcf", "#e5ebf0"
        style.configure("Modern.Treeview", background=bg, fieldbackground=bg,
                        foreground=fg, rowheight=76, borderwidth=0,
                        font=("Segoe UI",10))
        style.map("Modern.Treeview", background=[("selected",sel)],
                  foreground=[("selected",fg)])
        style.configure("Modern.Treeview.Heading", background=head, foreground=fg,
                        relief="flat", padding=(8,10), font=("Segoe UI Semibold",10))
        self.tree.tag_configure("critical",background=crit,foreground=fg)
        self.tree.tag_configure("high",background=high,foreground=fg)
        self.tree.tag_configure("check",background=check,foreground=fg)
        self.tree.tag_configure("protected",background=prot,foreground="#708396")
        self.tree.tag_configure("baseline",foreground="#708396")

    def _scan_ui(self, active, message="Scanning connected phone…", current=None, total=None):
        if not hasattr(self, "scan_overlay"):
            return
        if active:
            if current is not None and total:
                pct=max(0.0,min(1.0,float(current)/float(total)))
                self.scan_message_var.set(f"{message}  {current}/{total}")
                self.scan_progress.configure(mode="determinate")
                self.scan_progress.stop()
                self.scan_progress.set(pct)
                if hasattr(self,"scan_percent_var"):
                    self.scan_percent_var.set(f"{int(pct*100)}%")
            else:
                self.scan_message_var.set(message)
                self.scan_progress.configure(mode="indeterminate")
                self.scan_progress.start()
                if hasattr(self,"scan_percent_var"):
                    self.scan_percent_var.set("")
            self.scan_overlay.place(relx=0.5, rely=0.5, anchor="center")
            self.scan_overlay.lift()
            if hasattr(self,"bottom_status_var"): self.bottom_status_var.set(message)
        else:
            self.scan_progress.stop()
            self.scan_overlay.place_forget()
            if hasattr(self,"scan_percent_var"): self.scan_percent_var.set("")
            if hasattr(self,"bottom_status_var"): self.bottom_status_var.set("Ready")

    def apply_theme(self):
        ctk.set_appearance_mode("dark")
        self._apply_tree_palette()

    def set_appearance(self, mode):
        # Dark-only UI from v1.2.12 onward.
        self.appearance_mode = "Dark"
        ctk.set_appearance_mode("dark")
        self._apply_tree_palette()

    def _show_advanced_menu(self):
        try:
            x = self.advanced_button.winfo_rootx()
            y = self.advanced_button.winfo_rooty() + self.advanced_button.winfo_height() + 4
            self.advanced_menu.tk_popup(x, y)
        finally:
            try: self.advanced_menu.grab_release()
            except Exception: pass

    def _quick_theme_toggle(self):
        return

    def _ui_icon(self, kind, color="#ffffff", size=20):
        if not hasattr(self, "_ui_icon_cache"):
            self._ui_icon_cache = {}
        key=(kind,color,size)
        if key not in self._ui_icon_cache:
            pil=make_ui_icon(kind,color,size)
            self._ui_icon_cache[key]=ctk.CTkImage(light_image=pil,dark_image=pil,size=(size,size))
        return self._ui_icon_cache[key]

    def build(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.geometry("1540x900")
        self.minsize(1250, 720)

        self.C = {
            "bg": "#061521",
            "header": "#081a29",
            "card": "#0b1d2d",
            "card2": "#10283b",
            "line": "#1d405b",
            "text": "#f4f7fb",
            "muted": "#9fb5c9",
            "blue": "#168df2", "blue_hover": "#24a0ff",
            "red": "#ef2f49", "orange": "#f5a000",
            "green": "#13bf78"
        }
        C = self.C

        root = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        root.pack(fill="both", expand=True)

        # HEADER
        header = ctk.CTkFrame(root, fg_color=C["header"], corner_radius=0, height=118)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=(20, 12), pady=7)
        self.brand_image = None
        try:
            brand_path = bundled_asset("tig_red_brand.png")
            with Image.open(brand_path) as _brand:
                _brand = _brand.convert("RGB")
                self.brand_image = ctk.CTkImage(light_image=_brand.copy(), dark_image=_brand.copy(),
                                                size=(270,92))
            ctk.CTkLabel(brand, text="", image=self.brand_image).pack()
        except Exception as exc:
            resolver_log(f"BRAND image load failed: {exc!r}")
            ctk.CTkLabel(brand,text="The iPhone Guy",font=("Segoe UI",20,"bold"),
                         text_color="#ff334f").pack()
        ctk.CTkFrame(header, width=1, fg_color=C["line"]).pack(side="left", fill="y", pady=22, padx=8)

        title = ctk.CTkFrame(header, fg_color="transparent")
        title.pack(side="left", padx=18, pady=24)
        ctk.CTkLabel(title, text="Android Cleaner", font=("Segoe UI", 28, "bold"),
                     text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(title, text="Find and remove problematic Android apps",
                     font=("Segoe UI", 12), text_color=C["muted"]).pack(anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", padx=24)
        ctk.CTkButton(actions, text="?  Help", width=92, height=38, corner_radius=9,
                      fg_color="transparent", border_width=1, border_color=C["line"],
                      hover_color="#173f5e",
                      command=self.show_how_to_connect).pack(side="left", padx=5)
        self.advanced_button = ctk.CTkButton(actions, text="⚙  Advanced", width=118, height=38,
                                             corner_radius=9, fg_color="transparent",
                                             border_width=1, border_color=C["line"],
                                             hover_color="#173f5e",
                                             command=self._show_advanced_menu)
        self.advanced_button.pack(side="left", padx=5)
        self.advanced_menu = tk.Menu(self, tearoff=False)
        self.rebuild_advanced_menu()

        device = ctk.CTkFrame(header, fg_color=C["card2"], corner_radius=12,
                              border_width=1, border_color=C["line"])
        device.pack(side="right", padx=(20, 12), pady=18)
        self.device_var = tk.StringVar(value="No device")
        self.device_combo = ctk.CTkComboBox(device, variable=self.device_var, width=360, height=34,
                                            corner_radius=8, fg_color=C["card"],
                                            border_color=C["line"], button_color=C["card2"],
                                            dropdown_fg_color=C["card"],
                                            command=lambda _v:self._device_selected(None))
        self.device_combo.pack(padx=14, pady=(10, 2))
        self.info_var = tk.StringVar(value="Connect an Android phone")
        ctk.CTkLabel(device, textvariable=self.info_var, text_color=C["muted"],
                     font=("Segoe UI", 11), wraplength=350).pack(anchor="w", padx=14)
        self.status_var = tk.StringVar(value="Waiting for phone")
        ctk.CTkLabel(device, textvariable=self.status_var, text_color=C["green"],
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(0,8))

        # NAV CARD
        nav = ctk.CTkFrame(root, fg_color=C["card"], corner_radius=12,
                           border_width=1, border_color=C["line"])
        nav.pack(fill="x", padx=22, pady=(14, 10))
        self.nav_buttons = {}
        for label in ("Cleanup","Review","Games","Unused Apps","All Apps"):
            _nav_kind={"Cleanup":"cleanup","Review":"review","Games":"games","Unused Apps":"unused","All Apps":"all"}.get(label,"all")
            b = ctk.CTkButton(nav, text=label, image=self._ui_icon(_nav_kind,"#ffffff",19),
                              compound="left", height=46, corner_radius=9,
                              fg_color=C["card2"], hover_color="#17496e",
                              border_width=1, border_color=C["line"],
                              font=("Segoe UI", 11, "bold"),
                              command=lambda m=label:self.set_view(m))
            b.pack(side="left", padx=(10 if label=="Cleanup" else 4,4), pady=10)
            self.nav_buttons[label] = b

        self.rescan_button = ctk.CTkButton(
            nav, text="Rescan", image=self._ui_icon("rescan","#ffffff",19), compound="left",
            width=118, height=42, corner_radius=9,
            fg_color=C["blue"], border_width=2, border_color="#45b2ff",
            hover_color=C["blue_hover"], font=("Segoe UI", 11, "bold"),
            command=self.scan
        )
        self.rescan_button.pack(side="right", padx=10)
        self.onset_var = getattr(self, "onset_var", tk.StringVar(value="Unknown"))
        onset = ctk.CTkComboBox(nav, variable=self.onset_var, values=ONSET_OPTIONS,
                                width=170, height=40, corner_radius=9, fg_color=C["card2"],
                                border_color=C["line"], button_color=C["card2"],
                                dropdown_fg_color=C["card"], command=lambda _v:self.retriage())
        onset.pack(side="right", padx=8)
        ctk.CTkLabel(nav, text="Problem started:", text_color=C["text"]).pack(side="right", padx=(10,0))

        # Context
        context = ctk.CTkFrame(root, fg_color="transparent")
        context.pack(fill="x", padx=28, pady=(0,10))
        self.baseline_var = tk.StringVar(value="")
        ctk.CTkLabel(context, textvariable=self.baseline_var, text_color=C["muted"],
                     font=("Segoe UI", 11)).pack(anchor="w")
        self.popup_summary_var = tk.StringVar(value="Secondary cleanup: waiting for scan")
        ctk.CTkLabel(context, textvariable=self.popup_summary_var, text_color=C["muted"],
                     font=("Segoe UI", 11)).pack(anchor="w", pady=(3,0))
        self.count_var = getattr(self, "count_var", tk.StringVar(value="Showing 0 apps • 0 selected"))

        # MAIN SPLIT
        main = ctk.CTkFrame(root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=22, pady=(0,10))
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1, minsize=430)
        main.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(main, fg_color=C["card"], corner_radius=12,
                            border_width=1, border_color=C["line"])
        left.grid(row=0,column=0,sticky="nsew",padx=(0,8))
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10,6))
        ctk.CTkLabel(top, textvariable=self.count_var, text_color=C["muted"]).pack(side="right")
        ctk.CTkButton(top, text="Clear Selection", width=120, height=34, corner_radius=8,
                      fg_color="transparent", border_width=1, border_color=C["line"],
                      command=self.clear_all_checked).pack(side="right", padx=10)

        # Treeview retained as the high-performance 555-row grid, but fully themed.
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("Modern.Treeview", background="#0d1e2e", fieldbackground="#0d1e2e",
                        foreground="#f4f7fb", rowheight=72, borderwidth=0, relief="flat",
                        bordercolor="#0b1d2d", lightcolor="#0b1d2d", darkcolor="#0b1d2d",
                        font=("Segoe UI", 10))
        style.map("Modern.Treeview", background=[("selected","#164d82")],
                  foreground=[("selected","#ffffff")])
        style.configure("Modern.Treeview.Heading", background="#102438", foreground="#c8d4df",
                        relief="flat", padding=(8,10), font=("Segoe UI Semibold",10))
        style.map("Modern.Treeview.Heading", background=[("active","#17344f")])
        try:
            style.layout("Modern.Treeview", [("Treeview.treearea", {"sticky":"nswe"})])
        except Exception:
            pass

        cols=("checked","app","priority","app_type","installer","installed","package","reputation",
              "status","identity","version","updated","special","online","popup","reason")
        table = ctk.CTkFrame(left, fg_color="transparent", corner_radius=0)
        table.pack(fill="both", expand=True, padx=1, pady=(0,1))
        self.tree=ttk.Treeview(table,columns=cols,show="tree headings",selectmode="extended",
                               style="Modern.Treeview")
        heads={"checked":"","app":"App","priority":"Risk","app_type":"Type","installer":"Installed via",
               "installed":"First installed","package":"Package","reputation":"Reputation",
               "status":"Decision","identity":"Name","version":"Version","updated":"Last updated",
               "special":"Special access","online":"Online reputation","popup":"Popup ads","reason":"Why it is shown"}
        widths={"checked":46,"app":310,"priority":100,"app_type":115,"installer":145,"installed":160,
                "package":250,"reputation":130,"status":100,"identity":80,"version":90,"updated":145,
                "special":180,"online":175,"popup":120,"reason":280}
        for c in cols:
            self.tree.heading(c,text=heads[c],command=lambda col=c:self.sort_by(col,False))
            self.tree.column(c,width=widths[c],anchor="w")
        self.tree.heading("#0",text="")
        self.tree.column("#0",width=72,minwidth=72,stretch=False,anchor="center")
        self.tree.column("checked",width=46,minwidth=46,stretch=False,anchor="center")
        self.tree["displaycolumns"]=("checked","app","priority","app_type","installer","installed")
        ys=ctk.CTkScrollbar(table,orientation="vertical",command=self.tree.yview,
                            width=12,corner_radius=6,fg_color=C["card"],
                            button_color="#24445e",button_hover_color=C["blue"])
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left",fill="both",expand=True)
        ys.pack(side="right",fill="y",padx=(4,0))
        self.tree.bind("<Button-1>",self.on_tree_click,add="+")
        self.tree.bind("<<TreeviewSelect>>",lambda e:self.update_selection_summary())
        self.tree.tag_configure("critical",background="#35131d",foreground="#ffffff")
        self.tree.tag_configure("high",background="#2b2114",foreground="#ffffff")
        self.tree.tag_configure("check",background="#252414",foreground="#ffffff")
        self.tree.tag_configure("baseline",foreground="#708396")
        self.tree.tag_configure("protected",background="#0a1722",foreground="#627487")
        self.icon_images={}

        # Clear active scanning state: staff can see that work is happening.
        self.scan_overlay=ctk.CTkFrame(left,fg_color=C["card"],corner_radius=14,
                                       border_width=1,border_color=C["line"],width=360,height=150)
        self.scan_message_var=tk.StringVar(value="Scanning connected phone…")
        ctk.CTkLabel(self.scan_overlay,text="Scanning phone",font=("Segoe UI",17,"bold"),
                     text_color=C["text"]).pack(padx=28,pady=(24,4))
        ctk.CTkLabel(self.scan_overlay,textvariable=self.scan_message_var,text_color=C["muted"],
                     font=("Segoe UI",11)).pack(padx=28,pady=(0,14))
        self.scan_progress=ctk.CTkProgressBar(self.scan_overlay,width=280,height=8,mode="indeterminate")
        self.scan_progress.pack(padx=28,pady=(0,6))
        self.scan_percent_var=tk.StringVar(value="")
        ctk.CTkLabel(self.scan_overlay,textvariable=self.scan_percent_var,text_color=C["muted"],
                     font=("Segoe UI",10,"bold")).pack(padx=28,pady=(0,18))

        # ASSESSMENT CARD
        right=ctk.CTkFrame(main,fg_color=C["card"],corner_radius=12,border_width=1,border_color=C["line"])
        right.grid(row=0,column=1,sticky="nsew",padx=(8,0))
        self.selection_var=tk.StringVar(value="Select an app to review it.")
        self.intel_title_var=tk.StringVar(value="")
        self.intel_history_var=tk.StringVar(value="")
        self.intel_reason_var=tk.StringVar(value="")
        self.assessment_icon_image = None

        assess_top = ctk.CTkFrame(right, fg_color="transparent")
        assess_top.pack(fill="x", padx=16, pady=(10,5))
        assess_text = ctk.CTkFrame(assess_top, fg_color="transparent")
        assess_text.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(assess_text,text="App assessment",text_color=C["muted"],
                     font=("Segoe UI",11)).pack(anchor="w")
        ctk.CTkLabel(assess_text,textvariable=self.selection_var,text_color=C["text"],
                     font=("Segoe UI",18,"bold"),justify="left",anchor="w",
                     wraplength=300).pack(fill="x",pady=(4,0))

        self.assessment_icon_frame = ctk.CTkFrame(
            assess_top, width=112, height=112, corner_radius=20,
            fg_color="#0a2940", border_width=2, border_color="#17547a"
        )
        self.assessment_icon_frame.pack(side="right", padx=(12,0))
        self.assessment_icon_frame.pack_propagate(False)
        self.assessment_icon_label = ctk.CTkLabel(
            self.assessment_icon_frame, text="", width=100, height=100
        )
        self.assessment_icon_label.place(relx=.5,rely=.5,anchor="center")
        ctk.CTkFrame(right,height=1,fg_color=C["line"]).pack(fill="x",padx=18)

        ctk.CTkLabel(right,text="DETAILS",text_color=C["muted"],font=("Segoe UI",10,"bold")).pack(anchor="w",padx=16,pady=(6,1))
        ctk.CTkLabel(right,textvariable=self.intel_history_var,text_color=C["text"],justify="left",
                     anchor="w",wraplength=410).pack(fill="x",padx=16,pady=(1,4))

        risk=ctk.CTkFrame(right,fg_color=("#fff0f2","#2b1720"),corner_radius=10,border_width=1,border_color="#8d2c3b")
        risk.pack(fill="x",padx=16,pady=4)
        ctk.CTkLabel(risk,text="⚠  Why we're showing this",font=("Segoe UI",12,"bold"),
                     text_color=C["text"]).pack(anchor="w",padx=12,pady=(7,2))
        ctk.CTkLabel(risk,textvariable=self.intel_reason_var,text_color=("#5d2933","#e6cbd0"),
                     justify="left",anchor="w",wraplength=390).pack(fill="x",padx=12,pady=(1,7))

        intel=ctk.CTkFrame(right,fg_color=C["card2"],corner_radius=10,border_width=1,border_color=C["line"])
        intel.pack(fill="x",padx=16,pady=4)
        ctk.CTkLabel(intel,text="🔧  Repair intelligence",font=("Segoe UI",12,"bold"),
                     text_color=C["text"]).pack(anchor="w",padx=12,pady=(7,2))
        ctk.CTkLabel(intel,textvariable=self.intel_title_var,text_color=C["muted"],
                     justify="left",anchor="w",wraplength=390).pack(fill="x",padx=12,pady=(1,7))

        actions=ctk.CTkFrame(right,fg_color="transparent")
        actions.pack(fill="x",side="bottom",padx=16,pady=(6,10))
        actions.grid_columnconfigure((0,1),weight=1)
        self.remove_button=ctk.CTkButton(actions,text="Remove App",image=self._ui_icon("remove","#ffffff",19),compound="left",height=42,corner_radius=9,
                                         fg_color=C["red"],hover_color="#b92335",font=("Segoe UI",11,"bold"),
                                         command=self.uninstall)
        self.remove_button.grid(row=0,column=0,sticky="ew",padx=(0,6))
        ctk.CTkButton(actions,text="Mark Safe",image=self._ui_icon("safe","#ffffff",19),compound="left",height=42,corner_radius=9,fg_color=("#dff7ee","#103b32"),
                      text_color=("#116b50","#61e7b1"),hover_color=("#c8efe2","#155443"),
                      border_width=1,border_color=("#51b99a","#267c64"),font=("Segoe UI",11,"bold"),
                      command=lambda:self.classify("Safe")).grid(row=0,column=1,sticky="ew",padx=(6,0))

        footer=ctk.CTkFrame(root,fg_color=C["header"],corner_radius=0,height=34)
        footer.pack(fill="x")
        self.bottom_status_var=tk.StringVar(value="Ready")
        ctk.CTkLabel(footer,textvariable=self.bottom_status_var,text_color=C["muted"],font=("Segoe UI",10)).pack(side="left",padx=24)
        ctk.CTkLabel(footer,text="Icon cache enabled",text_color=C["muted"],font=("Segoe UI",10)).pack(side="right",padx=24)
        self.icon_status_var=tk.StringVar(value="Icons: waiting")
        ctk.CTkLabel(footer,textvariable=self.icon_status_var,text_color=C["muted"],font=("Segoe UI",10)).pack(side="right")
        self._apply_tree_palette()

    def set_view(self, mode):
        self.view_var.set(mode)
        if hasattr(self, "view_label_var"):
            self.view_label_var.set(mode)
        self.apply_view()

        # Workshop views should show human-readable Android labels, not package
        # names. Resolve only the apps relevant to the selected view so opening
        # All Apps never triggers hundreds of APK pulls.
        if mode in ("Cleanup", "Games", "Unused Apps"):
            self.after(75, lambda m=mode: self.resolve_view_names(m))

    def _set_assessment_icon(self, app=None):
        if not hasattr(self, "assessment_icon_label"):
            return
        self.assessment_icon_image = None
        if not app:
            self.assessment_icon_label.configure(image=None, text="")
            return
        path = str(app.get("icon_path") or "")
        if not path or not Path(path).is_file():
            self.assessment_icon_label.configure(image=None, text="")
            return
        try:
            with Image.open(path) as im:
                im = im.convert("RGBA")
                im.thumbnail((92,92), Image.Resampling.LANCZOS)
                self.assessment_icon_image = ctk.CTkImage(
                    light_image=im.copy(), dark_image=im.copy(), size=im.size
                )
            self.assessment_icon_label.configure(image=self.assessment_icon_image, text="")
        except Exception as exc:
            resolver_log(f"ICON ASSESSMENT load failed {path}: {exc!r}")
            self.assessment_icon_label.configure(image=None, text="")

    def update_selection_summary(self):
        n_checked = len(self.checked_packages)
        if hasattr(self, "remove_button"):
            self.remove_button.configure(text=("Remove Apps" if n_checked > 1 else "Remove App"))
        apps = self.action_apps()
        if not apps:
            self.selection_var.set("Select an app to review it.")
            self.intel_title_var.set(""); self.intel_history_var.set(""); self.intel_reason_var.set("")
            self._set_assessment_icon(None)
            return
        if len(apps) > 1:
            self.selection_var.set(f"{len(apps)} apps selected")
            self.intel_title_var.set("Repair intelligence will be recorded per app; group removals remain group-associated evidence.")
            self.intel_history_var.set(""); self.intel_reason_var.set("")
            self._set_assessment_icon(None)
            return
        a = apps[0]
        name=a.get("app_name") or a.get("package","")
        rep=a.get("reputation") or "UNKNOWN"
        priority=a.get("priority") or "INFO"
        self.selection_var.set(f"{name}\n{priority}   •   {rep}")
        self._set_assessment_icon(a)

        stats=knowledge_stats(a.get("package")) or {}
        evidence=repair_evidence_stats(a.get("package"))
        seen=int(stats.get("times_seen") or 0); removed=int(stats.get("times_removed") or 0)
        solo_yes=evidence.get("solo_yes",0); solo_no=evidence.get("solo_no",0); solo_unsure=evidence.get("solo_unsure",0)
        group_yes=evidence.get("group_yes",0); group_no=evidence.get("group_no",0); group_unsure=evidence.get("group_unsure",0)
        source=stats.get("knowledge_source") or ""
        history=[]
        if rep != "UNKNOWN": history.append(f"KNOWN: {rep}")
        if source: history.append(f"Source: {source}")
        history += [f"Seen {seen}", f"Removed {removed}"]
        if solo_yes or solo_no or solo_unsure:
            history.append(f"Solo: fixed {solo_yes}/{solo_yes+solo_no}" + (f" (+{solo_unsure} unsure)" if solo_unsure else ""))
        if group_yes or group_no or group_unsure:
            history.append(f"Group-associated: fixed {group_yes}/{group_yes+group_no}" + (f" (+{group_unsure} unsure)" if group_unsure else ""))
        if evidence.get("popup_solo_yes"):
            history.append(f"POP-UP ADS fixed solo {evidence['popup_solo_yes']}×")
        if evidence.get("popup_group_yes"):
            history.append(f"POP-UP ADS fixed in group {evidence['popup_group_yes']}×")
        net=shared_info(a.get("package"))
        if net:
            net_rep=str(net.get("reputation") or "UNKNOWN").upper()
            if net_rep != "UNKNOWN": history.append(f"SHARED REPUTATION: {net_rep}")
            history.append(f"SHARED: {net.get('observations',0)} obs / {net.get('removals',0)} removals / {net.get('repair_yes',0)} fixed")
            if int(net.get('safe_votes') or 0): history.append(f"Shared safe marks {net.get('safe_votes')}")
            if int(net.get('malware_votes') or 0): history.append(f"Shared malware marks {net.get('malware_votes')}")
        self.intel_title_var.set("\n".join("•  "+x for x in history) if history else "No previous repair evidence found")

        metadata=[]
        if a.get("version_name"):
            metadata.append("Version "+str(a.get("version_name")))
        if a.get("installer_label"):
            metadata.append("Installed via "+str(a.get("installer_label")))
        if a.get("first_install"):
            metadata.append("Installed "+str(a.get("first_install")))
        if a.get("last_update"):
            metadata.append("Updated "+str(a.get("last_update")))
        self.intel_history_var.set("\n".join("•  "+x for x in metadata))

        details=[]
        if a.get("active_special"):
            details.append("ACTIVE ACCESS: "+a["active_special"])
        if a.get("popup_risk") not in (None,"","NONE","SYSTEM","No signal"):
            details.append("Popup risk: "+str(a.get("popup_risk")))
        reasons=[x.strip() for x in (a.get("reason") or "").split("•") if x.strip()]
        if reasons:
            details.append("Why flagged: "+" • ".join(reasons[:4])+(" • …" if len(reasons)>4 else ""))
        if self._is_protected_app(a):
            details.insert(0, "PROTECTED SYSTEM APP — removal disabled")
        self.intel_reason_var.set("\n".join("•  "+x for x in details) if details else "No additional risk details.")

    def show_how_to_connect(self):
        win = tk.Toplevel(self)
        win.title("How to Connect an Android Phone")
        win.geometry("760x650")
        win.minsize(650, 540)
        win.transient(self)
        outer = ttk.Frame(win, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Connect a customer Android phone", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Once authorised, Android Cleaner detects the phone and starts scanning automatically.", style="Sub.TLabel").pack(anchor="w", pady=(2,14))

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        def page(title, body):
            f=ttk.Frame(nb, padding=18); nb.add(f, text=title)
            t=tk.Text(f, wrap="word", relief="flat", font=("Segoe UI",10), padx=4, pady=4)
            t.pack(fill="both", expand=True)
            t.insert("1.0", body); t.configure(state="disabled")

        page("Samsung", """1. Enable Developer options\n\nSettings → About phone → Software information → tap Build number 7 times. Enter the phone PIN if asked.\n\n2. Enable USB debugging\n\nSettings → Developer options → USB debugging → ON.\n\n3. Check Auto Blocker\n\nOn Samsung phones that use Auto Blocker, open Settings → Security and privacy → Auto Blocker. If it prevents the USB/ADB connection, temporarily turn Auto Blocker OFF while the phone is being serviced. Turn it back on when finished.\n\n4. Connect to the workshop PC\n\nUse a USB data cable and keep the phone unlocked. When “Allow USB debugging?” appears, tap Allow. “Always allow from this computer” is optional for a customer phone.\n\n5. Wait for the scan\n\nAndroid Cleaner will detect the authorised phone and start automatically. If the app says approval is required, check the phone screen.""")
        page("Pixel / Android", """1. Enable Developer options\n\nPixel: Settings → About phone → tap Build number 7 times.\nOther Android brands use a similar path, sometimes under About phone → Software information.\n\n2. Enable USB debugging\n\nSettings → System → Developer options → USB debugging → ON. The exact menu name can vary by manufacturer.\n\n3. Connect to the workshop PC\n\nUse a USB data cable and keep the phone unlocked. Accept the “Allow USB debugging?” prompt on the phone.\n\n4. If the phone is not detected\n\nTry another known-good data cable/USB port. Unlock the phone and check its USB connection notification. Revoke USB debugging authorisations in Developer options only if authorisation is stuck, then reconnect and approve the PC again.\n\n5. Wait for the scan\n\nOnce ADB reports the phone as authorised, Android Cleaner automatically clears any previous customer data and scans the new phone.""")
        page("Finish", """Before returning the phone\n\n• Review Cleanup findings and only remove apps after confirming the selection.\n• Record the repair outcome when useful so the knowledge database improves.\n• Disconnect the USB cable — Android Cleaner clears the customer phone from the screen automatically.\n• If Auto Blocker was temporarily disabled, turn it back ON.\n• USB debugging can also be turned back OFF unless the customer has a reason to leave Developer options enabled.\n\nImportant\n\nA HIGH result belongs in Cleanup. A CHECK result is kept in the separate Review queue and is not a removal recommendation. In this workshop, “malware” is the practical working bucket for apps that hijack the phone (for example pop-ups, unwanted launchers or similar behaviour). Use Repair Outcome to build negative evidence; use Mark Safe only for apps you know should be excluded from Cleanup.""")
        ttk.Button(outer, text="Close", command=win.destroy).pack(anchor="e", pady=(12,0))

    def status(self, text):
        self.after(0, lambda: self.status_var.set(text))


    def bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()


    def open_knowledge_db(self):
        win = tk.Toplevel(self)
        win.title("Knowledge Database")
        win.geometry("1420x760")
        win.minsize(1000, 540)

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")

        search_var = tk.StringVar()
        filter_var = tk.StringVar(value="All")
        stats_var = tk.StringVar()

        ttk.Label(top, text="Search:").pack(side="left")
        search = ttk.Entry(top, textvariable=search_var, width=34)
        search.pack(side="left", padx=(5, 12))

        ttk.Label(top, text="Filter:").pack(side="left")
        filter_box = ttk.Combobox(
            top,
            textvariable=filter_var,
            state="readonly",
            width=20,
            values=(
                "All",
                "System / OEM",
                "User",
                "Sideloaded",
                "Unknown Reputation",
                "Classified",
            ),
        )
        filter_box.pack(side="left", padx=(5, 12))

        ttk.Label(top, textvariable=stats_var).pack(side="left")

        cols = (
            "name", "package", "type", "reputation", "confidence",
            "source", "seen", "last", "hash"
        )
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=8)

        tree = ttk.Treeview(
            frame, columns=cols, show="headings", selectmode="browse"
        )
        heads = {
            "name": "App name",
            "package": "Package",
            "type": "Type",
            "reputation": "Reputation",
            "confidence": "Confidence",
            "source": "Source",
            "seen": "Distinct scans",
            "last": "Last seen",
            "hash": "Last SHA-256",
        }
        widths = {
            "name": 190, "package": 260, "type": 125,
            "reputation": 110, "confidence": 80, "source": 155,
            "seen": 90, "last": 145, "hash": 280,
        }
        for col in cols:
            tree.heading(col, text=heads[col])
            tree.column(col, width=widths[col], anchor="w")

        ys = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")

        detail = tk.Text(win, height=8, wrap="word")
        detail.pack(fill="x", padx=8, pady=(6, 8))
        detail.configure(state="disabled")

        rowmap = {}

        def matches_filter(d):
            flt = filter_var.get()
            app_type = str(d.get("app_type") or "").upper()
            reputation = str(d.get("reputation") or "UNKNOWN").upper()

            if flt == "System / OEM":
                return app_type in {
                    "SYSTEM", "OEM / SYSTEM", "OEM SYSTEM", "UPDATED SYSTEM"
                }
            if flt == "User":
                return app_type in {"USER", "OEM APP", "FACTORY PRELOAD", "WEB APP"}
            if flt == "Sideloaded":
                return app_type == "SIDELOADED"
            if flt == "Unknown Reputation":
                return reputation == "UNKNOWN"
            if flt == "Classified":
                return reputation != "UNKNOWN"
            return True

        def load(*_):
            q = search_var.get().strip().lower()
            for iid in tree.get_children():
                tree.delete(iid)
            rowmap.clear()

            con = sqlite3.connect(DB_PATH)
            con.row_factory = sqlite3.Row
            try:
                rows = con.execute(
                    """SELECT * FROM knowledge_apps
                       ORDER BY COALESCE(canonical_name,package_name)
                       COLLATE NOCASE"""
                ).fetchall()

                shown = 0
                for r in rows:
                    d = dict(r)
                    hay = (
                        str(d.get("canonical_name") or "") + " " +
                        d["package_name"] + " " +
                        str(d.get("app_type") or "") + " " +
                        str(d.get("reputation") or "") + " " +
                        str(d.get("knowledge_source") or "")
                    ).lower()

                    if q and q not in hay:
                        continue
                    if not matches_filter(d):
                        continue

                    iid = tree.insert(
                        "", "end",
                        values=(
                            d.get("canonical_name") or d["package_name"],
                            d["package_name"],
                            d.get("app_type") or "",
                            d.get("reputation") or "UNKNOWN",
                            d.get("confidence") or 0,
                            d.get("knowledge_source") or "",
                            d.get("times_seen") or 0,
                            d.get("last_seen") or "",
                            d.get("last_apk_sha256") or "",
                        ),
                    )
                    rowmap[iid] = d
                    shown += 1

                a, o, s, t = knowledge_database_stats()
                stats_var.set(
                    f"Showing {shown} of {a} known apps • "
                    f"{o} app observations • {s} system observations • "
                    f"{t} classified"
                )
            finally:
                con.close()

        def selected(_=None):
            sel = tree.selection()
            if not sel:
                return
            d = rowmap.get(sel[0], {})
            pkg = d.get("package_name", "")

            con = sqlite3.connect(DB_PATH)
            con.row_factory = sqlite3.Row
            try:
                obs = con.execute(
                    """SELECT observed_at,manufacturer,model,android_version,
                              app_type,installer,version_name,classification
                       FROM knowledge_observations
                       WHERE package_name=?
                       ORDER BY id DESC LIMIT 8""",
                    (pkg,),
                ).fetchall()
                sysobs = con.execute(
                    """SELECT observed_at,manufacturer,model,android_version,
                              app_type,source
                       FROM system_observations
                       WHERE package_name=?
                       ORDER BY id DESC LIMIT 8""",
                    (pkg,),
                ).fetchall()
                seed = con.execute(
                    """SELECT e.*,s.source_name,s.source_url
                       FROM knowledge_seed_entries e
                       LEFT JOIN knowledge_sources s
                         ON s.source_id=e.source_id
                       WHERE e.package_name=?""",
                    (pkg,),
                ).fetchone()
            finally:
                con.close()

            lines = [
                f"{d.get('canonical_name') or pkg}  •  {pkg}",
                f"Type: {d.get('app_type') or ''}    "
                f"Reputation: {d.get('reputation') or 'UNKNOWN'}    "
                f"Confidence: {d.get('confidence') or 0}%",
                f"Source: {d.get('knowledge_source') or ''}    "
                f"Distinct scans: {d.get('times_seen') or 0}    "
                f"Last: {d.get('last_seen') or ''}",
            ]
            if seed:
                lines.append(
                    f"Authoritative seed: "
                    f"{seed['source_name'] or seed['source_id']} • "
                    f"{seed['trust_status']} • "
                    f"protection {seed['protection_level']}"
                )
            if obs:
                lines.append("\nRecent app observations:")
                for r in obs:
                    lines.append(
                        f"  {r['observed_at']} • "
                        f"{r['manufacturer'] or ''} {r['model'] or ''} • "
                        f"Android {r['android_version'] or ''} • "
                        f"{r['app_type'] or ''} • {r['version_name'] or ''}"
                    )
            if sysobs:
                lines.append("\nSystem/OEM observations:")
                for r in sysobs:
                    lines.append(
                        f"  {r['observed_at']} • "
                        f"{r['manufacturer'] or ''} {r['model'] or ''} • "
                        f"Android {r['android_version'] or ''} • "
                        f"{r['app_type']} • {r['source']}"
                    )

            detail.configure(state="normal")
            detail.delete("1.0", "end")
            detail.insert("1.0", "\n".join(lines))
            detail.configure(state="disabled")

        search_var.trace_add("write", load)
        filter_box.bind("<<ComboboxSelected>>", load)
        tree.bind("<<TreeviewSelect>>", selected)
        load()
        search.focus_set()


    def _clear_device_results(self, message="Ready for scan"):
        """Clear every piece of per-device UI so stale phone data is never shown."""
        self._scan_generation += 1
        self.device_serial = None
        self.pending_repair_group = None
        self.pending_repair_apps = []
        self.all_apps = []
        self.rows = {}
        self.checked_packages.clear()
        self.baseline_date = None
        self.baseline_count = 0
        self.info_var.set("")
        self.baseline_var.set("")
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.count_var.set("Showing 0 apps • 0 selected")
        if hasattr(self, "selection_var"):
            self.selection_var.set("Select an app to review it.")
        self.status_var.set(message)

    def _device_selected(self, event=None):
        serial = self.serial()
        if serial == self._selected_serial:
            return
        self._selected_serial = serial
        self._clear_device_results(
            "New device selected — scanning..." if serial else "Device not ready"
        )
        if serial:
            self.after(100, self.scan)

    def _device_poll(self):
        # Store workflow: notice unplug/replug/new phones without requiring staff
        # to press Refresh Devices. refresh_devices has an in-flight guard.
        self.refresh_devices(auto=True)
        self.after(2500, self._device_poll)

    def refresh_devices(self, auto=False):
        if self._device_refresh_running:
            return
        self._device_refresh_running = True

        def worker():
            try:
                devices = get_devices()
                vals = []
                ready_serials = []
                for serial, state in devices:
                    label = "ready" if state == "device" else "USB debugging approval required"
                    vals.append(f"{serial}  [{label}]")
                    if state == "device":
                        ready_serials.append(serial)

                def update():
                    self._device_refresh_running = False
                    old_selected = self._selected_serial
                    self.device_combo["values"] = vals

                    # Exactly one authorised device: make it authoritative.
                    if len(ready_serials) == 1:
                        serial = ready_serials[0]
                        value = next(v for v in vals if v.startswith(serial + "  ["))
                        if old_selected != serial:
                            self.device_var.set(value)
                            self._selected_serial = serial
                            self._clear_device_results("New device detected — syncing knowledge...")
                            self.production_sync("device-connected")
                            self.after(250, self.scan)
                        elif self.device_var.get() != value:
                            self.device_var.set(value)

                    elif len(ready_serials) == 0:
                        if old_selected is not None or self.all_apps:
                            self._selected_serial = None
                            self.device_var.set(vals[0] if vals else "No device found")
                            self._clear_device_results(
                                "USB debugging approval required" if vals
                                else "No Android device found"
                            )
                        elif not vals:
                            self.device_var.set("No device found")
                            self.status_var.set("No Android device found")

                    else:
                        # Multiple authorised devices: never guess which customer's
                        # phone to scan. Clear stale results if the selected phone left.
                        if old_selected not in ready_serials:
                            self._selected_serial = None
                            self.device_var.set("Select device")
                            self._clear_device_results("Multiple devices detected — select one")
                        elif not auto:
                            self.status_var.set("Multiple devices detected")

                    self._known_ready_serials = set(ready_serials)

                self.after(0, update)

            except Exception as e:
                error_text = str(e)
                def failed():
                    self._device_refresh_running = False
                    if not auto:
                        messagebox.showerror("ADB Error", error_text)
                self.after(0, failed)

        self.bg(worker)

    def serial(self):
        text = self.device_var.get()
        if "  [" in text and "approval required" not in text:
            return text.split("  [", 1)[0]
        return None

    def scan(self):
        self._scan_ui(True, "Reading installed apps and device diagnostics…")
        serial = self.serial()
        if not serial:
            self._scan_ui(False)
            messagebox.showwarning(
                "Device not ready",
                "Enable USB debugging and approve this PC."
            )
            return

        self.device_serial = serial
        scan_generation = self._scan_generation

        def worker():
            try:
                man = get_prop(serial, "ro.product.manufacturer")
                model = get_prop(serial, "ro.product.model")
                ver = get_prop(serial, "ro.build.version.release")

                self.after(
                    0,
                    lambda: self.info_var.set(
                        f"{friendly_device_name(serial)[0]} ({model})  •  Android {ver}  •  Serial: {serial}"
                    )
                )

                self.status("Reading active special access...")
                special = {
                    "accessibility": enabled_component_packages(
                        serial, "enabled_accessibility_services"
                    ),
                    "notification": enabled_component_packages(
                        serial, "enabled_notification_listeners"
                    ),
                    "device_admin": active_device_admin(serial),
                    "overlay": appops_allowed(serial, "SYSTEM_ALERT_WINDOW"),
                    "install_unknown": appops_allowed(
                        serial, "REQUEST_INSTALL_PACKAGES"
                    ),
                }

                self.status("Reading installed apps...")
                apps = list_packages_fast(serial)
                self.status("Checking disabled and unused apps...")
                disabled = disabled_packages(serial)
                user_pkgs = [a.get("package") for a in apps if not a.get("is_system") and a.get("package")]
                hibernated, hibernation_supported = hibernated_packages(serial, user_pkgs, ver)
                self.status("Recording system/OEM inventory...")
                system_inventory = list_system_packages_fast(serial)
                knowledge_record_system_inventory(system_inventory, man, model, ver)

                rows = []
                for i, app in enumerate(apps, 1):
                    self.status(f"Reading metadata {i}/{len(apps)}")
                    if i == 1 or i == len(apps) or i % 5 == 0:
                        self.after(0, lambda n=i,t=len(apps): self._scan_ui(
                            True, "Reading app metadata", n, t))
                    if app.get("is_system"):
                        # All Apps must be literal, but a 400+ package phone should not
                        # require hundreds of dumpsys calls just to show system inventory.
                        app.update({
                            "version_name": "",
                            "first_install": "System / preloaded",
                            "last_update": "",
                        })
                    else:
                        details = package_details(serial, app["package"])
                        app.update(details)

                    cached_identity = identity_get(app)
                    if cached_identity and cached_identity.get("app_label"):
                        app_name = cached_identity["app_label"]
                        app["identity_state"] = "Resolved"
                        app["sha256"] = cached_identity.get("sha256", "") or ""
                        app["icon_path"] = icon_cache_path(app["sha256"])
                        knowledge_promote_identity(app)
                    else:
                        app_name = package_display_name(app["package"])
                        app["identity_state"] = "Pending"
                        app["sha256"] = ""
                        app["icon_path"] = ""

                    app["app_name"] = app_name
                    app["hibernated"] = app["package"] in hibernated
                    app["disabled_by_system"] = app["package"] in disabled
                    app["unused_state"], app["unused_reason"] = unused_cleanup_signal(app)

                    db_seen(app["package"], app_name)
                    rep = db_rep(app["package"])

                    active = []
                    for key, label in (
                        ("accessibility", "Accessibility"),
                        ("device_admin", "Device Admin"),
                        ("notification", "Notification access"),
                        ("overlay", "Overlay"),
                        ("install_unknown", "Install unknown apps"),
                    ):
                        if app["package"] in special[key]:
                            active.append(label)

                    app["active_special"] = ", ".join(active)
                    app["classification"] = (
                        rep.get("classification", "unknown")
                        if rep else "unknown"
                    )
                    app["online_status"] = "Not checked"
                    app["app_type"] = classify_app_type(app)
                    if app["app_type"] in ("SYSTEM", "OEM / SYSTEM"):
                        app["installer_label"] = "System image / OEM"
                    elif app["app_type"] == "UPDATED SYSTEM":
                        app["installer_label"] = installer_name(app.get("installer", "")) or "System update"
                    else:
                        app["installer_label"] = installer_name(app.get("installer", ""))
                    app["reputation"] = effective_reputation_label(app)
                    app["popup_risk"], app["popup_reasons"] = popup_ad_assessment(app, special)
                    rows.append(app)

                self.baseline_date, self.baseline_count = find_baseline_date(rows)

                for app in rows:
                    rep = db_rep(app["package"])
                    priority, score, reasons = triage_app(
                        app, rep, special,
                        self.baseline_date,
                        self.onset_var.get()
                    )
                    # Unused/hibernated/disabled state is deliberately NOT a diagnostic
                    # Cleanup signal. It is shown in the separate Unused Apps view. If an
                    # unused app independently triggers adware/security rules, those rules
                    # can still place it in Cleanup.
                    app["priority"] = priority
                    app["score"] = score
                    app["reason"] = " • ".join(reasons)
                    app["cleanup_candidate"] = is_cleanup_candidate(
                        app, self.onset_var.get()
                    )

                # If the cable/device changed while this scan was running, discard
                # its results rather than painting stale customer data onto the UI.
                if scan_generation != self._scan_generation or serial != self._selected_serial:
                    self.after(0, lambda:self._scan_ui(False))
                    return

                knowledge_record_scan(rows, man, model, ver)
                self.all_apps = rows
                self.checked_packages.intersection_update({a.get("package") for a in rows})
                self.sort_internal()
                self.after(0, self.update_baseline_label)
                self.after(0, self.apply_view)
                # Icon discovery is an independent post-scan pipeline. Do not rely
                # on name resolution/retriage to start it: a fully cached scan may
                # have no resolver work at all.
                self.after(50, self.start_background_icon_discovery)
                # v1.2.14: icon extraction is part of the visible scan. The icon
                # pipeline closes the overlay after its final repaint.
                if self._open_repair_outcome_after_scan and self.pending_repair_apps:
                    self._open_repair_outcome_after_scan = False
                    self.after(250, self.record_repair_outcome)

                cleanup_count = sum(
                    1 for x in rows if x.get("cleanup_candidate", False)
                )

                # Resolve a bounded Discovery Set before final triage. This includes
                # current findings plus recent/post-baseline user apps, sideloads,
                # active-special-access apps and cheap package-name hints. Discovery
                # itself is NOT a finding; after labels resolve, retriage decides.
                relevant = discovery_resolution_candidates(rows, self.baseline_date)
                unresolved = [
                    x for x in relevant
                    if x.get("identity_state") not in ("Resolved", "No label")
                ]

                if unresolved:
                    self.status(
                        f"Scan complete: {len(rows)} apps • {cleanup_count} worth checking • "
                        f"discovering {len(unresolved)} app "
                        f"name{'s' if len(unresolved) != 1 else ''}..."
                    )
                    self._resolve_names_for_apps(relevant, "Discovery names")
                elif cleanup_count:
                    self.status(
                        f"Scan complete: {len(rows)} apps • {cleanup_count} worth checking • names complete"
                    )
                else:
                    self.status(f"Scan complete: {len(rows)} apps • 0 worth checking")

            except Exception as e:
                self.after(0, lambda:self._scan_ui(False))
                self.after(
                    0, lambda: messagebox.showerror("Scan failed", str(e))
                )
                self.status("Scan failed")

        self.bg(worker)

    def update_baseline_label(self):
        if self.baseline_date:
            self.baseline_var.set(
                f"Detected setup/migration cluster: "
                f"{self.baseline_date.isoformat()} "
                f"({self.baseline_count} third-party apps installed that day)"
            )
        else:
            self.baseline_var.set(
                "No strong setup/migration install cluster detected."
            )

    def retriage(self):
        if not self.all_apps:
            return

        # Re-read special-access state from the already scanned rows rather than
        # hitting the phone again.
        special = {
            "accessibility": set(),
            "notification": set(),
            "device_admin": set(),
            "overlay": set(),
            "install_unknown": set(),
        }

        for app in self.all_apps:
            labels = set(
                x.strip() for x in app.get("active_special", "").split(",")
                if x.strip()
            )
            if "Accessibility" in labels:
                special["accessibility"].add(app["package"])
            if "Notification access" in labels:
                special["notification"].add(app["package"])
            if "Device Admin" in labels:
                special["device_admin"].add(app["package"])
            if "Overlay" in labels:
                special["overlay"].add(app["package"])
            if "Install unknown apps" in labels:
                special["install_unknown"].add(app["package"])

        for app in self.all_apps:
            rep = db_rep(app["package"])
            app["app_type"] = classify_app_type(app)
            app["reputation"] = effective_reputation_label(app)
            priority, score, reasons = triage_app(
                app, rep, special,
                self.baseline_date,
                self.onset_var.get()
            )
            app["priority"] = priority
            app["score"] = score
            app["reason"] = " • ".join(reasons)
            app["cleanup_candidate"] = is_cleanup_candidate(
                app, self.onset_var.get()
            )

        self.sort_internal()
        self.apply_view()
        self.start_background_icon_discovery()

        # A Problem-started change can introduce new Cleanup candidates. Resolve
        # whatever is now visible instead of leaving newly-added rows as package IDs.
        mode = self.view_var.get()
        if mode in ("Cleanup", "Review", "Games", "Unused Apps"):
            self.after(100, lambda m=mode: self.resolve_view_names(m))

    def sort_internal(self):
        priority_order = {
            "CRITICAL": 5,
            "HIGH": 4,
            "CHECK": 3,
            "INFO": 2,
            "BASELINE": 1,
        }
        self.all_apps.sort(
            key=lambda x: (
                priority_order.get(x.get("priority"), 0),
                x.get("score", 0),
                parse_dt(x.get("first_install")) or datetime.min,
            ),
            reverse=True
        )

    def _visible_packages(self):
        return [self.tree.set(i, "package") for i in self.tree.get_children("")
                if self.tree.set(i, "package")]

    def update_count_label(self):
        visible = self._visible_packages()
        selected = sum(pkg in self.checked_packages for pkg in visible)
        self.count_var.set(f"Showing {len(visible)} of {len(self.all_apps)} apps • {selected} selected")

    def refresh_checkbox_cells(self):
        for iid in self.tree.get_children(""):
            pkg = self.tree.set(iid, "package")
            app = self.rows.get(iid)
            self.tree.set(iid, "checked", "🔒" if app and self._is_protected_app(app)
                          else ("☑" if pkg in self.checked_packages else "☐"))
        self.update_count_label()

    def on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        # A normal click anywhere on a row now makes it the active app. This fixes
        # the workshop UI feeling non-clickable while retaining checkbox multi-select.
        self.tree.selection_set(row)
        self.tree.focus(row)
        if self.tree.identify_column(event.x) == "#1":
            pkg = self.tree.set(row, "package")
            app = self.rows.get(row)
            if app and self._is_protected_app(app):
                return
            if pkg in self.checked_packages:
                self.checked_packages.remove(pkg)
            else:
                self.checked_packages.add(pkg)
            self.tree.set(row, "checked", "☑" if pkg in self.checked_packages else "☐")
            self.update_count_label()
        self.after_idle(self.update_selection_summary)

    def check_all_visible(self):
        self.checked_packages.update(a["package"] for a in self.rows.values() if not self._is_protected_app(a))
        self.refresh_checkbox_cells()

    def clear_all_checked(self):
        self.checked_packages.clear()
        self.refresh_checkbox_cells()

    def action_apps(self):
        checked = [a for a in self.all_apps
                   if a.get("package") in self.checked_packages and not self._is_protected_app(a)]
        if checked:
            return checked
        ids = self.tree.selection()
        pkgs = {self.tree.set(i, "package") for i in ids}
        return [a for a in self.all_apps
                if a.get("package") in pkgs and not self._is_protected_app(a)]

    def _tree_icon_for_app(self, app):
        path = str(app.get("icon_path") or "")
        if not path or not Path(path).is_file():
            return ""
        key = (path, 46)
        if key in self.icon_images:
            return self.icon_images[key]
        try:
            with Image.open(path) as im:
                im = im.convert("RGBA")
                im.thumbnail((46, 46), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(im.copy())
            self.icon_images[key] = photo
            return photo
        except Exception as exc:
            resolver_log(f"ICON UI load failed {path}: {exc!r}")
            return ""

    def _icon_candidate_signature(self):
        serial = self.serial()
        if not serial or not self.all_apps:
            return None
        candidates = [
            a for a in self.all_apps
            if a.get("priority") in ("CRITICAL", "HIGH", "CHECK")
            and not self._is_protected_app(a)
        ]
        if not candidates:
            return (serial, ())
        return (
            serial,
            tuple(sorted(
                (str(a.get("package") or ""), str(a.get("priority") or ""))
                for a in candidates
            ))
        )

    def _ensure_icon_pipeline_after_view(self):
        """Guaranteed UI-side trigger after suspicious rows have been painted."""
        sig = self._icon_candidate_signature()
        if not sig:
            return
        if getattr(self, "_icon_pipeline_running", False):
            return
        if sig == getattr(self, "_icon_pipeline_completed_signature", None):
            return
        resolver_log(
            f"ICON UI TRIGGER serial={sig[0]} candidates={len(sig[1])}: "
            f"table rendered; starting icon pipeline"
        )
        self.start_background_icon_discovery()

    def start_background_icon_discovery(self):
        """Resolve icons only for apps the technician is being asked to inspect."""
        serial = self.serial()
        resolver_log("ICON SERIAL ACCESSOR OK serial={!r}".format(serial))
        if not serial or not self.all_apps:
            resolver_log("ICON PIPELINE SKIP: no current serial or no scanned apps")
            return
        if getattr(self, "_icon_pipeline_running", False):
            resolver_log(f"ICON PIPELINE SKIP serial={serial}: worker already running")
            return

        work = [
            a for a in self.all_apps
            if a.get("priority") in ("CRITICAL", "HIGH", "CHECK")
            and not self._is_protected_app(a)
        ]
        work.sort(key=lambda a: {"CRITICAL":0,"HIGH":1,"CHECK":2}.get(a.get("priority"),3))
        signature = (
            serial,
            tuple(sorted(
                (str(a.get("package") or ""), str(a.get("priority") or ""))
                for a in work
            ))
        )
        total = len(work)

        self._icon_pipeline_running = True
        token = getattr(self, "_icon_generation", 0) + 1
        self._icon_generation = token

        resolver_log(
            f"ICON PIPELINE START serial={serial} generation={token} "
            f"candidates={total} packages=" +
            ",".join(str(a.get("package") or "") for a in work)
        )
        if hasattr(self, "icon_status_var"):
            self.icon_status_var.set(f"Icons: 0/{total} loaded")
        self.after(0, lambda: self._scan_ui(
            True, "Loading app icons…", 0, max(total,1)
        ))

        if not work:
            self._icon_pipeline_running = False
            self._icon_pipeline_completed_signature = signature
            resolver_log(f"ICON PIPELINE FINISH serial={serial}: no suspicious/review candidates")
            self.after(0, lambda:self._scan_ui(False))
            return

        def worker():
            done = 0
            attempted = 0
            completed_normally = False
            try:
                for app in work:
                    if token != getattr(self, "_icon_generation", None) or serial != self.serial():
                        resolver_log(
                            f"ICON PIPELINE CANCEL serial={serial} generation={token}: "
                            "device/generation changed"
                        )
                        return
                    package = str(app.get("package") or "")
                    existing = str(app.get("icon_path") or "")
                    attempted += 1
                    resolver_log(
                        f"ICON PIPELINE QUEUE {attempted}/{total} {package}: "
                        "invoking Android device renderer"
                    )
                    icon = pull_device_rendered_icon(serial, app)
                    if not icon and existing and Path(existing).is_file() and Path(existing).stat().st_size > 100:
                        icon = existing
                        resolver_log(f"ICON PIPELINE FALLBACK CACHE {package}: {existing}")
                    elif not icon:
                        icon = pull_apk_icon_fallback(serial, app)
                    if icon:
                        done += 1
                        app["icon_path"] = icon
                        resolver_log(f"ICON PIPELINE RESULT {package}: loaded {icon}")
                    else:
                        resolver_log(f"ICON PIPELINE RESULT {package}: no icon")
                    if hasattr(self, "icon_status_var"):
                        self.after(
                            0,
                            lambda d=done,t=total:
                                self.icon_status_var.set(f"Icons: {d}/{t} loaded")
                        )
                    self.after(
                        0,
                        lambda n=attempted,t=total:
                            self._scan_ui(True, "Loading app icons…", n, t)
                    )
                completed_normally = True
                # One final repaint prevents the selected assessment from being
                # cleared/flickered once per icon.
                self.after(0, self.apply_view)
                resolver_log(
                    f"ICON PIPELINE FINISH serial={serial} generation={token}: "
                    f"loaded={done}/{total} attempted={attempted}"
                )
            except Exception as exc:
                resolver_log(
                    f"ICON PIPELINE ERROR serial={serial} generation={token}: {exc!r}"
                )
                self.after(0, lambda:self._scan_ui(False))
            finally:
                self._icon_pipeline_running = False
                if completed_normally:
                    self._icon_pipeline_completed_signature = signature
                    self.after(80, lambda:self._scan_ui(False))

        threading.Thread(
            target=worker, daemon=True, name=f"icon-pipeline-{token}"
        ).start()


    def _is_protected_app(self, app):
        t = str(app.get("app_type") or app.get("type") or "").upper().strip()
        return t in ("SYSTEM", "OEM / SYSTEM", "SYSTEM / OEM", "SYSTEM/OEM", "UPDATED SYSTEM")

    def apply_view(self):
        mode = self.view_var.get()
        if hasattr(self, "nav_buttons"):
            for label, button in self.nav_buttons.items():
                active = label == mode
                active_color = ("#e92f49" if label == "Cleanup" else self.C["blue"])
                active_border = ("#ff536b" if label == "Cleanup" else "#58baff")
                button.configure(
                    fg_color=(active_color if active else self.C["card2"]),
                    border_color=(active_border if active else self.C["line"]),
                    border_width=(2 if active else 1)
                )
        if hasattr(self, "view_label_var"):
            self.view_label_var.set(mode)

        if mode == "All Apps":
            apps = self.all_apps

        elif mode == "Deep Triage":
            # Broad technician view for difficult live repairs:
            # every post-baseline install, every recently updated app,
            # every app with active special access, and every normal Cleanup candidate.
            apps = []
            for app in self.all_apps:
                installed = parse_dt(app.get("first_install"))
                updated = parse_dt(app.get("last_update"))
                post_baseline = bool(
                    self.baseline_date and installed
                    and installed.date() > self.baseline_date
                )
                recent_update = bool(
                    updated and datetime.now() - updated <= timedelta(days=45)
                )
                has_special = bool(app.get("active_special"))
                candidate = app.get("priority") in ("CRITICAL", "HIGH", "CHECK")
                if post_baseline or recent_update or has_special or candidate:
                    apps.append(app)

            apps = sorted(
                apps,
                key=lambda x: (
                    {"CRITICAL":5, "HIGH":4, "CHECK":3, "INFO":2, "BASELINE":1}
                    .get(x.get("priority"), 0),
                    x.get("score", 0),
                    parse_dt(x.get("last_update")) or datetime.min,
                    parse_dt(x.get("first_install")) or datetime.min,
                ),
                reverse=True
            )

        elif mode == "Review":
            # CHECK is deliberately separated from the action-oriented Cleanup
            # queue. These are apps worth a technician glance, not bulk-removal
            # recommendations.
            apps = [
                x for x in self.all_apps
                if x.get("priority") == "CHECK"
                and x.get("app_type") not in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM")
                and str(x.get("reputation", "UNKNOWN")).upper() != "KNOWN SAFE"
            ]
            apps = sorted(
                apps,
                key=lambda x: (x.get("score", 0), parse_dt(x.get("first_install")) or datetime.min),
                reverse=True
            )

        elif mode == "Games":
            # Secondary cleanup view. Android-declared games are shown here for
            # optional customer tidy-up, but being a game never makes an app
            # suspicious or a Cleanup candidate by itself.
            apps = [
                x for x in self.all_apps
                if x.get("is_game")
                and x.get("app_type") not in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM")
            ]
            apps = sorted(
                apps,
                key=lambda x: (
                    bool(x.get("unused_state")),
                    parse_dt(x.get("first_install")) or datetime.min,
                    x.get("score", 0),
                ),
                reverse=True
            )

        elif mode == "Unused Apps":
            apps = [x for x in self.all_apps if x.get("unused_state") and x.get("app_type") not in ("SYSTEM","OEM / SYSTEM","UPDATED SYSTEM")]
            apps = sorted(apps, key=lambda x: (x.get("unused_state") == "HIBERNATED", x.get("is_game", False), x.get("score",0)), reverse=True)

        elif mode == "Recent Installs":
            apps = []
            for app in self.all_apps:
                dt = parse_dt(app.get("first_install"))
                if dt and datetime.now() - dt <= timedelta(days=45):
                    apps.append(app)

            apps = sorted(
                apps,
                key=lambda x: (
                    parse_dt(x.get("first_install")) or datetime.min
                ),
                reverse=True
            )

        else:
            apps = [
                x for x in self.all_apps
                if x.get("cleanup_candidate", False)
            ]

        # Preserve the technician's selected app across icon/name/retriage repaints.
        selected_package = None
        try:
            selected_ids = self.tree.selection()
            if selected_ids:
                selected_package = self.tree.set(selected_ids[0], "package")
        except Exception:
            selected_package = None

        for iid in self.tree.get_children():
            self.tree.delete(iid)

        self.rows = {}
        selected_iid = None

        for app in apps:
            tag = app["priority"].lower()
            if self._is_protected_app(app):
                tag = "protected"
                app["checked"] = False
            iid = self.tree.insert(
                "", "end",
                image=self._tree_icon_for_app(app),
                values=(
                    ("🔒" if self._is_protected_app(app) else ("☑" if app["package"] in self.checked_packages else "☐")),
                    app["app_name"],
                    ({"CRITICAL":"CRITICAL","HIGH":"HIGH","CHECK":"CHECK"}
                     .get(app.get("priority"),app.get("priority",""))),
                    app.get("app_type", "UNKNOWN"),
                    app["installer_label"],
                    app.get("first_install", ""),
                    app["package"],
                    app.get("reputation", "UNKNOWN"),
                    {
                        "safe": "Safe", "unknown": "Unclassified",
                        "suspicious": "Suspicious", "malware": "Malware",
                    }.get(app["classification"], "Unclassified"),
                    app.get("identity_state", "Pending"),
                    app.get("version_name", ""),
                    app.get("last_update", ""),
                    app.get("active_special", ""),
                    app.get("online_status", "Not checked"),
                    {"NONE":"No signal", "SYSTEM":"System", "LOW":"Low", "MEDIUM":"Medium", "HIGH":"High"}.get(app.get("popup_risk", "NONE"), app.get("popup_risk", "No signal")),
                    app["reason"],
                ),
                tags=(tag,)
            )
            self.rows[iid] = app
            if selected_package and app.get("package") == selected_package:
                selected_iid = iid

        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            self.tree.see(selected_iid)
        self.update_count_label()
        if selected_iid:
            self.after_idle(self.update_selection_summary)
        if hasattr(self, "popup_summary_var"):
            user_apps = [a for a in self.all_apps if a.get("popup_risk") not in ("SYSTEM", None, "")]
            high = sum(a.get("popup_risk") == "HIGH" for a in user_apps)
            medium = sum(a.get("popup_risk") == "MEDIUM" for a in user_apps)
            low = sum(a.get("popup_risk") == "LOW" for a in user_apps)
            dormant = sum(bool(a.get("unused_state")) for a in self.all_apps if a.get("app_type") not in ("SYSTEM","OEM / SYSTEM","UPDATED SYSTEM"))
            games = sum(bool(a.get("is_game")) for a in self.all_apps if a.get("app_type") not in ("SYSTEM","OEM / SYSTEM","UPDATED SYSTEM"))
            self.popup_summary_var.set(
                f"Secondary cleanup: {dormant} unused app{'s' if dormant != 1 else ''} • "
                f"{games} game{'s' if games != 1 else ''}. Click a row for details."
            )


        # Hook the actual Treeview population path.
        resolver_log(
            "ICON TREEVIEW HOOK method=apply_view serial={} apps={}".format(
                self.serial(), len(self.all_apps or [])
            )
        )
        self.after_idle(self._ensure_icon_pipeline_after_view)

    def toggle_cross_pc_test_mode(self):
        global DB_PATH, CROSS_PC_TEST_MODE
        if not CROSS_PC_TEST_MODE:
            if not shared_configured():
                messagebox.showinfo("Cross-PC Test Mode", "Configure Shared Knowledge first.")
                return
            if not messagebox.askyesno(
                "Cross-PC Test Mode",
                "Start a fresh-PC simulation?\n\nThis uses a separate empty local database, downloads shared intelligence only, and never uploads test data. Your Simon Home database is not modified."
            ):
                return
            CROSS_PC_TEST_MODE = True
            DB_PATH = TEST_DB_PATH
            try:
                if TEST_DB_PATH.exists():
                    TEST_DB_PATH.unlink()
                init_db()
                n = shared_pull()
                self._clear_device_results("Cross-PC Test Mode — shared intelligence downloaded")
                self.title(APP_NAME + "  [CROSS-PC TEST]")
                messagebox.showinfo(
                    "Cross-PC Test Mode",
                    f"Fresh test database created.\n\nDownloaded {n} shared app records.\nUploads are disabled.\nStore identity: TEST-PC-2\n\nThe connected phone will now rescan against shared intelligence only."
                )
                if self.serial():
                    self.after(150, self.scan)
            except Exception as e:
                CROSS_PC_TEST_MODE = False
                DB_PATH = REAL_DB_PATH
                self.title(APP_NAME)
                messagebox.showerror("Cross-PC Test Mode", "Could not start test mode: " + str(e))
        else:
            CROSS_PC_TEST_MODE = False
            DB_PATH = REAL_DB_PATH
            self._clear_device_results("Returned to normal local database — rescanning...")
            self.title(APP_NAME)
            if self.serial():
                self.after(150, self.scan)
            messagebox.showinfo("Cross-PC Test Mode", "Test Mode ended. Simon Home local database restored.")

    def open_shared_knowledge(self):
        win=tk.Toplevel(self); win.title("Shared Knowledge"); win.geometry("650x420"); win.transient(self)
        cfg=shared_config()
        ttk.Label(win,text="Shared Knowledge",font=("Segoe UI",12,"bold")).pack(anchor="w",padx=14,pady=(14,4))
        ttk.Label(win,text="Offline-first: every PC keeps its local database. Sync shares technician-safe decisions and repair evidence between stores.",wraplength=610).pack(anchor="w",padx=14,pady=(0,12))
        form=ttk.Frame(win); form.pack(fill="x",padx=14)
        ttk.Label(form,text="Apps Script Web App URL").grid(row=0,column=0,sticky="w",pady=5)
        url=tk.StringVar(value=cfg["url"]); ttk.Entry(form,textvariable=url,width=68).grid(row=0,column=1,sticky="ew",pady=5)
        ttk.Label(form,text="Store ID").grid(row=1,column=0,sticky="w",pady=5)
        store=tk.StringVar(value=cfg["store_id"]); ttk.Entry(form,textvariable=store,width=30).grid(row=1,column=1,sticky="w",pady=5)
        ttk.Label(form,text="API key").grid(row=2,column=0,sticky="w",pady=5)
        key=tk.StringVar(value=cfg["api_key"]); ttk.Entry(form,textvariable=key,width=45,show="•").grid(row=2,column=1,sticky="w",pady=5)
        form.columnconfigure(1,weight=1)
        status=tk.StringVar(value=("CROSS-PC TEST MODE — download only" if CROSS_PC_TEST_MODE else ("Configured" if shared_configured() else "Not configured")))
        ttk.Label(win,textvariable=status,wraplength=610).pack(anchor="w",padx=14,pady=(12,8))
        def save_cfg():
            st=load_settings(); st["shared_knowledge_url"]=url.get().strip(); st["shared_knowledge_store_id"]=store.get().strip(); st["shared_knowledge_api_key"]=key.get().strip(); save_settings(st); status.set("Settings saved")
        def test_sync():
            save_cfg(); status.set("Connecting…"); win.update_idletasks()
            try:
                r=shared_request({"op":"ping"}); status.set("Connected: "+str(r.get("message","Shared database online")))
            except Exception as e: status.set("Connection failed: "+str(e))
        def sync_now():
            save_cfg(); status.set("Syncing…"); win.update_idletasks()
            try:
                up=shared_push_local_snapshot(); n=shared_pull(); status.set((f"Test sync complete: {n} shared app records downloaded • uploads disabled" if CROSS_PC_TEST_MODE else f"Sync complete: {up} local records uploaded • {n} shared app records downloaded"))
                self.retriage(); self.update_selection_summary()
            except Exception as e: status.set("Sync failed: "+str(e))
        buttons=ttk.Frame(win); buttons.pack(fill="x",padx=14,pady=8)
        ttk.Button(buttons,text="Save",command=save_cfg).pack(side="left")
        ttk.Button(buttons,text="Test Connection",command=test_sync).pack(side="left",padx=6)
        ttk.Button(buttons,text="Sync Now",command=sync_now).pack(side="left")
        ttk.Label(win,text="Use a different Store ID on each shop PC (for example Belmont, Ballarat, Lara or Drysdale). The API key is shared by your stores.",wraplength=610).pack(anchor="w",padx=14,pady=(10,0))

    def record_repair_outcome(self):
        # A removal waiting for an outcome is a specific repair event.  It must
        # take precedence over whatever is currently selected after the automatic
        # rescan (including a reinstalled copy of the same package).
        group_id = None
        if self.pending_repair_apps:
            apps = list(self.pending_repair_apps)
            group_id = self.pending_repair_group
        else:
            apps = self.action_apps()
        if not apps:
            messagebox.showinfo("Repair Outcome", "Select apps, or remove apps first. Recent removals stay available here after the rescan.")
            return

        win = tk.Toplevel(self); win.title("Repair Intelligence"); win.geometry("600x520"); win.transient(self)
        names=", ".join((a.get("app_name") or a.get("package")) for a in apps[:4])
        if len(apps)>4: names += f" + {len(apps)-4} more"
        ttk.Label(win,text="Record repair result",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=14,pady=(14,4))
        scope_note = ""
        if group_id:
            if len(apps) == 1:
                scope_note = "  [removed alone — strong individual evidence]"
            else:
                scope_note = f"  [removed together — group evidence across {len(apps)} apps]"
        ttk.Label(win,text=names + scope_note,wraplength=560).pack(anchor="w",padx=14,pady=(0,6))
        if group_id and len(apps) > 1:
            ttk.Label(win,text="If the problem is fixed, the repair event is recorded against every removed app as GROUP-ASSOCIATED evidence — not proof that each app caused it.",wraplength=560).pack(anchor="w",padx=14,pady=(0,10))
        ttk.Label(win,text="Did removing / acting on these apps fix the customer's problem?").pack(anchor="w",padx=14)
        fixed=tk.StringVar(value="Unsure")
        ttk.Combobox(win,textvariable=fixed,state="readonly",width=18,values=("Yes","No","Unsure")).pack(anchor="w",padx=14,pady=6)
        ttk.Label(win,text="Problem / reason").pack(anchor="w",padx=14)
        reason=tk.StringVar(value="Pop-up ads")
        ttk.Combobox(win,textvariable=reason,state="readonly",width=32,values=("Pop-up ads","Browser redirects","Fake cleaner","Notification spam","Accessibility abuse","Launcher takeover","Performance / junk cleanup","Unknown / other")).pack(anchor="w",padx=14,pady=6)
        ttk.Label(win,text="The repair result becomes evidence automatically. Use Mark Safe on the main screen only when you know an app should be excluded from Cleanup.",wraplength=560).pack(anchor="w",padx=14,pady=(4,8))
        ttk.Label(win,text="Notes").pack(anchor="w",padx=14)
        notes=tk.Text(win,height=7,wrap="word"); notes.pack(fill="both",expand=True,padx=14,pady=6)

        def save():
            now=datetime.now().isoformat(timespec="seconds"); note=notes.get("1.0","end").strip(); chosen="Leave unchanged"
            con=sqlite3.connect(DB_PATH)
            try:
                nonlocal group_id
                if not group_id:
                    group_id="repair_"+datetime.now().strftime("%Y%m%d%H%M%S%f")
                    con.execute("INSERT INTO repair_groups(id,recorded_at,problem_tag,fixed_problem,notes,app_count) VALUES(?,?,?,?,?,?)",(group_id,now,reason.get(),fixed.get(),note,len(apps)))
                    for app in apps:
                        con.execute("""INSERT INTO repair_outcomes(recorded_at,package_name,app_name,apk_sha256,action,fixed_problem,reason_tag,notes,repair_group_id,classification_after) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                    (now,app.get("package"),app.get("app_name") or app.get("package"),app.get("sha256"),"Technician review",fixed.get(),reason.get(),note,group_id,None if chosen=="Leave unchanged" else chosen))
                else:
                    con.execute("UPDATE repair_groups SET problem_tag=?,fixed_problem=?,notes=? WHERE id=?",(reason.get(),fixed.get(),note,group_id))
                    con.execute("UPDATE repair_outcomes SET fixed_problem=?,reason_tag=?,notes=?,classification_after=? WHERE repair_group_id=?",(fixed.get(),reason.get(),note,None if chosen=="Leave unchanged" else chosen,group_id))
                field={"Yes":"times_fix_yes","No":"times_fix_no","Unsure":"times_fix_unsure"}[fixed.get()]
                for app in apps:
                    con.execute(f"UPDATE knowledge_apps SET {field}={field}+1,updated_at=? WHERE package_name=?",(now,app.get("package")))
                con.commit()
            finally: con.close()
            shared_push_repair(apps, fixed.get(), reason.get(), note, group_id)
            if chosen != "Leave unchanged":
                cls=chosen.lower()
                for app in apps:
                    db_classify(app["package"],cls,note,app.get("app_name") or app["package"]); knowledge_classify(app,cls,note)
                    app["classification"]=cls; app["reputation"]=reputation_label(app)
            if group_id == self.pending_repair_group:
                self.pending_repair_group=None; self.pending_repair_apps=[]
            # The saved repair result is a production-sync transaction boundary.
            # Push the authoritative cumulative local snapshot immediately so the
            # shared Apps sheet reflects the removal/outcome without waiting for
            # another startup, device connection or manual Sync Now.
            self.production_sync("repair-outcome", force=True)
            win.destroy(); self.retriage(); self.update_selection_summary(); messagebox.showinfo("Repair Intelligence","Repair outcome saved and queued for Shared Knowledge sync. Future scans of this package will show its accumulated repair history when selected.")
        ttk.Button(win,text="Save Repair Intelligence",command=save).pack(pady=(4,14))

    def classify(self, cls):
        apps_to_classify = self.action_apps()
        if not apps_to_classify:
            return

        note = simpledialog.askstring(
            "Notes",
            f"Optional note for {cls} classification:",
            parent=self
        )
        if note is None:
            note = ""

        for app in apps_to_classify:
            db_classify(
                app["package"],
                cls,
                note,
                app["app_name"]
            )
            app["classification"] = cls
            app["reputation"] = effective_reputation_label(app)
            knowledge_classify(app, cls, note)
            if cls.lower() == "safe":
                shared_push_classification(app, "safe", note)

        self.retriage()

    def notes(self):
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showinfo(
                "Edit notes", "Select one application."
            )
            return

        app = self.rows[selected[0]]
        rep = db_rep(app["package"]) or {}

        note = simpledialog.askstring(
            "App Notes",
            app["package"],
            initialvalue=rep.get("notes", ""),
            parent=self
        )

        if note is not None:
            db_classify(
                app["package"],
                rep.get("classification", "unknown"),
                note,
                app["app_name"]
            )

    def _resolve_names_for_apps(self, apps, label):
        if not apps or not self.device_serial:
            return

        pending = [
            a for a in apps
            if a.get("identity_state") not in ("Resolved", "No label")
        ]

        if not pending:
            self.status(f"{label}: names already resolved")
            return

        serial = self.device_serial

        def worker():
            total = len(pending)
            resolved = 0
            no_label = 0
            pull_errors = 0
            aapt_errors = 0
            other_errors = 0
            first_error = None

            resolver_log(
                f"START {label}: {total} apps on device {serial}"
            )
            self.status(f"{label}: starting resolver...")

            resolver_log("Checking installed AAPT2 path")
            aapt2 = find_aapt2()
            resolver_log(f"AAPT2 locator returned: {aapt2!r}")
            if not aapt2:
                msg = (
                    "AAPT2 tools are missing from this Android Cleaner installation. Reinstall or update Android Cleaner. "
                    "then reopen Android Cleaner."
                )
                resolver_log("ERROR " + msg)
                self.status("App-name resolver unavailable: AAPT2 not found")
                self.after(
                    0,
                    lambda: messagebox.showwarning("AAPT2 not found", msg)
                )
                return

            resolver_log(f"AAPT2 {aapt2}")

            for idx, app in enumerate(pending, 1):
                if serial != self.device_serial:
                    resolver_log("STOP device changed during resolution")
                    return

                app["identity_state"] = "Resolving..."
                self.status(
                    f"{label}: {idx}/{total} • {app['package']}"
                )
                self.after(0, self.apply_view)

                try:
                    resolver_log(
                        f"{idx}/{total} pull/start {app['package']}"
                    )
                    real_label, sha256_hex, _size = pull_apk_identity(
                        serial, app
                    )
                    resolver_log(
                        f"{idx}/{total} pull/done {app['package']} "
                        f"label={real_label!r}"
                    )

                    app["sha256"] = sha256_hex
                    app["icon_path"] = icon_cache_path(sha256_hex)

                    if real_label:
                        app["app_name"] = real_label
                        app["identity_state"] = "Resolved"
                        identity_set(app, real_label, sha256_hex)
                        knowledge_promote_identity(app)

                        rep = db_rep(app["package"]) or {}
                        db_classify(
                            app["package"],
                            rep.get("classification", "unknown"),
                            rep.get("notes", ""),
                            real_label
                        )
                        resolved += 1
                    else:
                        app["app_name"] = app["package"]
                        app["identity_state"] = "No label"
                        identity_set(app, "", sha256_hex)
                        no_label += 1

                except Exception as e:
                    text = str(e)
                    if text.startswith("APK pull failed:"):
                        app["identity_state"] = "Pull error"
                        pull_errors += 1
                    elif "AAPT2" in text:
                        app["identity_state"] = "AAPT2 error"
                        aapt_errors += 1
                    else:
                        app["identity_state"] = "Error"
                        other_errors += 1

                    resolver_log(
                        f"{idx}/{total} ERROR {app['package']}: {e!r}"
                    )

                    if first_error is None:
                        first_error = text

                self.after(0, self.apply_view)

            unresolved = sum(
                1 for a in pending
                if a.get("identity_state") not in ("Resolved", "No label")
            )
            total_errors = pull_errors + aapt_errors + other_errors
            summary = (
                f"{label} complete: {resolved}/{total} resolved"
                f" • {no_label} no label"
                f" • {pull_errors} pull errors"
                f" • {aapt_errors} AAPT2 errors"
                f" • {other_errors} other errors"
                f" • {unresolved} unresolved"
            )
            resolver_log("FINISH " + summary)
            self.status(summary)

            # Human-visible labels are themselves diagnostic evidence (Cleaner, QR,
            # PDF reader, launcher, etc.). Re-run triage after resolution so an app
            # discovered by the cheap package prefilter can enter Cleanup immediately.
            self.after(0, self.retriage)

            # For small Cleanup batches, surface one concise warning.
            # For full-phone Resolve All runs, keep the UI quiet and rely on
            # per-row states + the Resolver Log instead of a giant popup.
            if total_errors and first_error and total <= 20:
                msg = (
                    summary
                    + "\n\nFirst error:\n"
                    + first_error
                    + "\n\nDiagnostic log:\n"
                    + str(RESOLVER_LOG)
                )
                self.after(
                    0,
                    lambda m=msg: messagebox.showwarning(
                        "App-name resolver", m
                    )
                )

        self.bg(worker)

    def resolve_view_names(self, mode=None):
        mode = mode or self.view_var.get()
        if mode == "Cleanup":
            apps = [a for a in self.all_apps if a.get("cleanup_candidate", False)]
            label = "Cleanup names"
        elif mode == "Review":
            apps = [a for a in self.all_apps if a.get("priority") == "CHECK"]
            label = "Review names"
        elif mode == "Games":
            apps = [
                a for a in self.all_apps
                if a.get("is_game")
                and a.get("app_type") not in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM")
            ]
            label = "Game names"
        elif mode == "Unused Apps":
            apps = [
                a for a in self.all_apps
                if a.get("unused_state")
                and a.get("app_type") not in ("SYSTEM", "OEM / SYSTEM", "UPDATED SYSTEM")
            ]
            label = "Unused Apps names"
        else:
            return

        pending = [
            a for a in apps
            if a.get("identity_state") not in ("Resolved", "No label")
        ]
        if pending:
            self._resolve_names_for_apps(apps, label)

    def resolve_cleanup_names(self):
        self.resolve_view_names("Cleanup")

    def resolve_all_names(self):
        self._resolve_names_for_apps(
            list(self.all_apps),
            "All app names"
        )

    def retry_name_errors(self):
        apps = [
            a for a in self.all_apps
            if a.get("identity_state") in (
                "Error", "No label", "Pending", "Pull error", "AAPT2 error"
            )
        ]
        if not apps:
            self.status("No unresolved/error app names to retry")
            return
        self._resolve_names_for_apps(apps, "Retry names")


    def export_knowledge_db_ui(self):
        path=filedialog.asksaveasfilename(
            title="Export Knowledge Database",defaultextension=".db",
            initialfile=f"The_iPhone_Guy_Knowledge_{datetime.now().strftime('%Y-%m-%d')}.db",
            filetypes=[("SQLite database","*.db"),("All files","*.*")]
        )
        if not path: return
        try:
            export_knowledge_database(path)
            messagebox.showinfo("Knowledge DB","Knowledge database exported successfully.")
        except Exception as e:
            messagebox.showerror("Export failed",str(e))

    def import_knowledge_db_ui(self):
        path=filedialog.askopenfilename(
            title="Import Knowledge Database",
            filetypes=[("SQLite database","*.db"),("All files","*.*")]
        )
        if not path: return
        if not messagebox.askyesno(
            "Import Knowledge Database",
            "Replace the local Cleaner database with this database?\\n\\n"
            "The current database will be backed up first."
        ): return
        try:
            import_knowledge_database(path)
            messagebox.showinfo(
                "Knowledge DB","Import complete. Restart Android Cleaner before scanning."
            )
        except Exception as e:
            messagebox.showerror("Import failed",str(e))

    def open_adb_log(self):
        try:
            if not ADB_AUDIT_LOG.exists():
                ADB_AUDIT_LOG.write_text(
                    "No ADB commands logged yet.\n",
                    encoding="utf-8"
                )
            os.startfile(str(ADB_AUDIT_LOG))
        except Exception as e:
            messagebox.showerror("ADB Log", str(e))

    def open_resolver_log(self):
        try:
            if not RESOLVER_LOG.exists():
                RESOLVER_LOG.write_text(
                    "No resolver activity logged yet.\n",
                    encoding="utf-8"
                )
            os.startfile(str(RESOLVER_LOG))
        except Exception as e:
            messagebox.showerror("Resolver Log", str(e))

    def configure_online_key(self):
        current = get_malwarebazaar_key()
        key = simpledialog.askstring(
            "MalwareBazaar Auth-Key",
            "Paste your abuse.ch MalwareBazaar Auth-Key.\n\n"
            "The key is stored only on this Windows PC.\n"
            "Only SHA-256 hashes are sent for lookups; APK files are not uploaded.",
            initialvalue=current,
            show="*" if current else None,
            parent=self
        )
        if key is not None:
            set_malwarebazaar_key(key)
            messagebox.showinfo(
                "Saved",
                "MalwareBazaar Auth-Key saved on this PC."
            )

    def _ensure_malwarebazaar_key(self):
        key = get_malwarebazaar_key()
        if not key:
            messagebox.showinfo(
                "MalwareBazaar key required",
                "MalwareBazaar requires an Auth-Key.\n\n"
                "Use the 'MalwareBazaar Key' button first."
            )
            return None
        return key

    def check_online_selected(self):
        action_apps = self.action_apps()
        selected = [i for i in self.tree.get_children("")
                    if self.tree.set(i, "package") in {a["package"] for a in action_apps}]
        if not selected:
            messagebox.showinfo(
                "Check Selected",
                "Select one or more apps to check."
            )
            return
        apps = [self.rows[i] for i in selected]
        self._run_online_checks(apps, "selected apps")

    def check_online_cleanup(self):
        apps = [
            a for a in self.all_apps
            if a.get("cleanup_candidate", False)
        ]
        if not apps:
            messagebox.showinfo(
                "Check Cleanup",
                "There are currently no Cleanup candidates to check."
            )
            return
        self._run_online_checks(apps, "Cleanup candidates")

    def check_online_all(self):
        if not self.all_apps:
            messagebox.showinfo(
                "Check All Apps",
                "Scan the device first."
            )
            return

        if not messagebox.askyesno(
            "Check All Apps",
            f"This will hash and query all {len(self.all_apps)} third-party apps.\n\n"
            "It can take several minutes, especially on large apps.\n"
            "Normal scanning remains fast; this full online scan only runs when requested.\n\n"
            "Continue?"
        ):
            return

        self._run_online_checks(list(self.all_apps), "all apps")

    def _run_online_checks(self, apps, label):
        key = self._ensure_malwarebazaar_key()
        if not key:
            return

        serial = self.device_serial
        if not serial:
            messagebox.showwarning(
                "No device",
                "Connect and scan a device first."
            )
            return

        # Deduplicate by package in case a view ever contains duplicate rows.
        dedup = []
        seen = set()
        for app in apps:
            if app["package"] not in seen:
                dedup.append(app)
                seen.add(app["package"])
        apps = dedup

        def worker():
            total = len(apps)
            matches = 0
            cached = 0
            errors = 0

            for idx, app in enumerate(apps, 1):
                try:
                    self.status(
                        f"Online scan {idx}/{total}: hashing {app['app_name']}..."
                    )

                    sha256_hex, size = pull_apk_and_hash(serial, app)
                    app["sha256"] = sha256_hex

                    ident = identity_get(app)
                    if ident and ident.get("app_label"):
                        app["app_name"] = ident["app_label"]
                        app["identity_state"] = "Resolved"

                    cached_row = cache_get(sha256_hex)
                    if cached_row and cached_row.get("source") == "MalwareBazaar":
                        cached += 1
                        status = cached_row.get("status", "")
                        details = cached_row.get("details", "")

                        if status == "match":
                            app["online_status"] = (
                                f"MATCH: {details}" if details else "MATCH"
                            )
                            matches += 1
                        elif status == "no_match":
                            app["online_status"] = "No exact match"
                        else:
                            app["online_status"] = details or "Cached result"
                        continue

                    self.status(
                        f"Online scan {idx}/{total}: querying MalwareBazaar..."
                    )

                    result = malwarebazaar_lookup(sha256_hex, key)
                    q = result.get("query_status", "")

                    if q == "ok":
                        data = result.get("data") or []
                        first = data[0] if data else {}
                        signature = (
                            first.get("signature")
                            or first.get("file_type")
                            or "known sample"
                        )
                        app["online_status"] = f"MATCH: {signature}"
                        cache_set(
                            sha256_hex,
                            "MalwareBazaar",
                            "match",
                            signature
                        )
                        matches += 1

                    elif q in ("hash_not_found", "no_results"):
                        app["online_status"] = "No exact match"
                        cache_set(
                            sha256_hex,
                            "MalwareBazaar",
                            "no_match",
                            ""
                        )

                    elif q == "no_api_key":
                        app["online_status"] = "Auth-Key rejected"
                        cache_set(
                            sha256_hex,
                            "MalwareBazaar",
                            "error",
                            "Auth-Key rejected"
                        )

                    else:
                        text = f"No match ({q or 'unknown response'})"
                        app["online_status"] = text
                        cache_set(
                            sha256_hex,
                            "MalwareBazaar",
                            "other",
                            text
                        )

                except Exception as e:
                    errors += 1
                    app["online_status"] = "Lookup error"
                    # Don't interrupt a full scan with a popup for every error.
                    if total <= 5:
                        self.after(
                            0,
                            lambda msg=str(e): messagebox.showwarning(
                                "Online reputation lookup", msg
                            )
                        )

                # Refresh progressively so matches appear immediately.
                if idx == total or idx % 3 == 0:
                    self.after(0, self.retriage)

            self.status(
                f"Online scan complete: {total} checked • "
                f"{matches} exact matches • {cached} cached • {errors} errors"
            )

            def finish():
                self.retriage()
                messagebox.showinfo(
                    "Online scan complete",
                    f"{label.capitalize()} checked: {total}\n"
                    f"Exact MalwareBazaar matches: {matches}\n"
                    f"Used cached results: {cached}\n"
                    f"Errors: {errors}"
                )

            self.after(0, finish)

        self.bg(worker)

    def uninstall(self):
        # Workshop multi-select uses the checkbox set, not Treeview's blue
        # focus/selection.  A normal row click intentionally keeps only one
        # active row for the detail panel, while checked_packages can contain
        # many apps.  Use the same action_apps() helper as classification so
        # Remove Selected operates on every checked app.
        if not self.device_serial:
            return

        apps = self.action_apps()
        if not apps:
            return

        blocked = [
            a for a in apps
            if (
                a["package"].startswith(PROTECTED_PREFIXES)
                or protected_app_type(a)
            )
        ]

        if blocked:
            messagebox.showwarning(
                "Protected packages",
                "Some selected packages are system/OEM/preloaded or otherwise "
                "protected and will not be removed:\n\n"
                + "\n".join(
                    f"{a.get('app_name', a['package'])} — "
                    f"{classify_app_type(a)} — {a['package']}"
                    for a in blocked
                )
            )

        apps = [a for a in apps if a not in blocked]
        if not apps:
            return

        text = "\n".join(
            f"• {a['app_name']} ({a['package']})"
            for a in apps
        )

        if not messagebox.askyesno(
            "Confirm uninstall",
            "Uninstall these apps?\n\n" + text
        ):
            return

        def worker():
            results = []

            for app in apps:
                self.status(f"Uninstalling {app['app_name']}...")
                code, out, err = shell(
                    self.device_serial,
                    ["pm", "uninstall", app["package"]],
                    timeout=40
                )
                ok = code == 0 and "success" in out.lower()

                if ok:
                    db_removed(app["package"])

                results.append((app, ok, out or err))

            successful=[app for app,ok,_msg in results if ok]
            if successful:
                group_id=record_removal_group(successful, getattr(self,"device_manufacturer",""), getattr(self,"device_model",""), getattr(self,"device_android_version",""))
                self.pending_repair_group=group_id
                self.pending_repair_apps=[dict(a) for a in successful]

            def finish():
                messagebox.showinfo(
                    "Results",
                    "\n\n".join(
                        f"{'REMOVED' if ok else 'FAILED'}: "
                        f"{app['app_name']}\n{msg}"
                        for app, ok, msg in results
                    )
                )
                if successful:
                    # Guided workshop flow: successful removal -> refreshed scan ->
                    # Repair Outcome opens automatically.  The pending repair group
                    # survives the rescan so the technician records the actual apps
                    # that were removed, not whichever row becomes selected later.
                    self._open_repair_outcome_after_scan = True
                self.scan()

            self.after(0, finish)

        self.bg(worker)

    def sort_by(self, col, reverse):
        data = [
            (self.tree.set(iid, col), iid)
            for iid in self.tree.get_children("")
        ]

        if col == "priority":
            order = {
                "CRITICAL": 5,
                "HIGH": 4,
                "CHECK": 3,
                "INFO": 2,
                "BASELINE": 1,
            }
            key = lambda item: order.get(item[0], 0)

        elif col in ("installed", "updated"):
            key = lambda item: parse_dt(item[0]) or datetime.min

        else:
            key = lambda item: item[0].lower()

        data.sort(key=key, reverse=reverse)

        for idx, (_, iid) in enumerate(data):
            self.tree.move(iid, "", idx)

        self.tree.heading(
            col,
            command=lambda: self.sort_by(col, not reverse)
        )

if __name__ == "__main__":
    Cleaner().mainloop()
