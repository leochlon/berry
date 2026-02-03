"""
Berry CLI Authentication Flow

Provides professional browser-based authentication similar to Claude Code, Codex, and Gemini CLI.

Two flows supported:
1. Localhost Callback (default): Opens browser, user authenticates, browser redirects to localhost
2. Device Code Flow (fallback for headless): Displays code, user enters on website, CLI polls for completion

Usage:
    berry auth login          # Auto-detect best flow
    berry auth login --device # Force device code flow
"""

from __future__ import annotations

import http.server
import json
import os
import secrets
import socketserver
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import urllib.request

# Default service URLs
DEFAULT_BASE_URL = "https://strawberry.hassana.io"
DEFAULT_LITELLM_URL = "http://20.232.57.156/v1"
DEFAULT_BERRY_SERVICE_URL = "http://52.191.234.157:8000"


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    api_key: Optional[str] = None
    user_id: Optional[str] = None
    error: Optional[str] = None


def get_base_url() -> str:
    """Get the Strawberry API base URL."""
    return os.environ.get("STRAWBERRY_BASE_URL", DEFAULT_BASE_URL)


def _request_json(url: str, method: str = "GET", data: Optional[dict] = None, timeout: int = 30) -> dict:
    """Make an HTTP request and return JSON response."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# =============================================================================
# Localhost Callback Flow
# =============================================================================

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for receiving the OAuth callback."""

    result: Optional[AuthResult] = None

    def log_message(self, format, *args):
        """Suppress HTTP logs."""
        pass

    def do_GET(self):
        """Handle the callback GET request."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        api_key = params.get("api_key", [None])[0]
        status = params.get("status", [None])[0]
        error = params.get("error", [None])[0]

        if status == "success" and api_key:
            CallbackHandler.result = AuthResult(success=True, api_key=api_key)
            self._send_success_page()
        else:
            err_msg = error or "Authentication failed"
            CallbackHandler.result = AuthResult(success=False, error=err_msg)
            self._send_error_page(err_msg)

    def _send_success_page(self):
        """Send success HTML page."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Berry CLI - Authenticated</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { text-align: center; padding: 2rem; }
        .icon { width: 64px; height: 64px; background: rgba(34, 197, 94, 0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; }
        .icon svg { width: 32px; height: 32px; color: #22c55e; }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        p { color: #9ca3af; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
        </div>
        <h1>Authentication Successful!</h1>
        <p>You can close this window and return to your terminal.</p>
    </div>
    <script>setTimeout(() => window.close(), 3000);</script>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_error_page(self, error: str):
        """Send error HTML page."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Berry CLI - Error</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
        .container {{ text-align: center; padding: 2rem; }}
        .icon {{ width: 64px; height: 64px; background: rgba(239, 68, 68, 0.2); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; }}
        .icon svg {{ width: 32px; height: 32px; color: #ef4444; }}
        h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
        p {{ color: #9ca3af; }}
        code {{ background: #1f2937; padding: 0.25rem 0.5rem; border-radius: 0.25rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </div>
        <h1>Authentication Failed</h1>
        <p>{error}</p>
        <p style="margin-top: 1rem;">Please run <code>berry auth login</code> again.</p>
    </div>
</body>
</html>"""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def _find_available_port(start: int = 8400, end: int = 8500) -> int:
    """Find an available port in the given range."""
    import socket
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError("No available ports found")


def localhost_callback_flow(timeout: int = 300, verbose: bool = False) -> AuthResult:
    """
    Run the localhost callback authentication flow with polling.

    1. Request auth session from server
    2. Open browser for user to authenticate
    3. Poll server for completion (avoids HTTPS→HTTP redirect issues)
    """
    base_url = get_base_url()

    # We still register a callback URL for backwards compatibility,
    # but primarily rely on polling
    port = _find_available_port()
    callback_url = f"http://localhost:{port}/callback"

    # Reset handler result
    CallbackHandler.result = None

    # Start server in background thread (as fallback)
    server = socketserver.TCPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 1
    server_thread = threading.Thread(target=lambda: _run_server(server, timeout))
    server_thread.daemon = True
    server_thread.start()

    interrupted = False
    try:
        # Request session from API
        print(f"Contacting {base_url}...", flush=True)

        try:
            response = _request_json(
                f"{base_url}/api/auth/cli",
                method="POST",
                data={"callback_url": callback_url},
                timeout=10
            )
        except Exception as e:
            return AuthResult(success=False, error=f"Could not reach auth server at {base_url}: {e}")

        session_id = response.get("session_id")
        auth_url = response.get("auth_url")

        if not auth_url or not session_id:
            return AuthResult(success=False, error="Failed to get auth URL from server")

        # Open browser
        print(f"\nOpening browser to authenticate...", flush=True)
        print(f"If the browser doesn't open, visit:\n  {auth_url}\n", flush=True)

        if not webbrowser.open(auth_url):
            print("Could not open browser automatically.", flush=True)

        # Poll for completion (primary method)
        # Also check localhost callback as fallback
        print("Waiting for authentication...", flush=True)
        print("(Complete sign-in in your browser, then return here)", flush=True)
        start_time = time.time()
        poll_interval = 2  # seconds
        last_status_time = start_time

        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                return AuthResult(success=False, error="Authentication timed out")

            # Check localhost callback (fallback)
            if CallbackHandler.result is not None:
                return CallbackHandler.result

            # Poll the server
            try:
                poll_response = _request_json(
                    f"{base_url}/api/auth/cli/poll?session_id={session_id}",
                    method="GET",
                    timeout=10
                )

                if verbose:
                    print(f"  [poll] Response: {poll_response}", flush=True)

                # Check for pending status (server may return this on 200/202)
                if poll_response.get("error") == "authorization_pending":
                    # Continue polling
                    pass
                # Success - got the API key
                elif poll_response.get("status") == "success":
                    api_key = poll_response.get("api_key")
                    if api_key:
                        # Signal the server thread to exit (it checks CallbackHandler.result)
                        result = AuthResult(
                            success=True,
                            api_key=api_key,
                            user_id=poll_response.get("user_id")
                        )
                        CallbackHandler.result = result
                        return result
            except urllib.error.HTTPError as e:
                if verbose:
                    print(f"  [poll] HTTP {e.code}: {e.read().decode()}", flush=True)
                if e.code == 202:
                    # Still pending, continue polling
                    pass
                elif e.code == 404 or e.code == 410:
                    return AuthResult(success=False, error="Session expired. Please try again.")
                # Other errors - continue polling
            except Exception as poll_err:
                if verbose:
                    print(f"  [poll] Error: {poll_err}", flush=True)
                # Network error - continue polling
                pass

            # Show progress indicator every 30 seconds
            current_time = time.time()
            if current_time - last_status_time >= 30:
                elapsed = int(current_time - start_time)
                print(f"Still waiting... ({elapsed}s elapsed. Press Ctrl+C to cancel)", flush=True)
                last_status_time = current_time

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        # User cancelled - mark as interrupted so finally block skips shutdown()
        interrupted = True
        return AuthResult(success=False, error="Authentication cancelled")
    except urllib.error.URLError as e:
        return AuthResult(success=False, error=f"Network error: {e}")
    except Exception as e:
        return AuthResult(success=False, error=str(e))
    finally:
        # Clean up the server.
        # NOTE: Do NOT call server.shutdown() - it's designed for serve_forever()
        # and blocks indefinitely when using handle_request() loop like we do.
        # Since the server thread is a daemon thread, it will die automatically
        # when the main thread exits. We just need to close the socket.
        try:
            server.server_close()
        except (OSError, KeyboardInterrupt):
            pass


def _run_server(server: socketserver.TCPServer, timeout: int):
    """Run the server until callback received or timeout."""
    start = time.time()
    while CallbackHandler.result is None and time.time() - start < timeout:
        server.handle_request()


# =============================================================================
# Device Code Flow
# =============================================================================

def device_code_flow(timeout: int = 900, verbose: bool = False) -> AuthResult:
    """
    Run the device code authentication flow.

    1. Request device code from server
    2. Display code to user
    3. Poll for completion
    """
    base_url = get_base_url()

    try:
        # Request device code
        print(f"Contacting {base_url}...", flush=True)
        try:
            response = _request_json(
                f"{base_url}/api/auth/device",
                method="POST",
                data={},
                timeout=10
            )
        except Exception as e:
            return AuthResult(success=False, error=f"Could not reach auth server at {base_url}: {e}")

        device_code = response.get("device_code")
        user_code = response.get("user_code")
        verification_uri = response.get("verification_uri")
        verification_uri_complete = response.get("verification_uri_complete")
        interval = response.get("interval", 5)
        expires_in = response.get("expires_in", 900)

        if not device_code or not user_code:
            return AuthResult(success=False, error="Failed to get device code from server")

        # Display instructions
        print("\n" + "=" * 60, flush=True)
        print("  BERRY CLI AUTHENTICATION", flush=True)
        print("=" * 60, flush=True)
        print(f"\n  Your code: {user_code}\n", flush=True)
        print(f"  Visit: {verification_uri}", flush=True)
        print(f"  Or scan/click: {verification_uri_complete}", flush=True)
        print("\n" + "=" * 60, flush=True)
        print("\nWaiting for authorization...", flush=True)

        # Try to open browser
        try:
            webbrowser.open(verification_uri_complete)
        except Exception:
            pass  # Browser open is optional

        # Poll for completion
        start_time = time.time()
        poll_interval = max(interval, 5)

        while True:
            elapsed = time.time() - start_time
            if elapsed > min(timeout, expires_in):
                return AuthResult(success=False, error="Device code expired. Please try again.")

            time.sleep(poll_interval)

            try:
                token_response = _request_json(
                    f"{base_url}/api/auth/device/token",
                    method="POST",
                    data={"device_code": device_code}
                )

                # Check if authorized
                api_key = token_response.get("api_key")
                if api_key:
                    return AuthResult(
                        success=True,
                        api_key=api_key,
                        user_id=token_response.get("user_id")
                    )

            except urllib.error.HTTPError as e:
                if e.code == 400:
                    body = json.loads(e.read().decode("utf-8"))
                    error = body.get("error", "")

                    if error == "authorization_pending":
                        # Still waiting, continue polling
                        sys.stdout.write(".")
                        sys.stdout.flush()
                        continue
                    elif error == "expired_token":
                        return AuthResult(success=False, error="Device code expired. Please try again.")
                    else:
                        return AuthResult(success=False, error=body.get("message", error))
                raise
            except Exception as e:
                # Network error, retry
                continue

    except urllib.error.URLError as e:
        return AuthResult(success=False, error=f"Network error: {e}")
    except Exception as e:
        return AuthResult(success=False, error=str(e))


# =============================================================================
# Main Authentication Function
# =============================================================================

def authenticate(
    force_device: bool = False,
    force_localhost: bool = False,
    timeout: int = 300,
    verbose: bool = False,
) -> AuthResult:
    """
    Run authentication flow, auto-detecting the best method.

    Args:
        force_device: Force device code flow (for headless environments)
        force_localhost: Force localhost callback flow
        timeout: Timeout in seconds
        verbose: Show detailed debug output

    Returns:
        AuthResult with api_key on success
    """
    # Determine which flow to use
    use_device = force_device

    if not force_localhost and not force_device:
        # Auto-detect: use device code if no display available
        if os.environ.get("SSH_TTY") or os.environ.get("SSH_CLIENT"):
            # SSH session - use device code
            use_device = True
        elif not os.environ.get("DISPLAY") and sys.platform != "darwin" and sys.platform != "win32":
            # No display on Linux - use device code
            use_device = True

    if use_device:
        return device_code_flow(timeout=timeout, verbose=verbose)
    else:
        # Try localhost first, fall back to device code on failure
        result = localhost_callback_flow(timeout=timeout, verbose=verbose)
        if not result.success and "Network error" in (result.error or ""):
            print("\nLocalhost callback failed, trying device code flow...")
            return device_code_flow(timeout=timeout, verbose=verbose)
        return result


def save_credentials(api_key: str, base_url: Optional[str] = None) -> Path:
    """
    Save API key to Berry's config file.

    Returns the path to the saved config file.
    """
    from .paths import ensure_berry_home, mcp_env_path

    ensure_berry_home()
    p = mcp_env_path()

    # Load existing config
    env: dict[str, str] = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                env = {str(k): str(v) for k, v in raw.items() if k and v is not None}
        except Exception:
            env = {}

    # Update with new credentials
    env["OPENAI_API_KEY"] = api_key
    env["OPENAI_BASE_URL"] = base_url or DEFAULT_LITELLM_URL
    env["BERRY_SERVICE_URL"] = DEFAULT_BERRY_SERVICE_URL

    # Write config
    p.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Lock down permissions on POSIX
    try:
        if os.name != "nt":
            p.chmod(0o600)
    except Exception:
        pass

    return p


def run_login_flow(
    force_device: bool = False,
    force_localhost: bool = False,
    no_integrate: bool = False,
    interactive: bool = True,
    verbose: bool = False,
) -> int:
    """
    Run the full login flow with UI and credential saving.

    Returns exit code (0 for success, non-zero for failure).
    """
    if interactive:
        print("Berry CLI Authentication", flush=True)
        print("-" * 40, flush=True)
        print("Sign in to connect your Strawberry API account.\n", flush=True)

    # Run auth flow
    result = authenticate(
        force_device=force_device,
        force_localhost=force_localhost,
        verbose=verbose,
    )

    if not result.success:
        print(f"\nAuthentication failed: {result.error}")
        return 1

    if not result.api_key:
        print("\nAuthentication failed: No API key received")
        return 1

    # Save credentials
    config_path = save_credentials(result.api_key)
    print(f"\nAuthentication successful!")
    print(f"Credentials saved to: {config_path}")

    # Update global MCP configs
    if not no_integrate:
        if interactive:
            print("\nUpdating MCP client configurations...")
        try:
            from .integration import integrate
            results = integrate(
                clients=["cursor", "claude", "codex", "gemini"],
                name="berry",
                timeout_s=20,
                dry_run=False,
                managed=True,
                managed_only=False,
            )
            has_permission_error = False
            if interactive:
                for r in results:
                    if r.status == "ok":
                        print(f"  {r.client}: configured")
                    else:
                        print(f"  {r.client}: {r.status} - {r.message}")
                        if "Permission denied" in (r.message or ""):
                            has_permission_error = True
                if has_permission_error:
                    print("\n  Tip: To update system-managed configs, run: sudo berry integrate --managed")
        except Exception as e:
            if interactive:
                print(f"  Warning: Could not update MCP configs: {e}")

    print("\nYou're all set! Berry is now configured.")
    return 0
