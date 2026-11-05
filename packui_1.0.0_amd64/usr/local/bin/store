#!/usr/bin/env python3
import http.server
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

VENDOR_DIR = Path("/usr/lib/luma-store/vendor")
if VENDOR_DIR.is_dir():
    sys.path.insert(0, str(VENDOR_DIR))

import gi
from supabase import ClientOptions, create_client

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib, Gdk, GdkPixbuf

API_BASE = "https://api.free-time.me/v2/lumastore"
PLATFORM = "linux"
APPIMAGE_DIR = Path.home() / ".local" / "bin" / "luma-store-appimages"

SUPABASE_URL = "https://ndlaevedujqxhygbyxfh.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_HlppI4ILiXV7DZkpyrDEhQ_ytb2vV6g"
SESSION_FILE = Path.home() / ".config" / "luma-store" / "session.json"
DASHBOARD_API_BASE = "https://luma.free-time.me/api/luma"

CRYPTO_OPTIONS = [
    ("bitcoin", "Bitcoin (BTC)", ["Bitcoin"]),
    ("ethereum", "Ethereum (ETH)", ["Ethereum"]),
    ("tether", "Tether (USDT)", ["Ethereum (ERC-20)", "TRON (TRC-20)", "BNB Smart Chain (BEP-20)", "Solana", "Polygon", "Avalanche C-Chain", "Arbitrum", "Optimism"]),
    ("usdc", "USD Coin (USDC)", ["Ethereum (ERC-20)", "Solana", "Base", "Arbitrum", "Optimism", "Polygon", "Avalanche C-Chain"]),
    ("bnb", "BNB", ["BNB Smart Chain (BEP-20)", "BNB Beacon Chain"]),
    ("solana", "Solana (SOL)", ["Solana"]),
    ("xrp", "XRP", ["XRP Ledger"]),
    ("cardano", "Cardano (ADA)", ["Cardano"]),
    ("dogecoin", "Dogecoin (DOGE)", ["Dogecoin"]),
    ("tron", "TRON (TRX)", ["TRON"]),
    ("polkadot", "Polkadot (DOT)", ["Polkadot"]),
    ("avalanche", "Avalanche (AVAX)", ["Avalanche C-Chain", "Avalanche P-Chain"]),
    ("chainlink", "Chainlink (LINK)", ["Ethereum (ERC-20)", "BNB Smart Chain (BEP-20)", "Polygon", "Arbitrum", "Optimism"]),
    ("polygon", "Polygon (POL)", ["Polygon", "Ethereum (ERC-20)"]),
    ("litecoin", "Litecoin (LTC)", ["Litecoin"]),
    ("bitcoin_cash", "Bitcoin Cash (BCH)", ["Bitcoin Cash"]),
    ("stellar", "Stellar (XLM)", ["Stellar"]),
    ("monero", "Monero (XMR)", ["Monero"]),
    ("toncoin", "Toncoin (TON)", ["TON"]),
    ("shiba_inu", "Shiba Inu (SHIB)", ["Ethereum (ERC-20)", "Shibarium"]),
]


class LumaApi:
    @staticmethod
    def _get(path, params=None):
        query = urllib.parse.urlencode(params or {})
        url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Luma-Store-Linux/0.1"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def apps(cls, search=None):
        params = {"platform": PLATFORM}
        if search:
            params["search"] = search
        return cls._get("/apps", params)

    @classmethod
    def app(cls, app_id):
        return cls._get(f"/apps/{urllib.parse.quote(str(app_id), safe='')}", {"platform": PLATFORM})


class FileSupabaseStorage:
    """Simple file-backed storage adapter for supabase-py sessions."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self):
        try:
            if not self.path.exists():
                return {}
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get_item(self, key):
        with self._lock:
            return self._read().get(key)

    def set_item(self, key, value):
        with self._lock:
            data = self._read()
            data[key] = value
            self._write(data)

    def remove_item(self, key):
        with self._lock:
            data = self._read()
            data.pop(key, None)
            if data:
                self._write(data)
            else:
                try:
                    self.path.unlink(missing_ok=True)
                except Exception:
                    pass


class NativeSupabaseAuth:
    """Native Supabase authentication backed by supabase-py."""

    def __init__(self):
        self.client = create_client(
            SUPABASE_URL,
            SUPABASE_PUBLISHABLE_KEY,
            options=ClientOptions(
                flow_type="pkce",
                persist_session=True,
                auto_refresh_token=True,
                storage=FileSupabaseStorage(SESSION_FILE),
            ),
        )

    @staticmethod
    def _as_dict(value):
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return {
            key: getattr(value, key)
            for key in dir(value)
            if not key.startswith("_") and not callable(getattr(value, key, None))
        }

    def sign_out(self):
        try:
            self.client.auth.sign_out()
        finally:
            try:
                SESSION_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def session(self):
        try:
            return self.client.auth.get_session()
        except Exception:
            return None

    def access_token(self):
        session = self.session()
        return getattr(session, "access_token", None) if session else None

    def user(self):
        if not self.access_token():
            return None
        response = self.client.auth.get_user()
        return self._as_dict(getattr(response, "user", None))

    def provider(self):
        user = self.user() or {}
        metadata = user.get("app_metadata") or {}
        return metadata.get("provider") or "OAuth"

    def provider_token(self):
        session = self.session()
        return getattr(session, "provider_token", None) if session else None

    def login(self, provider):
        result = {"code": None, "error": None}

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                result["code"] = query.get("code", [None])[0]
                result["error"] = query.get("error_description", query.get("error", [None]))[0]
                ok = bool(result["code"]) and not result["error"]
                title = "Luma Store login complete" if ok else "Luma Store login failed"
                message = (
                    "You can close this tab and return to Luma Store."
                    if ok
                    else (result["error"] or "No authorization code was returned.")
                )
                html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui;background:#09111f;color:#eef2ff;display:grid;place-items:center;min-height:100vh;margin:0}}
main{{max-width:520px;padding:32px;border:1px solid #ffffff22;border-radius:28px;background:#ffffff10;box-shadow:0 20px 60px #0008}}
h1{{margin-top:0}}p{{color:#b9c3d5;line-height:1.6}}</style></head><body><main><h1>{title}</h1><p>{message}</p></main></body></html>"""
                payload = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format, *_args):
                return

        server = http.server.HTTPServer(("127.0.0.1", 8765), CallbackHandler)
        server.timeout = 180
        callback = f"http://127.0.0.1:{server.server_port}/auth/callback"

        options = {"redirect_to": callback}
        if provider == "github":
            options["scopes"] = "read:user public_repo"

        oauth = self.client.auth.sign_in_with_oauth({
            "provider": provider,
            "options": options,
        })
        auth_url = getattr(oauth, "url", None)
        if not auth_url:
            server.server_close()
            raise RuntimeError("Supabase did not return an OAuth URL.")

        if not webbrowser.open(str(auth_url)):
            server.server_close()
            raise RuntimeError("Could not open the system browser.")

        server.handle_request()
        server.server_close()

        if result["error"]:
            raise RuntimeError(result["error"])
        if not result["code"]:
            raise RuntimeError("Login timed out or no authorization code was returned.")

        return self.client.auth.exchange_code_for_session({
            "auth_code": result["code"],
        })


class DeveloperDashboardApi:
    SUBMISSION_COLUMNS = (
        "id,user_id,name,short_description,description,status,submitted_at,status_updated_at,"
        "approved_at,rejected_at,review_message,category,categories,subcategory,license_type,"
        "icon_url,version,version_code,package_name,changelog,screenshots,localized_metadata,"
        "platform,platforms,separate_platform_repos,linux_package_base,download_url,repo_url,link,"
        "source_code_url,author_name,author_email,author_website,website_url,issue_tracker_url,"
        "translation_url,changelog_url,ant_features,store_app_id,draft_step,draft_updated_at"
    )

    def __init__(self, auth):
        self.auth = auth

    @staticmethod
    def _data(response):
        return getattr(response, "data", None)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _user(self):
        user = self.auth.user()
        if not user or not user.get("id"):
            raise RuntimeError("Sign in to use the developer dashboard.")
        return user

    def submissions(self):
        user = self._user()
        response = (
            self.auth.client.table("luma_submissions")
            .select(self.SUBMISSION_COLUMNS)
            .eq("user_id", user["id"])
            .order("submitted_at", desc=True)
            .execute()
        )
        rows = self._data(response) or []

        # Match the web dashboard: hide stale duplicate approved submissions when
        # a canonical published store app points at a different submission.
        apps_response = (
            self.auth.client.table("store_apps")
            .select("id,luma_submission_id,developer_name")
            .eq("developer_id", user["id"])
            .execute()
        )
        store_apps = self._data(apps_response) or []
        canonical = {
            row.get("luma_submission_id")
            for row in store_apps
            if row.get("luma_submission_id")
        }
        if canonical:
            rows = [
                row for row in rows
                if row.get("status") != "Approved" or row.get("id") in canonical
            ]
        return rows

    def categories(self):
        response = (
            self.auth.client.table("store_categories")
            .select("name")
            .order("name")
            .execute()
        )
        return [row.get("name") for row in (self._data(response) or []) if row.get("name")]

    def licenses(self):
        response = (
            self.auth.client.table("store_license_types")
            .select("name,display_name")
            .eq("open_source", True)
            .order("display_name")
            .execute()
        )
        return self._data(response) or []

    def analytics(self):
        self._user()
        response = self.auth.client.rpc("luma_my_developer_analytics").execute()
        return self._data(response) or {
            "total_downloads": 0,
            "apps": [],
            "platforms": [],
            "app_platforms": [],
            "daily": [],
            "funding": [],
        }

    def profile(self):
        user = self._user()
        response = (
            self.auth.client.table("luma_developer_profiles")
            .select("display_name,bio,website_url,github_url,gitlab_url,avatar_url,verified")
            .eq("developer_id", user["id"])
            .limit(1)
            .execute()
        )
        rows = self._data(response) or []
        return rows[0] if rows else {}

    def save_profile(self, profile):
        user = self._user()
        payload = {
            "developer_id": user["id"],
            "display_name": profile.get("display_name") or None,
            "bio": profile.get("bio") or None,
            "website_url": profile.get("website_url") or None,
            "github_url": profile.get("github_url") or None,
            "gitlab_url": profile.get("gitlab_url") or None,
            "avatar_url": profile.get("avatar_url") or None,
            "updated_at": self._now(),
        }
        response = (
            self.auth.client.table("luma_developer_profiles")
            .upsert(payload, on_conflict="developer_id")
            .execute()
        )
        return self._data(response)

    def funding(self):
        user = self._user()
        response = (
            self.auth.client.table("luma_developer_funding")
            .select("donate_url,liberapay,opencollective,bitcoin,litecoin,crypto_addresses")
            .eq("developer_id", user["id"])
            .limit(1)
            .execute()
        )
        rows = self._data(response) or []
        return rows[0] if rows else {}

    def save_funding(self, funding):
        user = self._user()
        crypto = {
            key: str(value).strip()
            for key, value in (funding.get("crypto_addresses") or {}).items()
            if str(value).strip()
        }
        payload = {
            "developer_id": user["id"],
            "donate_url": funding.get("donate_url") or None,
            "liberapay": funding.get("liberapay") or None,
            "opencollective": funding.get("opencollective") or None,
            "crypto_addresses": crypto,
            "bitcoin": crypto.get("bitcoin::Bitcoin") or None,
            "litecoin": crypto.get("litecoin::Litecoin") or None,
            "updated_at": self._now(),
        }
        response = (
            self.auth.client.table("luma_developer_funding")
            .upsert(payload, on_conflict="developer_id")
            .execute()
        )
        return self._data(response)

    def status_data(self, submission_id=None):
        user = self._user()
        query = (
            self.auth.client.table("luma_submissions")
            .select(
                "id,name,description,link,category,status,submitted_at,review_message,"
                "changelog,status_updated_at,approved_at,rejected_at"
            )
            .eq("user_id", user["id"])
        )
        if submission_id:
            query = query.eq("id", submission_id)
        rows = self._data(query.order("submitted_at", desc=True).execute()) or []

        if not submission_id:
            store_apps = self._data(
                self.auth.client.table("store_apps")
                .select("luma_submission_id")
                .eq("developer_id", user["id"])
                .execute()
            ) or []
            canonical = {row.get("luma_submission_id") for row in store_apps if row.get("luma_submission_id")}
            if canonical:
                rows = [
                    row for row in rows
                    if row.get("status") != "Approved" or row.get("id") in canonical
                ]

        history = []
        ids = [row.get("id") for row in rows if row.get("id")]
        if ids:
            history = self._data(
                self.auth.client.table("luma_submission_status_history")
                .select("id,submission_id,status,review_message,created_at")
                .in_("submission_id", ids)
                .order("created_at")
                .execute()
            ) or []
        return {"submissions": rows, "history": history}

    def notifications(self):
        user = self._user()
        response = (
            self.auth.client.table("luma_developer_notifications")
            .select("id,submission_id,type,title,message,created_at,read_at")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        return self._data(response) or []

    def mark_notification_read(self, notification_id):
        user = self._user()
        return self._data(
            self.auth.client.table("luma_developer_notifications")
            .update({"read_at": self._now()})
            .eq("id", notification_id)
            .eq("user_id", user["id"])
            .execute()
        )

    def review_comments(self, submission_id):
        self._user()
        response = (
            self.auth.client.table("luma_review_comments")
            .select("id,submission_id,user_id,body,created_at")
            .eq("submission_id", submission_id)
            .order("created_at")
            .execute()
        )
        return self._data(response) or []

    def add_review_comment(self, submission_id, body):
        user = self._user()
        body = str(body or "").strip()
        if not body:
            raise RuntimeError("Comment cannot be empty.")
        response = (
            self.auth.client.table("luma_review_comments")
            .insert({
                "submission_id": submission_id,
                "user_id": user["id"],
                "body": body,
            })
            .execute()
        )
        return self._data(response)

    def submission_details(self, submission_id):
        user = self._user()
        response = (
            self.auth.client.table("luma_submissions")
            .select(self.SUBMISSION_COLUMNS)
            .eq("id", submission_id)
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        rows = self._data(response) or []
        if not rows:
            raise RuntimeError("Submission not found or you do not have access to it.")
        submission = rows[0]

        scan_rows = self._data(
            self.auth.client.table("luma_security_scans")
            .select(
                "id,status,risk_level,findings,permissions,scanned_at,created_at,provider,"
                "virus_total_permalink,malicious_count,suspicious_count,harmless_count,"
                "undetected_count,error_message,file_name,file_size_bytes"
            )
            .eq("submission_id", submission_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ) or []
        scan = scan_rows[0] if scan_rows else None

        history = self.status_data(submission_id).get("history", [])
        comments = self.review_comments(submission_id)

        versions = []
        if submission.get("package_name"):
            versions = self._data(
                self.auth.client.table("luma_app_versions")
                .select("id,version,version_code,changelog,download_url,status,created_at,published_at")
                .eq("package_name", submission["package_name"])
                .order("created_at", desc=True)
                .execute()
            ) or []

        published = None
        store_app_id = submission.get("store_app_id")
        if store_app_id:
            published_rows = self._data(
                self.auth.client.table("store_apps")
                .select(
                    "id,name,short_description,description,version,version_code,package_name,"
                    "license_type,repo_url,changelog,ant_features,updated_at,developer_name"
                )
                .eq("id", store_app_id)
                .limit(1)
                .execute()
            ) or []
            published = published_rows[0] if published_rows else None
        elif submission.get("status") == "Approved":
            published_rows = self._data(
                self.auth.client.table("store_apps")
                .select(
                    "id,name,short_description,description,version,version_code,package_name,"
                    "license_type,repo_url,changelog,ant_features,updated_at,developer_name"
                )
                .eq("luma_submission_id", submission_id)
                .limit(1)
                .execute()
            ) or []
            published = published_rows[0] if published_rows else None

        published_platforms = []
        stats = None
        if published and published.get("id"):
            published_platforms = self._data(
                self.auth.client.table("store_app_platforms")
                .select(
                    "id,platform,package_type,linux_package_base,download_url,file_size_mb,"
                    "sha256,artifact_verified_at,artifact_size_bytes,permissions"
                )
                .eq("app_id", published["id"])
                .order("platform")
                .execute()
            ) or []
            stat_rows = self._data(self.auth.client.rpc("get_my_luma_download_stats").execute()) or []
            stats = next((row for row in stat_rows if row.get("app_id") == published["id"]), None)

        return {
            "submission": submission,
            "scan": scan,
            "history": history,
            "comments": comments,
            "versions": versions,
            "published": published,
            "published_platforms": published_platforms,
            "stats": stats,
        }

    def _submission_request(self, body):
        access_token = self.auth.access_token()
        if not access_token:
            raise RuntimeError("Your Luma Store session expired. Sign in again.")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Luma-Store-Linux/1.1",
        }
        provider_token = self.auth.provider_token()
        if provider_token:
            headers["X-GitHub-Token"] = provider_token

        request = urllib.request.Request(
            f"{DASHBOARD_API_BASE}/submissions",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = payload.get("error") or payload.get("message") or raw
            except Exception:
                message = raw
            raise RuntimeError(message or f"Submission failed with HTTP {error.code}") from error

        saved = payload.get("submission") if isinstance(payload, dict) else None
        if not saved:
            raise RuntimeError("Submission could not be saved.")
        return saved

    def save_draft(self, submission, editing_id=None, draft_step=1):
        return self._submission_request({
            "submission": submission,
            "editingId": editing_id,
            "draft": True,
            "draftStep": draft_step,
        })

    def save_submission(self, submission, editing_id=None, editing_status=None):
        if not self.auth.provider_token():
            raise RuntimeError(
                "GitHub authorization is required. Sign out and sign in with GitHub again."
            )
        return self._submission_request({
            "submission": submission,
            "editingId": editing_id,
            "editingStatus": editing_status,
        })

    def submit_linux_app(self, submission):
        return self.save_submission(submission)

    def remove_submission(self, submission_id):
        access_token = self.auth.access_token()
        if not access_token:
            raise RuntimeError("Your Luma Store session expired. Sign in again.")
        url = f"{DASHBOARD_API_BASE}/submissions?id={urllib.parse.quote(str(submission_id), safe='')}"
        request = urllib.request.Request(
            url,
            method="DELETE",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Luma-Store-Linux/1.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = payload.get("error") or payload.get("message") or raw
            except Exception:
                message = raw
            raise RuntimeError(message or f"Action failed with HTTP {error.code}") from error


class LumaStoreWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Luma Store")
        self.set_default_size(960, 680)
        self.apps = []
        self.current_app = None
        self.auth = NativeSupabaseAuth()
        self.dashboard_api = DeveloperDashboardApi(self.auth)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)
            self.set_app_paintable(True)

        header = Gtk.HeaderBar(title="Luma Store", subtitle="Native Linux client", show_close_button=True)
        header.get_style_context().add_class("glass-header")
        self.set_titlebar(header)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.get_style_context().add_class("app-root")
        self.add(root)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav.set_border_width(10)
        nav.get_style_context().add_class("glass-nav")
        root.pack_start(nav, False, False, 0)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, transition_duration=180)
        root.pack_start(self.stack, True, True, 0)
        for label, page in (("Discover", "discover"), ("Search", "search"), ("Categories", "categories"), ("Dev Dashboard", "dashboard")):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class("nav-button")
            if page == "discover":
                button.connect("clicked", lambda _b: self.reset_and_show_discover())
            elif page == "dashboard":
                button.connect("clicked", lambda _b: self.open_dashboard())
            else:
                button.connect("clicked", lambda _b, name=page: self.show_page(name))
            nav.pack_start(button, False, False, 0)

        self.discover = self.page_box()
        self.discover.pack_start(self.heading("Discover Linux apps"), False, False, 0)
        self.discover_status = Gtk.Label(label="Loading apps from Luma Store…", xalign=0)
        self.discover.pack_start(self.discover_status, False, False, 0)
        self.discover_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.discover.pack_start(self.discover_list, True, True, 0)

        search_page = self.page_box()
        search_page.pack_start(self.heading("Search"), False, False, 0)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.connect("activate", self.search_apps)
        search_page.pack_start(self.search_entry, False, False, 0)
        self.search_status = Gtk.Label(label="Search Linux apps from the API.", xalign=0)
        search_page.pack_start(self.search_status, False, False, 0)
        self.search_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        search_page.pack_start(self.search_list, True, True, 0)

        self.categories_page = self.page_box()
        self.categories_page.pack_start(self.heading("Categories"), False, False, 0)
        self.categories_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.categories_page.pack_start(self.categories_box, False, False, 0)

        self.dashboard = self.page_box()
        dashboard_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        dashboard_titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        dashboard_titles.pack_start(self.heading("Developer Dashboard"), False, False, 0)
        dashboard_subtitle = Gtk.Label(
            label="Manage and review your Luma Store submissions in a fully native GTK view.",
            xalign=0,
            wrap=True,
        )
        dashboard_subtitle.get_style_context().add_class("muted")
        dashboard_titles.pack_start(dashboard_subtitle, False, False, 0)
        dashboard_header.pack_start(dashboard_titles, True, True, 0)
        self.dashboard.pack_start(dashboard_header, False, False, 0)

        self.dashboard_auth_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.dashboard_auth_card.get_style_context().add_class("glass-card")
        self.dashboard_auth_card.set_border_width(16)
        self.dashboard_auth_status = Gtk.Label(label="Sign in to use the developer dashboard.", xalign=0, wrap=True)
        self.dashboard_auth_card.pack_start(self.dashboard_auth_status, False, False, 0)

        self.dashboard_login_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.github_login_button = Gtk.Button(label="Sign in with GitHub")
        self.gitlab_login_button = Gtk.Button(label="Sign in with GitLab")
        self.github_login_button.get_style_context().add_class("glass-primary")
        self.github_login_button.connect("clicked", self.start_dashboard_login, "github")
        self.gitlab_login_button.connect("clicked", self.start_dashboard_login, "gitlab")
        self.dashboard_login_buttons.pack_start(self.github_login_button, False, False, 0)
        self.dashboard_login_buttons.pack_start(self.gitlab_login_button, False, False, 0)
        self.dashboard_auth_card.pack_start(self.dashboard_login_buttons, False, False, 0)

        self.dashboard_session_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        refresh_button = Gtk.Button(label="Refresh")
        refresh_button.connect("clicked", lambda _b: self.load_dashboard_submissions())
        logout_button = Gtk.Button(label="Sign out")
        logout_button.connect("clicked", self.dashboard_sign_out)
        self.dashboard_session_actions.pack_start(refresh_button, False, False, 0)
        self.dashboard_session_actions.pack_start(logout_button, False, False, 0)
        self.dashboard_auth_card.pack_start(self.dashboard_session_actions, False, False, 0)
        self.dashboard.pack_start(self.dashboard_auth_card, False, False, 0)

        self.dashboard_stats = Gtk.Label(label="No dashboard data loaded yet.", xalign=0, wrap=True)
        self.dashboard_stats.get_style_context().add_class("dashboard-stats")
        self.dashboard.pack_start(self.dashboard_stats, False, False, 0)

        dashboard_tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, page, loader in (
            ("Analytics", "dashboard_analytics", self.open_dashboard_analytics),
            ("Developer profile", "dashboard_profile", self.open_dashboard_profile),
            ("Funding", "dashboard_funding", self.open_dashboard_funding),
            ("Status & timeline", "dashboard_status", self.open_dashboard_status),
            ("Notifications", "dashboard_notifications", self.open_dashboard_notifications),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _b, callback=loader: callback())
            dashboard_tools.pack_start(button, False, False, 0)
        self.dashboard.pack_start(dashboard_tools, False, False, 0)

        self.submit_expander = Gtk.Expander(label="New app submission")
        self.submit_expander.set_expanded(False)
        submit_scrolled = Gtk.ScrolledWindow()
        submit_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        submit_scrolled.set_min_content_height(360)

        submit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        submit_box.set_border_width(14)
        submit_box.get_style_context().add_class("glass-card")
        submit_intro = Gtk.Label(
            label="Submit and maintain Android, Windows and Linux apps natively. Drafts can be saved before all required fields are complete; final submissions require GitHub verification.",
            xalign=0,
            wrap=True,
        )
        submit_intro.get_style_context().add_class("muted")
        submit_box.pack_start(submit_intro, False, False, 0)

        submit_grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        submit_box.pack_start(submit_grid, False, False, 0)
        self.submit_fields = {}
        self.submit_textviews = {}
        self.submit_platform_checks = {}
        self.submit_platform_fields = {}
        self.submit_platform_textviews = {}
        self.submit_draft_id = None
        self.submit_editing_id = None
        self.submit_editing_status = None
        self.submit_existing_localized_metadata = []
        self.submit_localizations = []
        self.submission_options_loaded = False

        def add_entry(row, key, title, placeholder=""):
            label = Gtk.Label(label=title, xalign=0)
            entry = Gtk.Entry()
            entry.set_hexpand(True)
            entry.set_placeholder_text(placeholder)
            submit_grid.attach(label, 0, row, 1, 1)
            submit_grid.attach(entry, 1, row, 1, 1)
            self.submit_fields[key] = entry
            return row + 1

        def add_text_area(row, key, title, height=76):
            label = Gtk.Label(label=title, xalign=0)
            label.set_valign(Gtk.Align.START)
            view = Gtk.TextView()
            view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            area = Gtk.ScrolledWindow()
            area.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            area.set_min_content_height(height)
            area.add(view)
            submit_grid.attach(label, 0, row, 1, 1)
            submit_grid.attach(area, 1, row, 1, 1)
            self.submit_textviews[key] = view
            return row + 1

        row = 0
        platform_label = Gtk.Label(label="Platforms", xalign=0)
        platform_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        for platform in ("Android", "Windows", "Linux"):
            check = Gtk.CheckButton(label=platform)
            self.submit_platform_checks[platform] = check
            platform_box.pack_start(check, False, False, 0)
        submit_grid.attach(platform_label, 0, row, 1, 1)
        submit_grid.attach(platform_box, 1, row, 1, 1)
        row += 1

        self.submit_separate_repos = Gtk.CheckButton(label="Different repository per platform")
        submit_grid.attach(Gtk.Label(label="Repository layout", xalign=0), 0, row, 1, 1)
        submit_grid.attach(self.submit_separate_repos, 1, row, 1, 1)
        row += 1

        row = add_entry(row, "name", "Title", "My app")
        row = add_entry(row, "repo_url", "GitHub repository", "https://github.com/owner/repository")
        row = add_entry(row, "categories", "Categories", "Development, System")
        row = add_entry(row, "license_type", "Open-source license", "GPL-3.0-only")
        row = add_entry(row, "version", "Version", "1.0.0")
        row = add_entry(row, "icon_url", "Icon URL", "https://...")
        row = add_entry(row, "android_url", "Android APK URL", "https://.../app.apk")
        row = add_entry(row, "package_name", "Android package name", "com.example.app")
        row = add_entry(row, "version_code", "Android versionCode", "1")
        row = add_entry(row, "windows_exe_url", "Windows EXE URL", "https://.../app.exe")
        row = add_entry(row, "windows_msi_url", "Windows MSI URL", "https://.../app.msi")
        row = add_entry(row, "deb_url", "Linux DEB URL", "https://.../app.deb")
        row = add_entry(row, "rpm_url", "Linux RPM URL", "https://.../app.rpm")
        row = add_text_area(row, "short_description", "Short description")
        row = add_text_area(row, "description", "Full description", 110)
        row = add_text_area(row, "changelog", "Changelog")
        row = add_text_area(row, "screenshots", "Screenshot URLs (one per line)", 90)
        row = add_entry(row, "author_name", "Author name")
        row = add_entry(row, "author_email", "Author email")
        row = add_entry(row, "author_website", "Author website", "https://...")
        row = add_entry(row, "website_url", "App website", "https://...")
        row = add_entry(row, "issue_tracker_url", "Issue tracker", "https://...")
        row = add_entry(row, "translation_url", "Translation URL", "https://...")
        row = add_entry(row, "changelog_url", "Changelog URL", "https://...")

        platform_metadata_expander = Gtk.Expander(label="Platform-specific repositories & store metadata")
        platform_metadata_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        platform_metadata_box.set_border_width(10)
        for platform in ("Android", "Windows", "Linux"):
            frame = Gtk.Frame(label=platform)
            grid = Gtk.Grid(column_spacing=10, row_spacing=8)
            grid.set_border_width(10)
            frame.add(grid)
            fields = {}
            textviews = {}
            for field_row, (key, title) in enumerate((
                ("repo_url", "Repository URL"),
                ("title", "Title"),
            )):
                label = Gtk.Label(label=title, xalign=0)
                entry = Gtk.Entry()
                entry.set_hexpand(True)
                grid.attach(label, 0, field_row, 1, 1)
                grid.attach(entry, 1, field_row, 1, 1)
                fields[key] = entry
            base_row = 2
            for offset, (key, title, height) in enumerate((
                ("short_description", "Short description", 65),
                ("description", "Full description", 95),
                ("changelog", "Changelog", 75),
                ("screenshots", "Screenshot URLs", 75),
            )):
                label = Gtk.Label(label=title, xalign=0)
                label.set_valign(Gtk.Align.START)
                view = Gtk.TextView()
                view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                scroller = Gtk.ScrolledWindow()
                scroller.set_min_content_height(height)
                scroller.add(view)
                grid.attach(label, 0, base_row + offset, 1, 1)
                grid.attach(scroller, 1, base_row + offset, 1, 1)
                textviews[key] = view
            self.submit_platform_fields[platform] = fields
            self.submit_platform_textviews[platform] = textviews
            platform_metadata_box.pack_start(frame, False, False, 0)
        platform_metadata_expander.add(platform_metadata_box)
        submit_box.pack_start(platform_metadata_expander, False, False, 0)

        localizations_expander = Gtk.Expander(label="Additional localized store metadata")
        localization_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        localization_content.set_border_width(10)
        self.submit_localizations_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        localization_content.pack_start(self.submit_localizations_box, False, False, 0)
        add_language = Gtk.Button(label="+ Add language")
        add_language.set_halign(Gtk.Align.START)
        add_language.connect("clicked", self.add_localization_form)
        localization_content.pack_start(add_language, False, False, 0)
        localizations_expander.add(localization_content)
        submit_box.pack_start(localizations_expander, False, False, 0)

        submit_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.fastlane_button = Gtk.Button(label="Load Android Fastlane metadata")
        self.fastlane_button.connect("clicked", self.load_fastlane_metadata)
        submit_actions.pack_start(self.fastlane_button, False, False, 0)
        self.submit_draft_button = Gtk.Button(label="Save draft")
        self.submit_draft_button.connect("clicked", self.save_submission_draft)
        self.submit_button = Gtk.Button(label="Submit app")
        self.submit_button.get_style_context().add_class("glass-primary")
        self.submit_button.connect("clicked", self.submit_app)
        clear_submit_button = Gtk.Button(label="Clear")
        clear_submit_button.connect("clicked", lambda _b: self.clear_submission_form())
        submit_actions.pack_start(self.submit_draft_button, False, False, 0)
        submit_actions.pack_start(self.submit_button, False, False, 0)
        submit_actions.pack_start(clear_submit_button, False, False, 0)
        submit_box.pack_start(submit_actions, False, False, 0)

        self.submit_status = Gtk.Label(xalign=0, wrap=True)
        self.submit_status.get_style_context().add_class("muted")
        submit_box.pack_start(self.submit_status, False, False, 0)

        submit_scrolled.add(submit_box)
        self.submit_expander.add(submit_scrolled)
        self.dashboard.pack_start(self.submit_expander, False, False, 0)

        submissions_title = Gtk.Label(label="My submissions", xalign=0)
        submissions_title.get_style_context().add_class("section-title")
        self.dashboard.pack_start(submissions_title, False, False, 0)
        self.dashboard_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.dashboard_list.get_style_context().add_class("transparent-list")
        self.dashboard_scrolled = Gtk.ScrolledWindow()
        self.dashboard_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.dashboard_scrolled.add(self.dashboard_list)
        self.dashboard.pack_start(self.dashboard_scrolled, True, True, 0)

        self._build_dashboard_aux_pages()

        self.details_scrolled = Gtk.ScrolledWindow()
        self.details_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.details_content = self.page_box()
        self.details_scrolled.add(self.details_content)

        back = Gtk.Button(label="← Back")
        back.set_halign(Gtk.Align.START)
        back.connect("clicked", lambda _b: self.show_page("discover"))
        self.details_content.pack_start(back, False, False, 0)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header_box.get_style_context().add_class("glass-card")
        header_box.set_border_width(14)
        self.details_icon = Gtk.Image()
        self.details_icon.set_size_request(64, 64)
        header_box.pack_start(self.details_icon, False, False, 0)

        header_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.details_title = self.heading("App")
        self.details_summary = Gtk.Label(xalign=0, wrap=True)
        header_text.pack_start(self.details_title, False, False, 0)
        header_text.pack_start(self.details_summary, False, False, 0)
        header_box.pack_start(header_text, True, True, 0)
        self.details_content.pack_start(header_box, False, False, 0)

        self.details_meta = Gtk.Label(xalign=0, wrap=True)
        self.details_download = Gtk.Label(xalign=0, selectable=True, wrap=True)
        self.install_button = Gtk.Button(label="Install")
        self.install_button.set_halign(Gtk.Align.START)
        self.install_button.get_style_context().add_class("suggested-action")
        self.install_button.connect("clicked", self.install_current_app)
        self.install_status = Gtk.Label(xalign=0, wrap=True)

        self.extra_fields_label = self.heading("Additional API Information")
        self.extra_fields_label.set_margin_top(12)
        self.extra_fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.screenshots_label = self.heading("Screenshots")
        self.screenshots_label.set_margin_top(12)
        self.screenshots_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.screenshots_scrolled = Gtk.ScrolledWindow()
        self.screenshots_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.screenshots_scrolled.set_min_content_height(200)
        self.screenshots_scrolled.add(self.screenshots_box)

        self.details_content.pack_start(self.details_meta, False, False, 0)
        self.details_content.pack_start(self.details_download, False, False, 0)
        self.details_content.pack_start(self.install_button, False, False, 0)
        self.details_content.pack_start(self.install_status, False, False, 0)
        self.details_content.pack_start(self.extra_fields_label, False, False, 0)
        self.details_content.pack_start(self.extra_fields_box, False, False, 0)
        self.details_content.pack_start(self.screenshots_label, False, False, 0)
        self.details_content.pack_start(self.screenshots_scrolled, False, False, 0)

        self.stack.add_named(self.discover, "discover")
        self.stack.add_named(search_page, "search")
        self.stack.add_named(self.categories_page, "categories")
        self.stack.add_named(self.dashboard, "dashboard")
        self.stack.add_named(self.analytics_page, "dashboard_analytics")
        self.stack.add_named(self.profile_page, "dashboard_profile")
        self.stack.add_named(self.funding_page, "dashboard_funding")
        self.stack.add_named(self.status_page, "dashboard_status")
        self.stack.add_named(self.notifications_page, "dashboard_notifications")
        self.stack.add_named(self.submission_details_page, "dashboard_app")
        self.stack.add_named(self.details_scrolled, "details")
        self.stack.set_visible_child_name("discover")

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window, .app-root {
                background-color: rgba(8, 14, 26, 0.97);
                color: #eef2ff;
            }
            headerbar.glass-header {
                background-image: linear-gradient(to bottom, rgba(31, 41, 67, 0.88), rgba(17, 24, 39, 0.82));
                border-bottom: 1px solid rgba(255, 255, 255, 0.11);
                box-shadow: 0 8px 28px rgba(0, 0, 0, 0.28);
                color: #f8fafc;
            }
            .glass-nav {
                margin: 2px 14px 8px 14px;
                padding: 6px;
                border-radius: 22px;
                border: 1px solid rgba(255, 255, 255, 0.12);
                background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.10), rgba(99, 102, 241, 0.08));
                box-shadow: 0 12px 34px rgba(0, 0, 0, 0.24);
            }
            button {
                min-height: 34px;
                padding: 7px 13px;
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.10);
                background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.10), rgba(255, 255, 255, 0.04));
                color: #e5e7eb;
                box-shadow: 0 7px 18px rgba(0, 0, 0, 0.17);
            }
            button:hover {
                background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.16), rgba(99, 102, 241, 0.12));
                border-color: rgba(165, 180, 252, 0.42);
            }
            button:active {
                background-color: rgba(99, 102, 241, 0.24);
            }
            button.nav-button {
                min-height: 36px;
                border-radius: 16px;
                box-shadow: none;
            }
            button.glass-primary, button.suggested-action {
                background-image: linear-gradient(135deg, rgba(99, 102, 241, 0.92), rgba(139, 92, 246, 0.84));
                border-color: rgba(199, 210, 254, 0.45);
                color: white;
            }
            entry, searchentry, textview, combobox button {
                min-height: 38px;
                padding: 6px 12px;
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.12);
                background-color: rgba(15, 23, 42, 0.70);
                color: #f8fafc;
            }
            textview text {
                background-color: rgba(15, 23, 42, 0.70);
                color: #f8fafc;
            }
            notebook header {
                border-radius: 16px;
                background-color: rgba(255, 255, 255, 0.055);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            notebook tab {
                min-height: 34px;
                padding: 5px 10px;
                border-radius: 12px;
            }
            notebook tab:checked {
                background-color: rgba(99, 102, 241, 0.18);
            }
            frame {
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.10);
                background-color: rgba(255, 255, 255, 0.035);
            }
            progressbar trough {
                min-height: 18px;
                border-radius: 9px;
                background-color: rgba(15, 23, 42, 0.75);
            }
            progressbar progress {
                min-height: 18px;
                border-radius: 9px;
                background-image: linear-gradient(to right, rgba(99, 102, 241, 0.9), rgba(139, 92, 246, 0.9));
            }
            .page-surface {
                background-color: rgba(8, 14, 26, 0.50);
            }
            .glass-card, .dashboard-stats {
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.11);
                background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.085), rgba(99, 102, 241, 0.055));
                box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
            }
            .dashboard-stats {
                padding: 12px 14px;
                color: #cbd5e1;
            }
            list, listbox, .transparent-list {
                background-color: transparent;
            }
            listbox row {
                margin: 5px 0;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.09);
                background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.025));
            }
            listbox row:hover {
                border-color: rgba(165, 180, 252, 0.30);
                background-color: rgba(99, 102, 241, 0.09);
            }
            scrolledwindow {
                border: none;
                background-color: transparent;
            }
            .page-title {
                font-size: 26px;
                font-weight: 700;
                color: #f8fafc;
            }
            .section-title {
                font-size: 18px;
                font-weight: 700;
                color: #f8fafc;
                margin-top: 5px;
            }
            .app-name {
                font-size: 16px;
                font-weight: 700;
                color: #f8fafc;
            }
            .muted {
                color: #aab4c5;
            }
            .status-approved { color: #86efac; }
            .status-rejected { color: #fca5a5; }
            .status-pending { color: #fde68a; }
            .status-review { color: #c4b5fd; }
        """)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.load_apps()

    def _make_dashboard_aux_page(self, title, subtitle):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = self.page_box()
        scrolled.add(content)

        back = Gtk.Button(label="← Developer Dashboard")
        back.set_halign(Gtk.Align.START)
        back.connect("clicked", lambda _b: self.open_dashboard())
        content.pack_start(back, False, False, 0)
        content.pack_start(self.heading(title), False, False, 0)
        description = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        description.get_style_context().add_class("muted")
        content.pack_start(description, False, False, 0)
        return scrolled, content

    def _build_dashboard_aux_pages(self):
        # Analytics
        self.analytics_page, analytics = self._make_dashboard_aux_page(
            "Analytics",
            "Private download analytics for your published apps and funding links.",
        )
        filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.analytics_days = Gtk.ComboBoxText()
        for value in ("7", "30", "90"):
            self.analytics_days.append(value, f"Last {value} days")
        self.analytics_days.set_active_id("30")
        self.analytics_app_filter = Gtk.ComboBoxText()
        self.analytics_app_filter.append("all", "All apps")
        self.analytics_app_filter.set_active_id("all")
        self.analytics_platform_filter = Gtk.ComboBoxText()
        self.analytics_platform_filter.append("all", "All platforms")
        self.analytics_platform_filter.set_active_id("all")
        for combo in (self.analytics_days, self.analytics_app_filter, self.analytics_platform_filter):
            combo.connect("changed", lambda _c: self._render_analytics_from_filters())
            filters.pack_start(combo, False, False, 0)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", lambda _b: self.open_dashboard_analytics())
        filters.pack_start(refresh, False, False, 0)
        analytics.pack_start(filters, False, False, 0)
        self.analytics_summary = Gtk.Label(label="Analytics not loaded.", xalign=0, wrap=True)
        self.analytics_summary.get_style_context().add_class("dashboard-stats")
        analytics.pack_start(self.analytics_summary, False, False, 0)
        self.analytics_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        analytics.pack_start(self.analytics_box, False, False, 0)
        self.analytics_data = None

        # Developer profile
        self.profile_page, profile = self._make_dashboard_aux_page(
            "Developer profile",
            "Public developer information shown on your Luma Store developer page.",
        )
        self.profile_status = Gtk.Label(xalign=0, wrap=True)
        profile.pack_start(self.profile_status, False, False, 0)
        self.profile_fields = {}
        profile_grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        profile_grid.get_style_context().add_class("glass-card")
        profile_grid.set_border_width(14)
        for row, (key, title) in enumerate((
            ("display_name", "Display name"),
            ("avatar_url", "Avatar URL"),
            ("website_url", "Website"),
            ("github_url", "GitHub"),
            ("gitlab_url", "GitLab"),
        )):
            label = Gtk.Label(label=title, xalign=0)
            entry = Gtk.Entry()
            entry.set_hexpand(True)
            profile_grid.attach(label, 0, row, 1, 1)
            profile_grid.attach(entry, 1, row, 1, 1)
            self.profile_fields[key] = entry
        bio_label = Gtk.Label(label="Bio", xalign=0)
        bio_label.set_valign(Gtk.Align.START)
        self.profile_bio = Gtk.TextView()
        self.profile_bio.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        bio_scroller = Gtk.ScrolledWindow()
        bio_scroller.set_min_content_height(120)
        bio_scroller.add(self.profile_bio)
        profile_grid.attach(bio_label, 0, 5, 1, 1)
        profile_grid.attach(bio_scroller, 1, 5, 1, 1)
        profile.pack_start(profile_grid, False, False, 0)
        save_profile = Gtk.Button(label="Save profile")
        save_profile.get_style_context().add_class("glass-primary")
        save_profile.set_halign(Gtk.Align.END)
        save_profile.connect("clicked", self.save_dashboard_profile)
        profile.pack_start(save_profile, False, False, 0)

        # Funding
        self.funding_page, funding = self._make_dashboard_aux_page(
            "Developer funding",
            "Configure donation methods once; they apply to all of your published apps.",
        )
        self.funding_status = Gtk.Label(xalign=0, wrap=True)
        funding.pack_start(self.funding_status, False, False, 0)
        self.funding_fields = {}
        funding_grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        funding_grid.get_style_context().add_class("glass-card")
        funding_grid.set_border_width(14)
        for row, (key, title) in enumerate((
            ("donate_url", "Donation URL"),
            ("liberapay", "Liberapay URL"),
            ("opencollective", "OpenCollective URL"),
        )):
            label = Gtk.Label(label=title, xalign=0)
            entry = Gtk.Entry()
            entry.set_hexpand(True)
            funding_grid.attach(label, 0, row, 1, 1)
            funding_grid.attach(entry, 1, row, 1, 1)
            self.funding_fields[key] = entry
        funding.pack_start(funding_grid, False, False, 0)

        crypto_title = Gtk.Label(label="Cryptocurrency wallet addresses", xalign=0)
        crypto_title.get_style_context().add_class("section-title")
        funding.pack_start(crypto_title, False, False, 0)
        self.crypto_fields = {}
        for currency, label_text, networks in CRYPTO_OPTIONS:
            frame = Gtk.Frame(label=label_text)
            grid = Gtk.Grid(column_spacing=10, row_spacing=8)
            grid.set_border_width(10)
            frame.add(grid)
            for row, network in enumerate(networks):
                key = f"{currency}::{network}"
                label = Gtk.Label(label=network, xalign=0)
                entry = Gtk.Entry()
                entry.set_hexpand(True)
                grid.attach(label, 0, row, 1, 1)
                grid.attach(entry, 1, row, 1, 1)
                self.crypto_fields[key] = entry
            funding.pack_start(frame, False, False, 0)
        save_funding = Gtk.Button(label="Save developer funding")
        save_funding.get_style_context().add_class("glass-primary")
        save_funding.set_halign(Gtk.Align.END)
        save_funding.connect("clicked", self.save_dashboard_funding)
        funding.pack_start(save_funding, False, False, 0)

        # Status / timeline
        self.status_page, status = self._make_dashboard_aux_page(
            "Submission status",
            "Follow scans, review messages, changelogs and publishing decisions for your apps.",
        )
        self.status_message = Gtk.Label(xalign=0, wrap=True)
        status.pack_start(self.status_message, False, False, 0)
        self.status_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        status.pack_start(self.status_list, False, False, 0)

        # Notifications
        self.notifications_page, notifications = self._make_dashboard_aux_page(
            "Developer notifications",
            "Status, review and feedback notifications for your submissions.",
        )
        self.notifications_message = Gtk.Label(xalign=0, wrap=True)
        notifications.pack_start(self.notifications_message, False, False, 0)
        self.notifications_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        notifications.pack_start(self.notifications_list, False, False, 0)

        # Detailed app view
        self.submission_details_page = self.page_box()
        app_back = Gtk.Button(label="← Developer Dashboard")
        app_back.set_halign(Gtk.Align.START)
        app_back.connect("clicked", lambda _b: self.open_dashboard())
        self.submission_details_page.pack_start(app_back, False, False, 0)
        self.submission_details_title = self.heading("App details")
        self.submission_details_page.pack_start(self.submission_details_title, False, False, 0)
        self.submission_details_status = Gtk.Label(xalign=0, wrap=True)
        self.submission_details_page.pack_start(self.submission_details_status, False, False, 0)
        self.submission_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.submission_edit_button = Gtk.Button(label="Edit app metadata")
        self.submission_edit_button.get_style_context().add_class("glass-primary")
        self.submission_edit_button.connect("clicked", self.edit_current_submission_metadata)
        self.submission_remove_button = Gtk.Button(label="Delete / archive")
        self.submission_remove_button.connect("clicked", self.remove_current_submission)
        self.submission_actions.pack_start(self.submission_edit_button, False, False, 0)
        self.submission_actions.pack_start(self.submission_remove_button, False, False, 0)
        self.submission_details_page.pack_start(self.submission_actions, False, False, 0)

        self.submission_notebook = Gtk.Notebook()
        self.submission_notebook.set_scrollable(True)
        self.submission_details_page.pack_start(self.submission_notebook, True, True, 0)

        def detail_tab(title):
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.set_border_width(14)
            scrolled.add(box)
            self.submission_notebook.append_page(scrolled, Gtk.Label(label=title))
            return box

        self.submission_overview_box = detail_tab("Overview")
        self.submission_timeline_box = detail_tab("Timeline")
        self.submission_security_box = detail_tab("Security")
        self.submission_versions_box = detail_tab("Versions")
        self.submission_comments_box = detail_tab("Review comments")
        self.submission_comment_entry = Gtk.Entry()
        self.submission_comment_entry.set_placeholder_text("Add a review comment…")
        self.submission_comment_button = Gtk.Button(label="Send comment")
        self.submission_comment_button.connect("clicked", self.add_current_review_comment)
        comment_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        comment_row.pack_start(self.submission_comment_entry, True, True, 0)
        comment_row.pack_start(self.submission_comment_button, False, False, 0)
        self.submission_comments_box.pack_end(comment_row, False, False, 0)
        self.current_submission_details = None

    def open_dashboard_analytics(self):
        self.show_page("dashboard_analytics")
        if not self.auth.access_token():
            self.analytics_summary.set_text("Sign in to view developer analytics.")
            return
        self.analytics_summary.set_text("Loading analytics…")
        threading.Thread(target=self._analytics_worker, daemon=True).start()

    def _analytics_worker(self):
        try:
            data = self.dashboard_api.analytics()
            GLib.idle_add(self._analytics_loaded, data)
        except Exception as error:
            GLib.idle_add(self.analytics_summary.set_text, f"Analytics unavailable: {error}")

    def _analytics_loaded(self, data):
        self.analytics_data = data if isinstance(data, dict) else {}
        current_app = self.analytics_app_filter.get_active_id() or "all"
        current_platform = self.analytics_platform_filter.get_active_id() or "all"
        self.analytics_app_filter.remove_all()
        self.analytics_app_filter.append("all", "All apps")
        for app in self.analytics_data.get("apps", []):
            app_id = str(app.get("id") or "")
            if app_id:
                self.analytics_app_filter.append(app_id, app.get("name") or app.get("package_name") or "App")
        self.analytics_app_filter.set_active_id(current_app if current_app else "all")

        platforms = sorted({
            str(row.get("platform"))
            for row in (
                list(self.analytics_data.get("platforms", []))
                + list(self.analytics_data.get("daily", []))
            )
            if row.get("platform")
        })
        self.analytics_platform_filter.remove_all()
        self.analytics_platform_filter.append("all", "All platforms")
        for platform in platforms:
            self.analytics_platform_filter.append(platform, platform)
        self.analytics_platform_filter.set_active_id(current_platform if current_platform in platforms else "all")
        self._render_analytics_from_filters()
        return False

    @staticmethod
    def _metric_card(title, value, detail=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.set_border_width(12)
        box.get_style_context().add_class("glass-card")
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.get_style_context().add_class("muted")
        value_label = Gtk.Label(label=str(value), xalign=0)
        value_label.get_style_context().add_class("section-title")
        box.pack_start(title_label, False, False, 0)
        box.pack_start(value_label, False, False, 0)
        if detail:
            detail_label = Gtk.Label(label=str(detail), xalign=0, wrap=True)
            detail_label.get_style_context().add_class("muted")
            box.pack_start(detail_label, False, False, 0)
        return box

    def _render_analytics_from_filters(self):
        data = self.analytics_data
        if not data:
            return
        self.clear(self.analytics_box)
        try:
            days = int(self.analytics_days.get_active_id() or "30")
        except ValueError:
            days = 30
        app_filter = self.analytics_app_filter.get_active_id() or "all"
        platform_filter = self.analytics_platform_filter.get_active_id() or "all"
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days - 1)

        daily_map = {}
        for row in data.get("daily", []):
            if app_filter != "all" and str(row.get("app_id")) != app_filter:
                continue
            if platform_filter != "all" and str(row.get("platform")) != platform_filter:
                continue
            day = str(row.get("download_day") or "")[:10]
            try:
                day_date = datetime.fromisoformat(day).date()
            except Exception:
                continue
            if day_date < cutoff:
                continue
            daily_map[day] = daily_map.get(day, 0) + int(row.get("downloads") or 0)

        period_total = sum(daily_map.values())
        total = int(data.get("total_downloads") or 0)
        top = (data.get("apps") or [None])[0]
        top_text = "—"
        if top:
            top_text = f"{top.get('name') or top.get('package_name') or 'App'} · {int(top.get('downloads') or 0):,}"
        self.analytics_summary.set_text(
            f"All-time downloads: {total:,}  •  Last {days} days: {period_total:,}  •  Top app: {top_text}"
        )

        daily_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        daily_card.set_border_width(12)
        daily_card.get_style_context().add_class("glass-card")
        daily_title = Gtk.Label(label=f"Downloads · last {days} days", xalign=0)
        daily_title.get_style_context().add_class("section-title")
        daily_card.pack_start(daily_title, False, False, 0)
        max_daily = max([1] + list(daily_map.values()))
        for offset in range(days):
            day = cutoff + timedelta(days=offset)
            key = day.isoformat()
            value = daily_map.get(key, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            label = Gtk.Label(label=key, xalign=0)
            label.set_size_request(95, -1)
            bar = Gtk.ProgressBar()
            bar.set_hexpand(True)
            bar.set_fraction(value / max_daily if max_daily else 0)
            bar.set_text(f"{value:,}")
            bar.set_show_text(True)
            row.pack_start(label, False, False, 0)
            row.pack_start(bar, True, True, 0)
            daily_card.pack_start(row, False, False, 0)
        self.analytics_box.pack_start(daily_card, False, False, 0)

        app_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        app_card.set_border_width(12)
        app_card.get_style_context().add_class("glass-card")
        app_card.pack_start(Gtk.Label(label="Downloads by app", xalign=0), False, False, 0)
        for app in data.get("apps", []):
            row = Gtk.Label(
                label=f"{app.get('name') or app.get('package_name') or 'App'}  —  {int(app.get('downloads') or 0):,}",
                xalign=0,
            )
            app_card.pack_start(row, False, False, 0)
        self.analytics_box.pack_start(app_card, False, False, 0)

        platform_rows = data.get("app_platforms", [])
        if app_filter != "all":
            platform_rows = [row for row in platform_rows if str(row.get("app_id")) == app_filter]
        platform_totals = {}
        for row in platform_rows:
            platform = str(row.get("platform") or "Unknown")
            platform_totals[platform] = platform_totals.get(platform, 0) + int(row.get("downloads") or 0)
        platform_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        platform_card.set_border_width(12)
        platform_card.get_style_context().add_class("glass-card")
        platform_card.pack_start(Gtk.Label(label="Downloads by platform", xalign=0), False, False, 0)
        for platform, value in sorted(platform_totals.items()):
            platform_card.pack_start(Gtk.Label(label=f"{platform}  —  {value:,}", xalign=0), False, False, 0)
        self.analytics_box.pack_start(platform_card, False, False, 0)

        funding = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        funding.set_border_width(12)
        funding.get_style_context().add_class("glass-card")
        funding.pack_start(Gtk.Label(label="Funding link clicks", xalign=0), False, False, 0)
        if data.get("funding"):
            for row in data.get("funding", []):
                funding.pack_start(
                    Gtk.Label(label=f"{row.get('provider')}: {int(row.get('clicks') or 0):,}", xalign=0),
                    False, False, 0,
                )
        else:
            empty = Gtk.Label(label="No funding link clicks yet.", xalign=0)
            empty.get_style_context().add_class("muted")
            funding.pack_start(empty, False, False, 0)
        self.analytics_box.pack_start(funding, False, False, 0)
        self.analytics_box.show_all()

    def open_dashboard_profile(self):
        self.show_page("dashboard_profile")
        self.profile_status.set_text("Loading developer profile…")
        threading.Thread(target=self._profile_worker, daemon=True).start()

    def _profile_worker(self):
        try:
            profile = self.dashboard_api.profile()
            GLib.idle_add(self._profile_loaded, profile)
        except Exception as error:
            GLib.idle_add(self.profile_status.set_text, f"Could not load profile: {error}")

    def _profile_loaded(self, profile):
        for key, entry in self.profile_fields.items():
            entry.set_text(str(profile.get(key) or ""))
        self.profile_bio.get_buffer().set_text(str(profile.get("bio") or ""))
        self.profile_status.set_text("Verified by Luma Store." if profile.get("verified") else "")
        return False

    def save_dashboard_profile(self, _button):
        profile = {key: entry.get_text().strip() for key, entry in self.profile_fields.items()}
        profile["bio"] = self._text_view_value(self.profile_bio)
        self.profile_status.set_text("Saving profile…")
        threading.Thread(target=self._save_profile_worker, args=(profile,), daemon=True).start()

    def _save_profile_worker(self, profile):
        try:
            self.dashboard_api.save_profile(profile)
            GLib.idle_add(self.profile_status.set_text, "Developer profile saved.")
        except Exception as error:
            GLib.idle_add(self.profile_status.set_text, f"Could not save profile: {error}")

    def open_dashboard_funding(self):
        self.show_page("dashboard_funding")
        self.funding_status.set_text("Loading developer funding…")
        threading.Thread(target=self._funding_worker, daemon=True).start()

    def _funding_worker(self):
        try:
            funding = self.dashboard_api.funding()
            GLib.idle_add(self._funding_loaded, funding)
        except Exception as error:
            GLib.idle_add(self.funding_status.set_text, f"Could not load funding: {error}")

    def _funding_loaded(self, funding):
        for key, entry in self.funding_fields.items():
            entry.set_text(str(funding.get(key) or ""))
        crypto = dict(funding.get("crypto_addresses") or {})
        if funding.get("bitcoin") and "bitcoin::Bitcoin" not in crypto:
            crypto["bitcoin::Bitcoin"] = funding["bitcoin"]
        if funding.get("litecoin") and "litecoin::Litecoin" not in crypto:
            crypto["litecoin::Litecoin"] = funding["litecoin"]
        for key, entry in self.crypto_fields.items():
            entry.set_text(str(crypto.get(key) or ""))
        self.funding_status.set_text("")
        return False

    def save_dashboard_funding(self, _button):
        payload = {key: entry.get_text().strip() for key, entry in self.funding_fields.items()}
        payload["crypto_addresses"] = {
            key: entry.get_text().strip()
            for key, entry in self.crypto_fields.items()
            if entry.get_text().strip()
        }
        self.funding_status.set_text("Saving developer funding…")
        threading.Thread(target=self._save_funding_worker, args=(payload,), daemon=True).start()

    def _save_funding_worker(self, payload):
        try:
            self.dashboard_api.save_funding(payload)
            GLib.idle_add(
                self.funding_status.set_text,
                "Developer funding saved. These methods now apply to all your apps.",
            )
        except Exception as error:
            GLib.idle_add(self.funding_status.set_text, f"Could not save funding: {error}")

    def open_dashboard_status(self):
        self.show_page("dashboard_status")
        self.status_message.set_text("Loading submission history…")
        threading.Thread(target=self._status_worker, daemon=True).start()

    def _status_worker(self):
        try:
            data = self.dashboard_api.status_data()
            GLib.idle_add(self._status_loaded, data)
        except Exception as error:
            GLib.idle_add(self.status_message.set_text, f"Could not load submission status: {error}")

    def _status_loaded(self, data):
        self.clear(self.status_list)
        submissions = data.get("submissions", [])
        history = data.get("history", [])
        self.status_message.set_text(
            f"{len(submissions)} submission(s)" if submissions else "You have not submitted an app yet."
        )
        for submission in submissions:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.set_border_width(12)
            card.get_style_context().add_class("glass-card")
            title = Gtk.Label(
                label=f"{submission.get('name') or 'App'}  ·  {submission.get('status') or 'Unknown'}",
                xalign=0,
            )
            title.get_style_context().add_class("section-title")
            card.pack_start(title, False, False, 0)
            if submission.get("description"):
                desc = Gtk.Label(label=str(submission["description"]), xalign=0, wrap=True)
                desc.get_style_context().add_class("muted")
                card.pack_start(desc, False, False, 0)
            if submission.get("review_message"):
                review = Gtk.Label(label=f"Latest status message: {submission['review_message']}", xalign=0, wrap=True)
                card.pack_start(review, False, False, 0)
            if submission.get("changelog"):
                changelog = Gtk.Label(label=f"Changelog: {submission['changelog']}", xalign=0, wrap=True)
                changelog.get_style_context().add_class("muted")
                card.pack_start(changelog, False, False, 0)
            events = [row for row in history if row.get("submission_id") == submission.get("id")]
            for event in events:
                event_label = Gtk.Label(
                    label=f"• {event.get('status')} · {event.get('created_at')}"
                          + (f" — {event.get('review_message')}" if event.get("review_message") else ""),
                    xalign=0,
                    wrap=True,
                )
                event_label.get_style_context().add_class("muted")
                card.pack_start(event_label, False, False, 0)
            button = Gtk.Button(label="Open app details")
            button.set_halign(Gtk.Align.START)
            button.connect("clicked", self.show_submission_details, submission)
            card.pack_start(button, False, False, 0)
            self.status_list.pack_start(card, False, False, 0)
        self.status_list.show_all()
        return False

    def open_dashboard_notifications(self):
        self.show_page("dashboard_notifications")
        self.notifications_message.set_text("Loading notifications…")
        threading.Thread(target=self._notifications_worker, daemon=True).start()

    def _notifications_worker(self):
        try:
            rows = self.dashboard_api.notifications()
            GLib.idle_add(self._notifications_loaded, rows)
        except Exception as error:
            GLib.idle_add(self.notifications_message.set_text, f"Could not load notifications: {error}")

    def _notifications_loaded(self, rows):
        self.clear(self.notifications_list)
        unread = sum(1 for row in rows if not row.get("read_at"))
        self.notifications_message.set_text(f"{len(rows)} notification(s) · {unread} unread")
        for notification in rows:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            card.set_border_width(10)
            card.get_style_context().add_class("glass-card")
            title = notification.get("title") or notification.get("type") or "Notification"
            card.pack_start(Gtk.Label(label=title, xalign=0, wrap=True), False, False, 0)
            if notification.get("message"):
                message = Gtk.Label(label=str(notification["message"]), xalign=0, wrap=True)
                message.get_style_context().add_class("muted")
                card.pack_start(message, False, False, 0)
            meta = Gtk.Label(label=str(notification.get("created_at") or ""), xalign=0)
            meta.get_style_context().add_class("muted")
            card.pack_start(meta, False, False, 0)
            if not notification.get("read_at"):
                read = Gtk.Button(label="Mark as read")
                read.set_halign(Gtk.Align.START)
                read.connect("clicked", self.mark_notification_read, notification.get("id"))
                card.pack_start(read, False, False, 0)
            if notification.get("submission_id"):
                open_button = Gtk.Button(label="Open app")
                open_button.set_halign(Gtk.Align.START)
                open_button.connect(
                    "clicked",
                    lambda _b, submission_id=notification.get("submission_id"): self.open_submission_by_id(submission_id),
                )
                card.pack_start(open_button, False, False, 0)
            self.notifications_list.pack_start(card, False, False, 0)
        self.notifications_list.show_all()
        return False

    def mark_notification_read(self, _button, notification_id):
        if not notification_id:
            return
        threading.Thread(
            target=self._mark_notification_worker,
            args=(notification_id,),
            daemon=True,
        ).start()

    def _mark_notification_worker(self, notification_id):
        try:
            self.dashboard_api.mark_notification_read(notification_id)
        finally:
            GLib.idle_add(self.open_dashboard_notifications)

    def open_submission_by_id(self, submission_id):
        if not submission_id:
            return
        self.show_page("dashboard_app")
        self.submission_details_title.set_text("Loading app details…")
        self.submission_details_status.set_text("")
        threading.Thread(
            target=self._submission_details_worker,
            args=(submission_id,),
            daemon=True,
        ).start()

    def _submission_details_worker(self, submission_id):
        try:
            data = self.dashboard_api.submission_details(submission_id)
            GLib.idle_add(self._submission_details_loaded, data)
        except Exception as error:
            GLib.idle_add(self._submission_details_failed, str(error))

    def _submission_details_failed(self, message):
        self.submission_details_title.set_text("App details")
        self.submission_details_status.set_text(f"Could not load app details: {message}")
        return False

    @staticmethod
    def _json_text(value):
        if value in (None, [], {}, ""):
            return "—"
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, ensure_ascii=False)
        return str(value)

    def _submission_details_loaded(self, data):
        self.current_submission_details = data
        submission = data.get("submission") or {}
        self.submission_details_title.set_text(submission.get("name") or "App details")
        self.submission_details_status.set_text(
            f"{submission.get('status') or 'Unknown'}"
            + (f"  •  {submission.get('category')}" if submission.get("category") else "")
            + (f"  •  Version {submission.get('version')}" if submission.get("version") else "")
        )

        for box in (
            self.submission_overview_box,
            self.submission_timeline_box,
            self.submission_security_box,
            self.submission_versions_box,
        ):
            self.clear(box)

        def add_field(box, title, value):
            if value in (None, "", [], {}):
                return
            label = Gtk.Label(xalign=0, wrap=True, selectable=True)
            label.set_markup(f"<b>{GLib.markup_escape_text(str(title))}:</b> {GLib.markup_escape_text(self._json_text(value))}")
            box.pack_start(label, False, False, 0)

        for title, key in (
            ("Status", "status"),
            ("Short description", "short_description"),
            ("Description", "description"),
            ("Categories", "categories"),
            ("License", "license_type"),
            ("Version", "version"),
            ("versionCode", "version_code"),
            ("Package name", "package_name"),
            ("Repository", "repo_url"),
            ("Changelog", "changelog"),
            ("Submitted", "submitted_at"),
            ("Updated", "status_updated_at"),
            ("Review message", "review_message"),
        ):
            add_field(self.submission_overview_box, title, submission.get(key))

        stats = data.get("stats")
        if stats:
            add_field(
                self.submission_overview_box,
                "Downloads",
                f"Total {stats.get('total', 0)} · Today {stats.get('today', 0)} · Month {stats.get('this_month', 0)} · Year {stats.get('this_year', 0)}",
            )
        for platform in data.get("published_platforms", []):
            add_field(
                self.submission_overview_box,
                f"Published {platform.get('platform')} {platform.get('package_type') or ''}".strip(),
                {
                    "download_url": platform.get("download_url"),
                    "file_size_mb": platform.get("file_size_mb"),
                    "sha256": platform.get("sha256"),
                    "artifact_verified_at": platform.get("artifact_verified_at"),
                },
            )
        for artifact in submission.get("platforms") or []:
            add_field(
                self.submission_overview_box,
                f"Submission platform {artifact.get('platform', '')} {artifact.get('packageType') or artifact.get('package_type') or ''}".strip(),
                artifact,
            )

        history = data.get("history", [])
        if history:
            for event in history:
                event_label = Gtk.Label(
                    label=f"{event.get('status')} · {event.get('created_at')}"
                          + (f"\n{event.get('review_message')}" if event.get("review_message") else ""),
                    xalign=0,
                    wrap=True,
                )
                event_label.set_border_width(8)
                event_label.get_style_context().add_class("glass-card")
                self.submission_timeline_box.pack_start(event_label, False, False, 0)
        else:
            self.submission_timeline_box.pack_start(
                Gtk.Label(label="No timeline entries are available yet.", xalign=0),
                False, False, 0,
            )

        scan = data.get("scan")
        if scan and scan.get("status") in ("Queued", "Scanning"):
            GLib.timeout_add_seconds(
                12,
                self._refresh_active_security_scan,
                submission.get("id"),
            )
        if scan:
            for title, key in (
                ("Status", "status"),
                ("Risk level", "risk_level"),
                ("Provider", "provider"),
                ("Scanned", "scanned_at"),
                ("File", "file_name"),
                ("File size", "file_size_bytes"),
                ("Malicious detections", "malicious_count"),
                ("Suspicious detections", "suspicious_count"),
                ("Harmless", "harmless_count"),
                ("Undetected", "undetected_count"),
                ("Findings", "findings"),
                ("Permissions", "permissions"),
                ("VirusTotal", "virus_total_permalink"),
                ("Error", "error_message"),
            ):
                add_field(self.submission_security_box, title, scan.get(key))
            if scan.get("virus_total_permalink"):
                vt_button = Gtk.Button(label="Open VirusTotal report")
                vt_button.set_halign(Gtk.Align.START)
                vt_button.connect(
                    "clicked",
                    lambda _b, url=str(scan.get("virus_total_permalink")): self.open_external_url(url),
                )
                self.submission_security_box.pack_start(vt_button, False, False, 0)
        else:
            self.submission_security_box.pack_start(
                Gtk.Label(label="No security scan is available yet.", xalign=0),
                False, False, 0,
            )

        published = data.get("published") or {}
        if published:
            package_name = published.get("package_name") or submission.get("package_name")
            developer_name = published.get("developer_name")
            if package_name or developer_name:
                badge = Gtk.Button(label="Copy README download badge")
                badge.set_halign(Gtk.Align.START)
                badge.connect(
                    "clicked",
                    lambda _b, package=package_name, developer=developer_name: self.copy_download_badge(package, developer),
                )
                self.submission_overview_box.pack_start(badge, False, False, 0)

        versions = data.get("versions", [])
        if versions:
            for version in versions:
                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                card.set_border_width(10)
                card.get_style_context().add_class("glass-card")
                card.pack_start(
                    Gtk.Label(
                        label=f"{version.get('version') or 'Unknown version'}"
                              + (f" ({version.get('version_code')})" if version.get("version_code") else "")
                              + f" · {version.get('status') or ''}",
                        xalign=0,
                    ),
                    False, False, 0,
                )
                if version.get("changelog"):
                    change = Gtk.Label(label=str(version["changelog"]), xalign=0, wrap=True)
                    change.get_style_context().add_class("muted")
                    card.pack_start(change, False, False, 0)
                if version.get("download_url"):
                    url = Gtk.Label(label=str(version["download_url"]), xalign=0, selectable=True, wrap=True)
                    card.pack_start(url, False, False, 0)
                self.submission_versions_box.pack_start(card, False, False, 0)
        else:
            self.submission_versions_box.pack_start(
                Gtk.Label(label="No version history is available for this submission.", xalign=0),
                False, False, 0,
            )

        # Comments: preserve the input row at the bottom.
        children = self.submission_comments_box.get_children()
        input_row = children[-1] if children else None
        for child in list(children):
            if child is not input_row:
                self.submission_comments_box.remove(child)
        for comment in data.get("comments", []):
            label = Gtk.Label(
                label=f"{comment.get('created_at')}\n{comment.get('body')}",
                xalign=0,
                wrap=True,
            )
            label.set_border_width(8)
            label.get_style_context().add_class("glass-card")
            self.submission_comments_box.pack_start(label, False, False, 0)
        if input_row:
            self.submission_comments_box.reorder_child(input_row, -1)

        self.submission_overview_box.show_all()
        self.submission_timeline_box.show_all()
        self.submission_security_box.show_all()
        self.submission_versions_box.show_all()
        self.submission_comments_box.show_all()
        return False

    def edit_current_submission_metadata(self, _button):
        data = self.current_submission_details or {}
        submission = data.get("submission")
        if submission:
            self.edit_submission_in_form(submission)

    def add_current_review_comment(self, _button):
        data = self.current_submission_details or {}
        submission = data.get("submission") or {}
        submission_id = submission.get("id")
        body = self.submission_comment_entry.get_text().strip()
        if not submission_id or not body:
            return
        self.submission_comment_button.set_sensitive(False)
        threading.Thread(
            target=self._add_review_comment_worker,
            args=(submission_id, body),
            daemon=True,
        ).start()

    def _add_review_comment_worker(self, submission_id, body):
        try:
            self.dashboard_api.add_review_comment(submission_id, body)
            GLib.idle_add(self.submission_comment_entry.set_text, "")
            GLib.idle_add(self.submission_comment_button.set_sensitive, True)
            GLib.idle_add(self.open_submission_by_id, submission_id)
        except Exception as error:
            GLib.idle_add(self.submission_comment_button.set_sensitive, True)
            GLib.idle_add(self.submission_details_status.set_text, f"Could not add comment: {error}")

    def remove_current_submission(self, _button):
        data = self.current_submission_details or {}
        submission = data.get("submission") or {}
        self.confirm_remove_submission(submission)

    @staticmethod
    def open_external_url(url):
        try:
            Gio.AppInfo.launch_default_for_uri(str(url), None)
        except Exception:
            webbrowser.open(str(url))
        return False

    def copy_download_badge(self, package_name=None, developer_name=None):
        if package_name:
            query = "package_name=" + urllib.parse.quote(str(package_name), safe="")
            target = "https://luma.free-time.me/discover/" + urllib.parse.quote(str(package_name), safe="")
            alt = "Luma Store downloads"
        elif developer_name:
            query = "developer_name=" + urllib.parse.quote(str(developer_name), safe="") + "&badge_v=3"
            target = "https://luma.free-time.me/discover/developers/" + urllib.parse.quote(str(developer_name), safe="")
            alt = "Luma Store total downloads"
        else:
            return False
        badge_url = f"{SUPABASE_URL}/functions/v1/download-badge?{query}"
        markdown = f"[![{alt}]({badge_url})]({target})"
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(markdown, -1)
        clipboard.store()
        self.submission_details_status.set_text(
            self.submission_details_status.get_text() + "  •  Badge Markdown copied"
        )
        return False

    def _refresh_active_security_scan(self, submission_id):
        if (
            not submission_id
            or self.stack.get_visible_child_name() != "dashboard_app"
            or not self.current_submission_details
            or (self.current_submission_details.get("submission") or {}).get("id") != submission_id
        ):
            return False
        self.open_submission_by_id(submission_id)
        return False

    @staticmethod
    def page_box():
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_border_width(24)
        box.get_style_context().add_class("page-surface")
        return box

    @staticmethod
    def heading(text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("page-title")
        return label

    def show_page(self, name):
        self.stack.set_visible_child_name(name)

    def open_dashboard(self):
        self.show_page("dashboard")
        self.refresh_dashboard_state()
        if self.auth.access_token():
            self.load_dashboard_submissions()
            if not self.submission_options_loaded:
                threading.Thread(target=self._submission_options_worker, daemon=True).start()

    def _submission_options_worker(self):
        try:
            categories = self.dashboard_api.categories()
            licenses = self.dashboard_api.licenses()
            GLib.idle_add(self._submission_options_loaded, categories, licenses)
        except Exception:
            # These are conveniences only; free-form input stays available.
            pass

    def _submission_options_loaded(self, categories, licenses):
        def completion_for(values):
            model = Gtk.ListStore(str)
            seen = set()
            for value in values:
                value = str(value or "").strip()
                if value and value not in seen:
                    model.append([value])
                    seen.add(value)
            completion = Gtk.EntryCompletion()
            completion.set_model(model)
            completion.set_text_column(0)
            completion.set_inline_completion(True)
            completion.set_popup_completion(True)
            return completion

        self.submit_fields["categories"].set_completion(completion_for(categories))
        self.submit_fields["license_type"].set_completion(
            completion_for([
                row.get("name") or row.get("display_name")
                for row in licenses
                if isinstance(row, dict)
            ])
        )
        self.submission_options_loaded = True
        return False

    def refresh_dashboard_state(self):
        token = self.auth.access_token()
        if not token:
            self.dashboard_auth_status.set_text(
                "Sign in with GitHub or GitLab. Authentication opens in your system browser; the dashboard itself stays native."
            )
            self.dashboard_login_buttons.show()
            self.dashboard_session_actions.hide()
            self.dashboard_stats.set_text("Sign in to load your submissions.")
            self.submit_button.set_sensitive(False)
            self.submit_draft_button.set_sensitive(False)
            self.clear(self.dashboard_list)
            self.dashboard_list.show_all()
            return

        try:
            user = self.auth.user() or {}
            metadata = user.get("user_metadata") or {}
            display_name = (
                metadata.get("user_name")
                or metadata.get("preferred_username")
                or metadata.get("full_name")
                or user.get("email")
                or "Developer"
            )
            provider = self.auth.provider()
            self.dashboard_auth_status.set_text(f"Signed in as {display_name} via {provider.title()}.")
            self.dashboard_login_buttons.hide()
            self.dashboard_session_actions.show()
            self.submit_button.set_sensitive(bool(self.auth.provider_token()))
            self.submit_draft_button.set_sensitive(True)
            if not self.auth.provider_token():
                self.submit_status.set_text("Viewing works with this session, but app submission requires GitHub login.")
            else:
                self.submit_status.set_text("")
        except Exception as error:
            self.dashboard_auth_status.set_text(f"Session error: {error}")
            self.dashboard_login_buttons.show()
            self.dashboard_session_actions.hide()
            self.submit_button.set_sensitive(False)
            self.submit_draft_button.set_sensitive(False)

    def start_dashboard_login(self, _button, provider):
        self.dashboard_auth_status.set_text(
            f"Opening {provider.title()} in your system browser… Complete the login there and return to Luma Store."
        )
        self.github_login_button.set_sensitive(False)
        self.gitlab_login_button.set_sensitive(False)
        threading.Thread(target=self._dashboard_login_worker, args=(provider,), daemon=True).start()

    def _dashboard_login_worker(self, provider):
        try:
            self.auth.login(provider)
            GLib.idle_add(self._dashboard_login_done)
        except Exception as error:
            GLib.idle_add(self._dashboard_login_failed, str(error))

    def _dashboard_login_done(self):
        self.github_login_button.set_sensitive(True)
        self.gitlab_login_button.set_sensitive(True)
        self.refresh_dashboard_state()
        self.load_dashboard_submissions()
        return False

    def _dashboard_login_failed(self, message):
        self.github_login_button.set_sensitive(True)
        self.gitlab_login_button.set_sensitive(True)
        self.dashboard_auth_status.set_text(f"Login failed: {message}")
        return False

    def dashboard_sign_out(self, _button):
        self.auth.sign_out()
        self.refresh_dashboard_state()

    @staticmethod
    def _text_view_value(view):
        buffer = view.get_buffer()
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True).strip()

    @staticmethod
    def _set_text_view(view, value):
        view.get_buffer().set_text(str(value or ""))

    def clear_submission_form(self):
        for entry in self.submit_fields.values():
            entry.set_text("")
        for view in self.submit_textviews.values():
            view.get_buffer().set_text("")
        for check in self.submit_platform_checks.values():
            check.set_active(False)
        self.submit_separate_repos.set_active(False)
        for fields in self.submit_platform_fields.values():
            for entry in fields.values():
                entry.set_text("")
        for views in self.submit_platform_textviews.values():
            for view in views.values():
                view.get_buffer().set_text("")
        for localization in list(self.submit_localizations):
            frame = localization.get("frame")
            if frame is not None and frame.get_parent() is self.submit_localizations_box:
                self.submit_localizations_box.remove(frame)
        self.submit_localizations = []
        self.submit_draft_id = None
        self.submit_editing_id = None
        self.submit_editing_status = None
        self.submit_existing_localized_metadata = []
        self.submit_status.set_text("")
        self.submit_button.set_label("Submit app")

    def add_localization_form(self, _button=None, metadata=None):
        metadata = metadata if isinstance(metadata, dict) else {}
        frame = Gtk.Frame(label=metadata.get("locale") or "Additional language")
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        grid.set_border_width(10)
        frame.add(grid)

        locale = Gtk.Entry()
        locale.set_placeholder_text("de-DE")
        locale.set_text(str(metadata.get("locale") or ""))
        title = Gtk.Entry()
        title.set_text(str(metadata.get("title") or ""))
        grid.attach(Gtk.Label(label="Locale", xalign=0), 0, 0, 1, 1)
        grid.attach(locale, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="Title", xalign=0), 0, 1, 1, 1)
        grid.attach(title, 1, 1, 1, 1)

        textviews = {}
        for offset, (key, label_text, height, source_keys) in enumerate((
            ("short_description", "Short description", 65, ("shortDescription", "short_description")),
            ("description", "Full description", 95, ("fullDescription", "full_description")),
            ("changelog", "Changelog", 75, ("changelog",)),
            ("screenshots", "Screenshot URLs", 75, ("screenshots",)),
        )):
            label = Gtk.Label(label=label_text, xalign=0)
            label.set_valign(Gtk.Align.START)
            view = Gtk.TextView()
            view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            value = None
            for source_key in source_keys:
                if source_key in metadata:
                    value = metadata.get(source_key)
                    break
            if key == "screenshots" and isinstance(value, list):
                value = "\n".join(str(item) for item in value if item)
            view.get_buffer().set_text(str(value or ""))
            scroller = Gtk.ScrolledWindow()
            scroller.set_min_content_height(height)
            scroller.add(view)
            grid.attach(label, 0, 2 + offset, 1, 1)
            grid.attach(scroller, 1, 2 + offset, 1, 1)
            textviews[key] = view

        record = {
            "frame": frame,
            "locale": locale,
            "title": title,
            "textviews": textviews,
        }
        remove = Gtk.Button(label="Remove language")
        remove.set_halign(Gtk.Align.START)
        remove.connect("clicked", lambda _b, item=record: self.remove_localization_form(item))
        grid.attach(remove, 1, 6, 1, 1)

        self.submit_localizations.append(record)
        self.submit_localizations_box.pack_start(frame, False, False, 0)
        frame.show_all()
        return record

    def remove_localization_form(self, record):
        if record in self.submit_localizations:
            self.submit_localizations.remove(record)
        frame = record.get("frame")
        if frame is not None and frame.get_parent() is self.submit_localizations_box:
            self.submit_localizations_box.remove(frame)

    def _selected_submit_platforms(self):
        return [
            platform
            for platform, check in self.submit_platform_checks.items()
            if check.get_active()
        ]

    @staticmethod
    def _submission_artifacts(value):
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, dict):
                continue
            platform = item.get("platform")
            if platform not in ("Android", "Windows", "Linux"):
                continue
            package_type = item.get("packageType") or item.get("package_type")
            download_url = item.get("downloadUrl") or item.get("download_url") or ""
            result.append({
                "platform": platform,
                "packageType": package_type,
                "downloadUrl": download_url,
                "repoUrl": item.get("repoUrl") or item.get("repo_url") or "",
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            })
        return result

    def edit_submission_in_form(self, submission):
        self.clear_submission_form()
        fields = self.submit_fields
        textviews = self.submit_textviews

        for key, source in (
            ("name", "name"),
            ("repo_url", "repo_url"),
            ("license_type", "license_type"),
            ("version", "version"),
            ("icon_url", "icon_url"),
            ("package_name", "package_name"),
            ("author_name", "author_name"),
            ("author_email", "author_email"),
            ("author_website", "author_website"),
            ("website_url", "website_url"),
            ("issue_tracker_url", "issue_tracker_url"),
            ("translation_url", "translation_url"),
            ("changelog_url", "changelog_url"),
        ):
            fields[key].set_text(str(submission.get(source) or ""))

        categories = submission.get("categories") or []
        if not categories and submission.get("category"):
            categories = [submission.get("category")]
        fields["categories"].set_text(", ".join(str(value) for value in categories if value))
        fields["version_code"].set_text(str(submission.get("version_code") or ""))

        self._set_text_view(textviews["short_description"], submission.get("short_description"))
        self._set_text_view(textviews["description"], submission.get("description"))
        self._set_text_view(textviews["changelog"], submission.get("changelog"))
        screenshots = submission.get("screenshots") or []
        self._set_text_view(
            textviews["screenshots"],
            "\n".join(str(value) for value in screenshots if value),
        )

        artifacts = self._submission_artifacts(submission.get("platforms"))
        selected = []
        for artifact in artifacts:
            platform = artifact["platform"]
            if platform not in selected:
                selected.append(platform)
            package_type = artifact.get("packageType")
            url = str(artifact.get("downloadUrl") or "")
            if platform == "Android" and package_type == "apk":
                fields["android_url"].set_text(url)
            elif platform == "Windows" and package_type == "exe":
                fields["windows_exe_url"].set_text(url)
            elif platform == "Windows" and package_type == "msi":
                fields["windows_msi_url"].set_text(url)
            elif platform == "Linux" and package_type == "deb":
                fields["deb_url"].set_text(url)
            elif platform == "Linux" and package_type == "rpm":
                fields["rpm_url"].set_text(url)

            platform_fields = self.submit_platform_fields[platform]
            platform_views = self.submit_platform_textviews[platform]
            platform_fields["repo_url"].set_text(str(artifact.get("repoUrl") or ""))
            metadata = artifact.get("metadata") or {}
            platform_fields["title"].set_text(str(metadata.get("title") or submission.get("name") or ""))
            self._set_text_view(platform_views["short_description"], metadata.get("shortDescription") or metadata.get("short_description"))
            self._set_text_view(platform_views["description"], metadata.get("fullDescription") or metadata.get("full_description"))
            self._set_text_view(platform_views["changelog"], metadata.get("changelog"))
            self._set_text_view(platform_views["screenshots"], "\n".join(metadata.get("screenshots") or []))

        if not selected and submission.get("platform") in self.submit_platform_checks:
            selected = [submission.get("platform")]
            legacy_url = str(submission.get("download_url") or "")
            if submission.get("platform") == "Android":
                fields["android_url"].set_text(legacy_url)
            elif submission.get("platform") == "Windows":
                fields["windows_exe_url"].set_text(legacy_url)
            elif submission.get("platform") == "Linux":
                if submission.get("linux_package_base") == "RPM-based":
                    fields["rpm_url"].set_text(legacy_url)
                else:
                    fields["deb_url"].set_text(legacy_url)

        for platform in selected:
            if platform in self.submit_platform_checks:
                self.submit_platform_checks[platform].set_active(True)

        separate = bool(submission.get("separate_platform_repos")) or any(
            artifact.get("repoUrl") or artifact.get("metadata")
            for artifact in artifacts
        )
        self.submit_separate_repos.set_active(separate)
        self.submit_existing_localized_metadata = list(submission.get("localized_metadata") or [])
        for metadata in self.submit_existing_localized_metadata:
            if not isinstance(metadata, dict):
                continue
            locale = str(metadata.get("locale") or "").lower()
            if locale and locale != "en-us" and not locale.startswith("en"):
                self.add_localization_form(metadata=metadata)
        self.submit_editing_id = submission.get("id")
        self.submit_editing_status = submission.get("status")
        self.submit_draft_id = submission.get("id") if submission.get("status") == "Draft" else None
        self.submit_button.set_label(
            "Submit update" if submission.get("status") == "Approved"
            else "Resubmit changes" if submission.get("status") == "Changes Requested"
            else "Submit app"
        )
        self.submit_expander.set_expanded(True)
        self.show_page("dashboard")
        self.submit_status.set_text(
            f"Editing {submission.get('name') or 'submission'} · current status {submission.get('status') or 'Unknown'}"
        )

    def _platform_metadata_for_submission(self, platform, final):
        fields = self.submit_platform_fields[platform]
        views = self.submit_platform_textviews[platform]
        screenshots = [
            value.strip()
            for value in self._text_view_value(views["screenshots"]).splitlines()
            if value.strip()
        ]
        values = {
            "repoUrl": fields["repo_url"].get_text().strip(),
            "title": fields["title"].get_text().strip(),
            "shortDescription": self._text_view_value(views["short_description"]),
            "fullDescription": self._text_view_value(views["description"]),
            "changelog": self._text_view_value(views["changelog"]),
            "screenshots": screenshots,
        }
        if final:
            missing = [
                label for label, value in (
                    ("repository URL", values["repoUrl"]),
                    ("title", values["title"]),
                    ("short description", values["shortDescription"]),
                    ("full description", values["fullDescription"]),
                    ("changelog", values["changelog"]),
                    ("screenshots", values["screenshots"]),
                )
                if not value
            ]
            if missing:
                raise RuntimeError(
                    f"{platform} platform metadata is incomplete: " + ", ".join(missing)
                )
            if not re.match(r"^https://github\.com/[^/]+/[^/]+/?$", values["repoUrl"]):
                raise RuntimeError(f"{platform} repository must be a public GitHub repository URL.")
        return {
            "repoUrl": values["repoUrl"],
            "metadata": {
                "title": values["title"],
                "shortDescription": values["shortDescription"],
                "fullDescription": values["fullDescription"],
                "changelog": values["changelog"],
                "screenshots": values["screenshots"],
            },
        }

    def _build_submission_payload(self, final=True):
        fields = {key: entry.get_text().strip() for key, entry in self.submit_fields.items()}
        texts = {key: self._text_view_value(view) for key, view in self.submit_textviews.items()}
        categories = [value.strip() for value in fields["categories"].split(",") if value.strip()]
        screenshots = [value.strip() for value in texts["screenshots"].splitlines() if value.strip()]
        platforms = self._selected_submit_platforms()
        separate_repos = self.submit_separate_repos.get_active()

        if final:
            required = {
                "Title": fields["name"],
                "Category": categories[0] if categories else "",
                "Open-source license": fields["license_type"],
                "Version": fields["version"],
                "Icon URL": fields["icon_url"],
                "Short description": texts["short_description"],
                "Full description": texts["description"],
                "Changelog": texts["changelog"],
                "Screenshot": screenshots[0] if screenshots else "",
                "Platform": platforms[0] if platforms else "",
            }
            missing = [label for label, value in required.items() if not value]
            if missing:
                raise RuntimeError("Missing required fields: " + ", ".join(missing))
            if not separate_repos:
                if not fields["repo_url"]:
                    raise RuntimeError("GitHub repository is required.")
                if not re.match(r"^https://github\.com/[^/]+/[^/]+/?$", fields["repo_url"]):
                    raise RuntimeError("Repository must be a public GitHub repository URL.")

        details = {}
        if separate_repos:
            for platform in platforms:
                details[platform] = self._platform_metadata_for_submission(platform, final)

        artifacts = []
        if "Android" in platforms and fields["android_url"]:
            artifacts.append({
                "platform": "Android",
                "packageType": "apk",
                "downloadUrl": fields["android_url"],
                **(details.get("Android") or {}),
            })
        if "Windows" in platforms and fields["windows_exe_url"]:
            artifacts.append({
                "platform": "Windows",
                "packageType": "exe",
                "downloadUrl": fields["windows_exe_url"],
                **(details.get("Windows") or {}),
            })
        if "Windows" in platforms and fields["windows_msi_url"]:
            artifacts.append({
                "platform": "Windows",
                "packageType": "msi",
                "downloadUrl": fields["windows_msi_url"],
                **(details.get("Windows") or {}),
            })
        if "Linux" in platforms and fields["deb_url"]:
            artifacts.append({
                "platform": "Linux",
                "packageType": "deb",
                "downloadUrl": fields["deb_url"],
                **(details.get("Linux") or {}),
            })
        if "Linux" in platforms and fields["rpm_url"]:
            artifacts.append({
                "platform": "Linux",
                "packageType": "rpm",
                "downloadUrl": fields["rpm_url"],
                **(details.get("Linux") or {}),
            })

        if final:
            if "Android" in platforms:
                if not fields["android_url"]:
                    raise RuntimeError("Android requires an APK download URL.")
                if not re.match(r"^([A-Za-z][A-Za-z0-9_]*\.)+[A-Za-z][A-Za-z0-9_]*$", fields["package_name"]):
                    raise RuntimeError("Android requires a valid package name.")
                if not fields["version_code"].isdigit() or int(fields["version_code"]) <= 0:
                    raise RuntimeError("Android requires a positive versionCode.")
            if "Windows" in platforms and not (fields["windows_exe_url"] or fields["windows_msi_url"]):
                raise RuntimeError("Windows requires an EXE or MSI download URL.")
            if "Linux" in platforms and not (fields["deb_url"] or fields["rpm_url"]):
                raise RuntimeError("Linux requires a DEB or RPM download URL.")
            if not artifacts:
                raise RuntimeError("At least one valid platform download is required.")

        primary_platform = platforms[0] if platforms else None
        primary_repo = (
            details.get(primary_platform, {}).get("repoUrl")
            if separate_repos and primary_platform
            else fields["repo_url"]
        )

        english = {
            "locale": "en-US",
            "title": fields["name"],
            "shortDescription": texts["short_description"],
            "fullDescription": texts["description"],
            "changelog": texts["changelog"],
            "screenshots": screenshots,
        }
        localized = [english]
        locale_keys = {"en-us"}
        for record in self.submit_localizations:
            locale = record["locale"].get_text().strip()
            title = record["title"].get_text().strip()
            views = record["textviews"]
            short_description = self._text_view_value(views["short_description"])
            full_description = self._text_view_value(views["description"])
            localized_changelog = self._text_view_value(views["changelog"])
            localized_screenshots = [
                value.strip()
                for value in self._text_view_value(views["screenshots"]).splitlines()
                if value.strip()
            ]
            has_any = any((
                locale, title, short_description, full_description,
                localized_changelog, localized_screenshots,
            ))
            if not has_any:
                continue
            if final and not all((
                locale, title, short_description, full_description,
                localized_changelog, localized_screenshots,
            )):
                raise RuntimeError(
                    "Every additional language requires locale, title, descriptions, changelog and at least one screenshot."
                )
            locale_key = locale.lower()
            if final and locale_key in locale_keys:
                raise RuntimeError(f"Locale {locale} is duplicated.")
            locale_keys.add(locale_key)
            localized.append({
                "locale": locale,
                "title": title,
                "shortDescription": short_description,
                "fullDescription": full_description,
                "changelog": localized_changelog,
                "screenshots": localized_screenshots,
            })

        version_code = int(fields["version_code"]) if fields["version_code"].isdigit() else None
        submission = {
            "name": fields["name"] or "Untitled draft",
            "short_description": texts["short_description"] or None,
            "description": texts["description"] or None,
            "link": primary_repo or None,
            "repo_url": primary_repo or None,
            "source_code_url": primary_repo or None,
            "category": categories[0] if categories else None,
            "categories": categories,
            "subcategory": None,
            "license_type": fields["license_type"] or None,
            "closed_source": False,
            "localized_metadata": localized,
            "icon_url": fields["icon_url"] or None,
            "version": fields["version"] or None,
            "platform": primary_platform,
            "platforms": artifacts,
            "separate_platform_repos": separate_repos,
            "linux_package_base": None,
            "download_url": artifacts[0]["downloadUrl"] if artifacts else None,
            "changelog": texts["changelog"] or None,
            "package_name": fields["package_name"] if "Android" in platforms else None,
            "version_code": version_code if "Android" in platforms else None,
            "screenshots": screenshots,
            "website_url": fields["website_url"] or None,
            "issue_tracker_url": fields["issue_tracker_url"] or None,
            "translation_url": fields["translation_url"] or None,
            "changelog_url": fields["changelog_url"] or None,
            "author_name": fields["author_name"] or None,
            "author_email": fields["author_email"] or None,
            "author_website": fields["author_website"] or None,
            "review_message": None,
        }
        return submission

    @staticmethod
    def _github_repository_parts(project_url):
        try:
            parsed = urllib.parse.urlparse(str(project_url).strip())
        except Exception as error:
            raise RuntimeError("Please enter a valid GitHub repository URL.") from error
        if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != "github.com":
            raise RuntimeError("Fastlane metadata requires a github.com repository URL.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise RuntimeError("Please enter the URL of a GitHub repository.")
        branch = parts[3] if len(parts) > 3 and parts[2] == "tree" else None
        return parts[0], parts[1].removesuffix(".git"), [item for item in (branch, "main", "master") if item]

    @staticmethod
    def _fetch_text_url(url):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Luma-Store-Linux/1.1"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                value = response.read().decode("utf-8").strip()
                return value or None
        except Exception:
            return None

    @staticmethod
    def _fetch_fastlane_screenshots(owner, repo, branch, locale):
        path = f"fastlane/metadata/android/{locale}/images/phoneScreenshots"
        url = (
            f"https://api.github.com/repos/{urllib.parse.quote(owner, safe='')}/"
            f"{urllib.parse.quote(repo, safe='')}/contents/{path}"
            f"?ref={urllib.parse.quote(branch, safe='')}"
        )
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Luma-Store-Linux/1.1",
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, list):
                return []
            items = [
                item for item in data
                if isinstance(item, dict)
                and item.get("type") == "file"
                and re.search(r"\.(png|jpe?g)$", str(item.get("name") or ""), re.IGNORECASE)
                and item.get("download_url")
            ]
            items.sort(key=lambda item: str(item.get("name") or ""))
            return [str(item["download_url"]) for item in items]
        except Exception:
            return []

    def load_fastlane_metadata(self, _button):
        version_code = self.submit_fields["version_code"].get_text().strip()
        if not version_code.isdigit() or int(version_code) <= 0:
            self.submit_status.set_text(
                "Enter a positive Android versionCode before checking Fastlane metadata."
            )
            return
        repo_url = self.submit_fields["repo_url"].get_text().strip()
        if self.submit_separate_repos.get_active():
            repo_url = self.submit_platform_fields["Android"]["repo_url"].get_text().strip()
        self.fastlane_button.set_sensitive(False)
        self.submit_status.set_text("Loading Android Fastlane metadata…")
        threading.Thread(
            target=self._fastlane_metadata_worker,
            args=(repo_url, int(version_code)),
            daemon=True,
        ).start()

    def _fastlane_metadata_worker(self, repo_url, version_code):
        try:
            owner, repo, branches = self._github_repository_parts(repo_url)
            for branch in dict.fromkeys(branches):
                for locale in ("en-US", "en-GB", "de-DE", "en", "de"):
                    base = (
                        f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
                        f"fastlane/metadata/android/{locale}"
                    )
                    title = self._fetch_text_url(f"{base}/title.txt")
                    if not title:
                        continue
                    short_description = self._fetch_text_url(f"{base}/short_description.txt")
                    full_description = self._fetch_text_url(f"{base}/full_description.txt")
                    if not short_description or not full_description:
                        continue
                    changelog = (
                        self._fetch_text_url(f"{base}/changelogs/{version_code}.txt")
                        or self._fetch_text_url(f"{base}/changelogs/default.txt")
                    )
                    if not changelog:
                        continue
                    screenshots = self._fetch_fastlane_screenshots(
                        owner, repo, branch, locale
                    )
                    if screenshots:
                        GLib.idle_add(
                            self._fastlane_metadata_loaded,
                            {
                                "title": title,
                                "short_description": short_description,
                                "description": full_description,
                                "changelog": changelog,
                                "screenshots": screenshots,
                                "locale": locale,
                                "branch": branch,
                            },
                        )
                        return
            raise RuntimeError(
                "Fastlane metadata is incomplete. Luma Store requires title.txt, "
                "short_description.txt, full_description.txt, a changelog for the "
                "versionCode (or default.txt), and at least one phone screenshot."
            )
        except Exception as error:
            GLib.idle_add(self._fastlane_metadata_failed, str(error))

    def _fastlane_metadata_loaded(self, metadata):
        self.fastlane_button.set_sensitive(True)
        self.submit_fields["name"].set_text(metadata["title"])
        self._set_text_view(
            self.submit_textviews["short_description"],
            metadata["short_description"],
        )
        self._set_text_view(
            self.submit_textviews["description"],
            metadata["description"],
        )
        self._set_text_view(
            self.submit_textviews["changelog"],
            metadata["changelog"],
        )
        self._set_text_view(
            self.submit_textviews["screenshots"],
            "\n".join(metadata["screenshots"]),
        )
        self.submit_status.set_text(
            f"Fastlane metadata loaded from {metadata['branch']} · {metadata['locale']}."
        )
        return False

    def _fastlane_metadata_failed(self, message):
        self.fastlane_button.set_sensitive(True)
        self.submit_status.set_text(f"Fastlane metadata could not be loaded: {message}")
        return False

    def save_submission_draft(self, _button):
        if not self.auth.access_token():
            self.submit_status.set_text("Sign in before saving a draft.")
            return
        try:
            submission = self._build_submission_payload(final=False)
        except Exception as error:
            self.submit_status.set_text(str(error))
            return
        self.submit_draft_button.set_sensitive(False)
        self.submit_status.set_text("Saving draft…")
        editing_id = self.submit_draft_id if self.submit_editing_status == "Draft" else None
        threading.Thread(
            target=self._save_draft_worker,
            args=(submission, editing_id),
            daemon=True,
        ).start()

    def _save_draft_worker(self, submission, editing_id):
        try:
            saved = self.dashboard_api.save_draft(submission, editing_id=editing_id, draft_step=1)
            GLib.idle_add(self._save_draft_done, saved)
        except Exception as error:
            GLib.idle_add(self._submission_action_failed, f"Draft could not be saved: {error}")

    def _save_draft_done(self, saved):
        self.submit_draft_button.set_sensitive(True)
        self.submit_draft_id = saved.get("id")
        self.submit_editing_id = saved.get("id")
        self.submit_editing_status = "Draft"
        self.submit_status.set_text("Draft saved.")
        self.load_dashboard_submissions()
        return False

    def submit_app(self, _button):
        if not self.auth.access_token():
            self.submit_status.set_text("Sign in before submitting an app.")
            return
        if not self.auth.provider_token():
            self.submit_status.set_text(
                "Final submission requires GitHub login. Sign out and sign in with GitHub."
            )
            return
        try:
            submission = self._build_submission_payload(final=True)
        except Exception as error:
            self.submit_status.set_text(str(error))
            return

        editing_id = self.submit_draft_id or self.submit_editing_id
        editing_status = "Draft" if self.submit_draft_id else self.submit_editing_status
        self.submit_button.set_sensitive(False)
        self.submit_draft_button.set_sensitive(False)
        self.submit_status.set_text("Submitting app…")
        threading.Thread(
            target=self._submit_app_worker,
            args=(submission, editing_id, editing_status),
            daemon=True,
        ).start()

    def _submit_app_worker(self, submission, editing_id, editing_status):
        try:
            saved = self.dashboard_api.save_submission(
                submission,
                editing_id=editing_id,
                editing_status=editing_status,
            )
            GLib.idle_add(self._submit_app_done, saved)
        except Exception as error:
            GLib.idle_add(self._submission_action_failed, f"Submission failed: {error}")

    def _submit_app_done(self, saved):
        message = (
            f"Submitted {saved.get('name') or 'app'} successfully. "
            f"Status: {saved.get('status') or 'Pending'}."
        )
        self.clear_submission_form()
        self.submit_button.set_sensitive(bool(self.auth.provider_token()))
        self.submit_draft_button.set_sensitive(True)
        self.submit_status.set_text(message)
        self.submit_expander.set_expanded(False)
        self.load_dashboard_submissions()
        return False

    def _submission_action_failed(self, message):
        self.submit_button.set_sensitive(bool(self.auth.provider_token()))
        self.submit_draft_button.set_sensitive(True)
        self.submit_status.set_text(message)
        return False

    def confirm_remove_submission(self, submission):
        submission_id = submission.get("id")
        if not submission_id:
            return
        action = "Archive" if submission.get("status") == "Approved" else "Delete"
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"{action} {submission.get('name') or 'app'}?",
        )
        dialog.format_secondary_text(
            "The published app will be archived and removed from active Store listings."
            if action == "Archive"
            else "This submission will be permanently deleted."
        )
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        self.dashboard_stats.set_text(f"{action} in progress…")
        threading.Thread(
            target=self._remove_submission_worker,
            args=(submission_id,),
            daemon=True,
        ).start()

    def _remove_submission_worker(self, submission_id):
        try:
            result = self.dashboard_api.remove_submission(submission_id)
            GLib.idle_add(self._remove_submission_done, result)
        except Exception as error:
            GLib.idle_add(self.dashboard_stats.set_text, f"Action failed: {error}")

    def _remove_submission_done(self, _result):
        self.open_dashboard()
        return False

    def load_dashboard_submissions(self):
        if not self.auth.access_token():
            self.refresh_dashboard_state()
            return
        self.dashboard_stats.set_text("Loading submissions…")
        threading.Thread(target=self._dashboard_submissions_worker, daemon=True).start()

    def _dashboard_submissions_worker(self):
        try:
            submissions = self.dashboard_api.submissions()
            GLib.idle_add(self._dashboard_submissions_loaded, submissions)
        except Exception as error:
            GLib.idle_add(self._dashboard_submissions_failed, str(error))

    def _dashboard_submissions_loaded(self, submissions):
        submissions = submissions if isinstance(submissions, list) else []
        self.clear(self.dashboard_list)
        counts = {}
        for submission in submissions:
            status = str(submission.get("status") or "Unknown")
            counts[status] = counts.get(status, 0) + 1
            self.dashboard_list.add(self.submission_row(submission))

        summary_order = ["Draft", "Pending", "In Review", "Changes Requested", "Approved", "Rejected", "Archived"]
        summary = "  •  ".join(f"{name}: {counts[name]}" for name in summary_order if counts.get(name))
        self.dashboard_stats.set_text(
            f"{len(submissions)} submission(s)" + (f"  —  {summary}" if summary else "")
        )
        if not submissions:
            empty = Gtk.Label(label="No submissions yet.", xalign=0)
            empty.set_border_width(14)
            empty.get_style_context().add_class("muted")
            self.dashboard_list.add(empty)
        self.dashboard_list.show_all()
        self.refresh_dashboard_state()
        return False

    def _dashboard_submissions_failed(self, message):
        self.dashboard_stats.set_text(f"Could not load dashboard: {message}")
        return False

    def submission_row(self, submission):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        box.set_border_width(13)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=submission.get("name") or "Untitled submission", xalign=0)
        name.get_style_context().add_class("app-name")
        status_text = str(submission.get("status") or "Unknown")
        status = Gtk.Label(label=status_text, xalign=0)
        lowered = status_text.lower()
        if lowered == "approved":
            status.get_style_context().add_class("status-approved")
        elif lowered == "rejected":
            status.get_style_context().add_class("status-rejected")
        elif lowered in ("pending", "changes requested"):
            status.get_style_context().add_class("status-pending")
        elif lowered == "in review":
            status.get_style_context().add_class("status-review")
        title_line.pack_start(name, False, False, 0)
        title_line.pack_start(status, False, False, 0)
        text.pack_start(title_line, False, False, 0)

        description = submission.get("short_description") or submission.get("description") or ""
        if description:
            desc = Gtk.Label(label=str(description), xalign=0, ellipsize=3)
            desc.get_style_context().add_class("muted")
            text.pack_start(desc, False, False, 0)

        meta_bits = [
            str(value) for value in (
                submission.get("category"),
                submission.get("platform"),
                submission.get("version"),
            ) if value
        ]
        if meta_bits:
            meta = Gtk.Label(label="  •  ".join(meta_bits), xalign=0)
            meta.get_style_context().add_class("muted")
            text.pack_start(meta, False, False, 0)

        review_message = submission.get("review_message")
        if review_message:
            review = Gtk.Label(label=f"Review: {review_message}", xalign=0, wrap=True)
            review.get_style_context().add_class("status-pending")
            text.pack_start(review, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        details = Gtk.Button(label="Details")
        details.connect("clicked", self.show_submission_details, submission)
        actions.pack_start(details, False, False, 0)

        if status_text in ("Draft", "Rejected", "Changes Requested", "Approved"):
            edit = Gtk.Button(
                label="Continue draft" if status_text == "Draft"
                else "Submit update" if status_text == "Approved"
                else "Edit / resubmit"
            )
            edit.connect("clicked", lambda _b, item=submission: self.edit_submission_in_form(item))
            actions.pack_start(edit, False, False, 0)

        if status_text in ("Draft", "Pending", "In Review", "Changes Requested", "Rejected", "Approved"):
            remove = Gtk.Button(label="Archive" if status_text == "Approved" else "Delete")
            remove.connect("clicked", lambda _b, item=submission: self.confirm_remove_submission(item))
            actions.pack_start(remove, False, False, 0)

        box.pack_start(text, True, True, 0)
        box.pack_end(actions, False, False, 0)
        row.add(box)
        return row

    def show_submission_details(self, _button, submission):
        self.open_submission_by_id(submission.get("id"))


    @staticmethod
    def clear(container):
        for child in container.get_children():
            container.remove(child)

    def app_row(self, app):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        box.set_border_width(12)

        icon_image = Gtk.Image()
        icon_image.set_size_request(48, 48)
        box.pack_start(icon_image, False, False, 0)
        icon_url = app.get("icon") or app.get("icon_url")
        if icon_url:
            self._set_image_from_url(icon_image, icon_url, 48, 48)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        name = Gtk.Label(label=app.get("name") or "Unnamed app", xalign=0)
        name.get_style_context().add_class("app-name")
        summary = Gtk.Label(label=app.get("summary") or app.get("description") or "", xalign=0, ellipsize=3)
        text.pack_start(name, False, False, 0)
        text.pack_start(summary, False, False, 0)
        view = Gtk.Button(label="View")
        view.connect("clicked", self.open_details, app)
        box.pack_start(text, True, True, 0)
        box.pack_end(view, False, False, 0)
        row.add(box)
        return row

    def load_apps(self):
        self.discover_status.set_text("Loading Linux apps from API…")
        threading.Thread(target=self._load_apps_worker, daemon=True).start()

    def _load_apps_worker(self):
        try:
            apps = LumaApi.apps()
            GLib.idle_add(self._apps_loaded, apps)
        except Exception as error:
            GLib.idle_add(self.discover_status.set_text, f"Could not load apps: {error}")

    def _apps_loaded(self, apps):
        self.apps = apps if isinstance(apps, list) else []
        self.clear(self.discover_list)
        for app in self.apps:
            self.discover_list.add(self.app_row(app))
        self.discover_status.set_text(f"{len(self.apps)} Linux app(s) available.")
        self.discover_list.show_all()
        self.rebuild_categories()
        return False

    def search_apps(self, _entry):
        query = self.search_entry.get_text().strip()
        self.clear(self.search_list)
        if not query:
            self.search_status.set_text("Enter a search term.")
            return
        self.search_status.set_text("Searching API…")
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query):
        try:
            apps = LumaApi.apps(search=query)
            GLib.idle_add(self._search_loaded, apps)
        except Exception as error:
            GLib.idle_add(self.search_status.set_text, f"Search failed: {error}")

    def _search_loaded(self, apps):
        apps = apps if isinstance(apps, list) else []
        self.clear(self.search_list)
        for app in apps:
            self.search_list.add(self.app_row(app))
        self.search_status.set_text(f"{len(apps)} result(s).")
        self.search_list.show_all()
        return False

    def rebuild_categories(self):
        self.clear(self.categories_box)
        categories = sorted({str(app.get("category")) for app in self.apps if app.get("category")})
        if not categories:
            self.categories_box.pack_start(Gtk.Label(label="No categories returned by the API.", xalign=0), False, False, 0)
        for category in categories:
            button = Gtk.Button(label=category)
            button.connect("clicked", self.show_category, category)
            self.categories_box.pack_start(button, False, False, 0)
        self.categories_box.show_all()

    def reset_and_show_discover(self):
        self.clear(self.discover_list)
        for app in self.apps:
            self.discover_list.add(self.app_row(app))
        self.discover_status.set_text(f"{len(self.apps)} Linux app(s) available.")
        self.discover_list.show_all()
        self.show_page("discover")

    def show_category(self, _button, category):
        self.clear(self.discover_list)
        matching = [app for app in self.apps if str(app.get("category")) == category]
        for app in matching:
            self.discover_list.add(self.app_row(app))
        self.discover_status.set_text(f"{category}: {len(matching)} app(s)")
        self.discover_list.show_all()
        self.show_page("discover")

    def open_details(self, _button, app):
        app_id = app.get("id")
        if app_id is None:
            self.render_details(app)
            return
        self.details_title.set_text("Loading…")
        self.show_page("details")
        threading.Thread(target=self._details_worker, args=(app_id, app), daemon=True).start()

    def _details_worker(self, app_id, fallback):
        try:
            app = LumaApi.app(app_id)
        except Exception:
            app = fallback
        GLib.idle_add(self.render_details, app)

    def render_details(self, app):
        self.current_app = app
        self.details_title.set_text(app.get("name") or "App")
        self.details_summary.set_text(app.get("summary") or app.get("description") or "")

        # Icon
        self.details_icon.set_from_icon_name("system-run", Gtk.IconSize.DIALOG)
        icon_url = app.get("icon") or app.get("icon_url")
        if icon_url:
            self._set_image_from_url(self.details_icon, icon_url, 64, 64)

        # Screenshots
        self.clear(self.screenshots_box)
        screenshots = app.get("screenshots") or app.get("images") or []
        if isinstance(screenshots, str):
            screenshots = [s.strip() for s in screenshots.split(",") if s.strip()]

        if screenshots:
            self.screenshots_label.show()
            self.screenshots_scrolled.show()
            for screenshot_url in screenshots:
                img = Gtk.Image()
                img.set_margin_bottom(12)
                self.screenshots_box.pack_start(img, False, False, 0)
                self._set_image_from_url(img, screenshot_url, 320, 180)
        else:
            self.screenshots_label.hide()
            self.screenshots_scrolled.hide()

        category = app.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        version = app.get("version") or app.get("version_name") or "Unknown"
        size = app.get("file_size_mb")
        package_format = app.get("package_format") or app.get("linux_package_base") or ""
        meta = f"Category: {category or 'Unknown'}  •  Version: {version}"
        if package_format:
            meta += f"  •  {package_format}"
        if size is not None:
            meta += f"  •  {size} MB"
        self.details_meta.set_text(meta)
        download_url = app.get("download_url") or ""
        self.details_download.set_text(f"Download: {download_url or 'No Linux download available'}")

        # Extra dynamic dynamic fields from API
        self.clear(self.extra_fields_box)
        known_keys = {"name", "summary", "description", "icon", "icon_url", "screenshots", "images", "category", "version", "version_name", "file_size_mb", "package_format", "linux_package_base", "download_url", "id"}
        extra_content_added = False
        for k, v in app.items():
            if k not in known_keys and v is not None and str(v).strip():
                extra_content_added = True
                lbl_key = k.replace("_", " ").title()
                field_label = Gtk.Label(xalign=0, selectable=True, wrap=True)
                field_label.set_markup(f"<b>{lbl_key}:</b> {v}")
                self.extra_fields_box.pack_start(field_label, False, False, 0)

        if extra_content_added:
            self.extra_fields_label.show()
            self.extra_fields_box.show()
        else:
            self.extra_fields_label.hide()
            self.extra_fields_box.hide()

        fmt = package_format.lower()
        url_lower = download_url.lower()
        is_deb = fmt == "deb" or fmt == "debian" or ".deb" in url_lower
        is_rpm = fmt == "rpm" or ".rpm" in url_lower

        if is_deb:
            self.install_button.set_label("Install DEB Package")
            self.install_button.set_visible(True)
            self.install_button.set_sensitive(True)
            self.install_status.set_text("")
        elif is_rpm:
            self.install_button.set_label("Install RPM Package")
            self.install_button.set_visible(True)
            self.install_button.set_sensitive(True)
            self.install_status.set_text("")
        else:
            self.install_button.set_visible(False)
            self.install_status.set_text("No supported package format available for this app." if download_url else "No Linux download available.")

        self.show_page("details")
        return False

    def install_current_app(self, _button):
        app = self.current_app or {}
        url = app.get("download_url") or ""
        package_format = app.get("package_format") or app.get("linux_package_base") or ""

        fmt = package_format.lower()
        url_lower = url.lower()
        is_deb = fmt == "deb" or fmt == "debian" or ".deb" in url_lower
        is_rpm = fmt == "rpm" or ".rpm" in url_lower

        if not (is_deb or is_rpm):
            self.install_status.set_text("Unsupported package format.")
            return

        self.install_button.set_sensitive(False)
        if is_deb:
            self.install_status.set_text("Downloading DEB Package…")
            threading.Thread(target=self._install_native_package_worker, args=(app, url, "deb"), daemon=True).start()
        elif is_rpm:
            self.install_status.set_text("Downloading RPM Package…")
            threading.Thread(target=self._install_native_package_worker, args=(app, url, "rpm"), daemon=True).start()


    def _install_native_package_worker(self, app, url, pkg_type):
        try:
            target_dir = Path.home() / "Downloads"
            target_dir.mkdir(parents=True, exist_ok=True)
            parsed_name = Path(urllib.parse.urlparse(url).path).name
            safe_app_name = re.sub(r"[^A-Za-z0-9._-]+", "-", app.get("name") or "app").strip("-") or "app"
            ext = f".{pkg_type}"
            filename = parsed_name if parsed_name.lower().endswith(ext) else f"{safe_app_name}{ext}"
            destination = target_dir / filename
            temporary = destination.with_suffix(destination.suffix + ".part")
            request = urllib.request.Request(url, headers={"User-Agent": "Luma-Store-Linux/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response, open(temporary, "wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            temporary.replace(destination)
            file_uri = destination.as_uri()
            GLib.idle_add(self._launch_package_installer, file_uri, str(destination), pkg_type)
        except Exception as error:
            GLib.idle_add(self._install_failed, str(error))

    def _launch_package_installer(self, file_uri, file_path, pkg_type):
        try:
            success = Gio.AppInfo.launch_default_for_uri(file_uri, None)
            if success:
                self.install_status.set_text(f"Downloaded package to {file_path} and opened the system installer.")
            else:
                self.install_status.set_text(f"Downloaded package to {file_path}. Please open it to complete the installation.")
        except Exception as error:
            self.install_status.set_text(f"Downloaded package to {file_path}, but could not open installer: {error}")
        self.install_button.set_label(f"Reinstall {pkg_type.upper()}")
        self.install_button.set_sensitive(True)
        return False

    def _install_finished(self, destination):
        self.install_status.set_text(f"Downloaded package to {destination}")
        self.install_button.set_sensitive(True)
        return False

    def _install_failed(self, message):
        self.install_status.set_text(f"Installation failed: {message}")
        self.install_button.set_sensitive(True)
        return False

    def _set_image_from_url(self, gtk_image, url, width=None, height=None):
        def worker():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Luma-Store-Linux/0.1"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = response.read()

                loader = GdkPixbuf.PixbufLoader()
                loader.write(data)
                loader.close()
                pixbuf = loader.get_pixbuf()

                if pixbuf and width and height:
                    pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)

                GLib.idle_add(gtk_image.set_from_pixbuf, pixbuf)
                GLib.idle_add(gtk_image.show)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()


class LumaStore(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.freetime.lumastore", flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        window = self.props.active_window or LumaStoreWindow(self)
        window.show_all()
        window.present()


if __name__ == "__main__":
    raise SystemExit(LumaStore().run(None))
