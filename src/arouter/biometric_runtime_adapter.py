from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast


class BiometricRuntimeAdapter:
    def __init__(
        self,
        *,
        runtime: Any,
        prefer_arouter_helpers: bool,
        asee_client_available: bool,
        default_lock_signal_file: str,
        default_unlock_signal_file: str,
        default_password_file: str,
        default_password_private_key: str,
        default_lock_screen_text: Any,
        default_locked_denied_text: Any,
        biometric_lock_enabled: Any,
        biometric_unlock_success_text: Any,
        ensure_biometric_runtime_attrs: Any,
        resolve_biometric_arg_path: Any,
        seed_signal_seen_mtime: Any,
        set_system_locked: Any,
        reassert_lock_screen: Any,
        unlock_requires_live_voice_text: Any,
        unlock_requires_speaker_auth_text: Any,
        unlock_requires_face_auth_text: Any,
        unlock_requires_password_text: Any,
        run_biometric_status_url_fetch: Any,
        run_biometric_status_client_get: Any,
        run_biometric_status_runtime_fetch: Any,
        run_biometric_password_candidate_load: Any,
        load_password_candidates: Any,
        verify_unlock_password: Any,
        run_biometric_signal_consume: Any,
        consume_signal_file: Any,
        record_successful_command_activity: Any,
        run_biometric_owner_face_absent_runtime_check: Any,
        run_biometric_owner_face_recent_runtime_check: Any,
        maybe_unlock_from_signal: Any,
        maybe_lock_from_signal: Any,
        maybe_auto_lock: Any,
        authorize_command: Any,
        resolve_biometric_poll_interval: Any,
        run_biometric_poller_loop: Any,
        run_biometric_poll_iteration: Any,
        start_biometric_poller: Any,
        stop_biometric_poller: Any,
        resolve_remote_status_client: Any,
        fetch_remote_status: Any,
        owner_face_absent_from_status: Any,
        owner_face_recent_from_status: Any,
        request_builder: Any,
        urlopen: Any,
        json_loads: Any,
        normalize_transcript: Any,
        now: Any,
        lock_factory: Any,
        event_factory: Any,
        thread_factory: Any,
    ) -> None:
        self.runtime = runtime
        self.prefer_arouter_helpers = bool(prefer_arouter_helpers)
        self.asee_client_available = bool(asee_client_available)
        self.default_lock_signal_file = default_lock_signal_file
        self.default_unlock_signal_file = default_unlock_signal_file
        self.default_password_file = default_password_file
        self.default_password_private_key = default_password_private_key
        self.default_lock_screen_text = default_lock_screen_text
        self.default_locked_denied_text = default_locked_denied_text
        self.biometric_lock_enabled_fn = biometric_lock_enabled
        self.biometric_unlock_success_text_fn = biometric_unlock_success_text
        self.ensure_biometric_runtime_attrs_fn = ensure_biometric_runtime_attrs
        self.resolve_biometric_arg_path = resolve_biometric_arg_path
        self.seed_signal_seen_mtime_fn = seed_signal_seen_mtime
        self.set_system_locked_fn = set_system_locked
        self.reassert_lock_screen_fn = reassert_lock_screen
        self.unlock_requires_live_voice_text_fn = unlock_requires_live_voice_text
        self.unlock_requires_speaker_auth_text_fn = unlock_requires_speaker_auth_text
        self.unlock_requires_face_auth_text_fn = unlock_requires_face_auth_text
        self.unlock_requires_password_text_fn = unlock_requires_password_text
        self.run_biometric_status_url_fetch = run_biometric_status_url_fetch
        self.run_biometric_status_client_get = run_biometric_status_client_get
        self.run_biometric_status_runtime_fetch = run_biometric_status_runtime_fetch
        self.run_biometric_password_candidate_load = run_biometric_password_candidate_load
        self.load_password_candidates = load_password_candidates
        self.verify_unlock_password_fn = verify_unlock_password
        self.run_biometric_signal_consume = run_biometric_signal_consume
        self.consume_signal_file = consume_signal_file
        self.record_successful_command_activity_fn = record_successful_command_activity
        self.run_biometric_owner_face_absent_runtime_check = (
            run_biometric_owner_face_absent_runtime_check
        )
        self.run_biometric_owner_face_recent_runtime_check = (
            run_biometric_owner_face_recent_runtime_check
        )
        self.maybe_unlock_from_signal_fn = maybe_unlock_from_signal
        self.maybe_lock_from_signal_fn = maybe_lock_from_signal
        self.maybe_auto_lock_fn = maybe_auto_lock
        self.authorize_command_fn = authorize_command
        self.resolve_biometric_poll_interval_fn = resolve_biometric_poll_interval
        self.run_biometric_poller_loop_fn = run_biometric_poller_loop
        self.run_biometric_poll_iteration_fn = run_biometric_poll_iteration
        self.start_biometric_poller_fn = start_biometric_poller
        self.stop_biometric_poller_fn = stop_biometric_poller
        self.resolve_remote_status_client = resolve_remote_status_client
        self.fetch_remote_status = fetch_remote_status
        self.owner_face_absent_from_status = owner_face_absent_from_status
        self.owner_face_recent_from_status = owner_face_recent_from_status
        self.request_builder = request_builder
        self.urlopen = urlopen
        self.json_loads = json_loads
        self.normalize_transcript = normalize_transcript
        self.now = now
        self.lock_factory = lock_factory
        self.event_factory = event_factory
        self.thread_factory = thread_factory

    def __getattr__(self, name: str) -> Any:
        return getattr(self.runtime, name)

    def _set_locked_callback(self, _runtime: Any, locked: bool, *, reason: str) -> bool:
        return bool(self._set_system_locked(locked, reason=reason))

    def _instance_override(self, name: str) -> Any | None:
        override = getattr(self.runtime, "__dict__", {}).get(name)
        return override if callable(override) else None

    def _debug(self, msg: str) -> None:
        debug = getattr(self.runtime, "debug", None)
        if callable(debug):
            debug(msg)

    def _log(self, msg: str) -> None:
        log = getattr(self.runtime, "log", None)
        if callable(log):
            log(msg)

    def _args(self) -> Any:
        return getattr(self.runtime, "args", None)

    def _biometric_lock_enabled(self) -> bool:
        override = self._instance_override("_biometric_lock_enabled")
        if override is not None:
            return bool(override())
        args = self._args()
        if self.prefer_arouter_helpers:
            return bool(self.biometric_lock_enabled_fn(args))
        return bool(getattr(args, "biometric_lock", False))

    def _ensure_biometric_runtime_attrs(self) -> None:
        override = self._instance_override("_ensure_biometric_runtime_attrs")
        if override is not None:
            override()
            return
        if self.prefer_arouter_helpers:
            self.ensure_biometric_runtime_attrs_fn(
                self.runtime,
                now=self.now,
                lock_factory=self.lock_factory,
                event_factory=self.event_factory,
                seed_lock_seen_mtime=lambda: self._seed_signal_seen_mtime(
                    signal_arg_name="biometric_lock_signal_file",
                    default_path=self.default_lock_signal_file,
                ),
                seed_unlock_seen_mtime=lambda: self._seed_signal_seen_mtime(
                    signal_arg_name="biometric_unlock_signal_file",
                    default_path=self.default_unlock_signal_file,
                ),
            )
            return
        if not hasattr(self.runtime, "_biometric_lock_state_lock"):
            self.runtime._biometric_lock_state_lock = self.lock_factory()
        if not hasattr(self.runtime, "_system_locked"):
            self.runtime._system_locked = False
        if not hasattr(self.runtime, "_lock_screen_visible"):
            self.runtime._lock_screen_visible = False
        if not hasattr(self.runtime, "_last_successful_command_at"):
            self.runtime._last_successful_command_at = self.now()
        if not hasattr(self.runtime, "_biometric_poll_stop_event"):
            self.runtime._biometric_poll_stop_event = self.event_factory()
        if not hasattr(self.runtime, "_biometric_poll_thread"):
            self.runtime._biometric_poll_thread = None
        if not hasattr(self.runtime, "_biometric_password_candidates_cache"):
            self.runtime._biometric_password_candidates_cache = None
        if not hasattr(self.runtime, "_biometric_status_client"):
            self.runtime._biometric_status_client = None
        if not hasattr(self.runtime, "_biometric_lock_signal_seen_mtime"):
            self.runtime._biometric_lock_signal_seen_mtime = self._seed_signal_seen_mtime(
                signal_arg_name="biometric_lock_signal_file",
                default_path=self.default_lock_signal_file,
            )
        if not hasattr(self.runtime, "_biometric_unlock_signal_seen_mtime"):
            self.runtime._biometric_unlock_signal_seen_mtime = self._seed_signal_seen_mtime(
                signal_arg_name="biometric_unlock_signal_file",
                default_path=self.default_unlock_signal_file,
            )

    def _seed_signal_seen_mtime(self, *, signal_arg_name: str, default_path: str) -> float:
        override = self._instance_override("_seed_signal_seen_mtime")
        if override is not None:
            return float(
                override(signal_arg_name=signal_arg_name, default_path=default_path)
            )
        args = self._args()
        if self.prefer_arouter_helpers:
            signal_path = self.resolve_biometric_arg_path(
                args=args,
                attr_name=signal_arg_name,
                default_path=default_path,
            )
            return float(self.seed_signal_seen_mtime_fn(signal_path=signal_path, seen_mtime=0.0))
        signal_path = Path(
            os.path.expanduser(str(getattr(args, signal_arg_name, default_path)))
        )
        try:
            return float(signal_path.stat().st_mtime)
        except Exception:
            return 0.0

    def _lock_screen_text(self) -> str:
        override = self._instance_override("_lock_screen_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.default_lock_screen_text())
        return "SYSTEM LOCKED\nNeed biometric authentication"

    def _set_system_locked(self, locked: bool, *, reason: str) -> bool:
        override = self._instance_override("_set_system_locked")
        if override is not None:
            return bool(override(locked, reason=reason))
        if self.prefer_arouter_helpers:
            return bool(self.set_system_locked_fn(self.runtime, locked, reason=reason))
        self._ensure_biometric_runtime_attrs()
        with self.runtime._biometric_lock_state_lock:
            previous = bool(self.runtime._system_locked)
            self.runtime._system_locked = bool(locked)
        changed = previous != bool(locked)
        lock_client = getattr(self.runtime, "lock_overlay", None) or getattr(
            self.runtime, "overlay", None
        )
        try:
            if self.runtime._system_locked:
                if changed or not bool(getattr(self.runtime, "_lock_screen_visible", False)):
                    show = getattr(lock_client, "show_lock_screen", None)
                    if callable(show):
                        show(text=self._lock_screen_text())
                    self.runtime._lock_screen_visible = True
            else:
                if changed or bool(getattr(self.runtime, "_lock_screen_visible", False)):
                    hide = getattr(lock_client, "hide_lock_screen", None)
                    if callable(hide):
                        hide()
                    self.runtime._lock_screen_visible = False
        except Exception as exc:
            self._log(f"biometric lock overlay update failed ({reason}): {exc}")
        if changed:
            self._log(
                f"system lock state changed: locked={self.runtime._system_locked} reason={reason}"
            )
        return changed

    def _locked_denied_text(self) -> str:
        override = self._instance_override("_locked_denied_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.default_locked_denied_text())
        return (
            "現在ロック中です。"
            "システム、おはよう、システム、バイオメトリクス認証、"
            "またはシステム、パスワードで解除してください。"
        )

    def _reassert_lock_screen(self, *, reason: str) -> bool:
        override = self._instance_override("_reassert_lock_screen")
        if override is not None:
            return bool(override(reason=reason))
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            return bool(self.reassert_lock_screen_fn(self.runtime, reason=reason))
        if not self._biometric_lock_enabled() or not bool(
            getattr(self.runtime, "_system_locked", False)
        ):
            return False
        lock_client = getattr(self.runtime, "lock_overlay", None) or getattr(
            self.runtime, "overlay", None
        )
        try:
            show = getattr(lock_client, "show_lock_screen", None)
            if callable(show):
                show(text=self._lock_screen_text())
            self.runtime._lock_screen_visible = True
            self._log(f"system lock overlay reasserted: reason={reason}")
            return True
        except Exception as exc:
            self._log(f"biometric lock overlay reassert failed ({reason}): {exc}")
            return False

    def _log_auth_decision(self, *, cmd: Any, source: str, outcome: str, detail: str) -> None:
        override = self._instance_override("_log_auth_decision")
        if override is not None:
            override(cmd=cmd, source=source, outcome=outcome, detail=detail)
            return
        try:
            self._log(
                "command auth "
                + json.dumps(
                    {
                        "intent": cmd.intent,
                        "source": source,
                        "outcome": outcome,
                        "detail": detail,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass

    def _unlock_requires_live_voice_text(self) -> str:
        override = self._instance_override("_unlock_requires_live_voice_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.unlock_requires_live_voice_text_fn())
        return (
            "ロック解除には実際の音声入力が必要です。"
            "カメラの前で、システム、おはよう、またはシステム、バイオメトリクス認証と話してください。"
        )

    def _unlock_requires_speaker_auth_text(self) -> str:
        override = self._instance_override("_unlock_requires_speaker_auth_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.unlock_requires_speaker_auth_text_fn())
        return "声紋認証が利用できないため、ロックを解除できません。"

    def _unlock_requires_face_auth_text(self) -> str:
        override = self._instance_override("_unlock_requires_face_auth_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.unlock_requires_face_auth_text_fn())
        return "顔認証を確認できませんでした。カメラの前で、もう一度お試しください。"

    def _unlock_requires_password_text(self) -> str:
        override = self._instance_override("_unlock_requires_password_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.unlock_requires_password_text_fn())
        return "パスワード認証に失敗しました。もう一度お試しください。"

    def _biometric_unlock_success_text(self) -> str:
        override = self._instance_override("_biometric_unlock_success_text")
        if override is not None:
            return str(override())
        if self.prefer_arouter_helpers:
            return str(self.biometric_unlock_success_text_fn())
        return "バイオメトリクス認証に成功しました。おかえりなさい、ユイさま"

    def _speaker_auth_enabled(self) -> bool:
        override = self._instance_override("_speaker_auth_enabled")
        if override is not None:
            return bool(override())
        return bool(self.runtime._speaker_auth_enabled())

    def _verify_speaker_identity(
        self,
        wav_path: Path,
        *,
        cmd: Any,
        log_label: str,
    ) -> tuple[bool, str | None]:
        override = self._instance_override("_verify_speaker_identity")
        if override is not None:
            return cast(
                tuple[bool, str | None],
                override(wav_path, cmd=cmd, log_label=log_label),
            )
        return cast(
            tuple[bool, str | None],
            self.runtime._verify_speaker_identity(wav_path, cmd=cmd, log_label=log_label),
        )

    def _fetch_biometric_status_from_url(self, status_url: str) -> dict[str, Any] | None:
        override = self._instance_override("_fetch_biometric_status_from_url")
        if override is not None:
            result = override(status_url)
            return result if isinstance(result, dict) else None
        if self.prefer_arouter_helpers:
            result = self.run_biometric_status_url_fetch(
                status_url=status_url,
                debug=getattr(self.runtime, "debug", None),
                request_builder=self.request_builder,
                urlopen=self.urlopen,
                json_loads=self.json_loads,
            )
            return result if isinstance(result, dict) else None
        url = str(status_url or "").strip()
        if not url:
            return None
        try:
            req = self.request_builder(url, headers={"Accept": "application/json"})
            with self.urlopen(req, timeout=1.5) as resp:
                data = self.json_loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as exc:
            self._debug(f"god mode biometric status fetch failed: {exc}")
        return None

    def _get_biometric_status_client(self) -> Any | None:
        override = self._instance_override("_get_biometric_status_client")
        if override is not None:
            return override()
        client = getattr(self.runtime, "_biometric_status_client", None)
        args = self._args()
        status_url = str(
            getattr(args, "god_mode_status_url", "http://127.0.0.1:8765/biometric_status") or ""
        ).strip()
        logger = getattr(self.runtime, "debug", None)
        if not callable(logger):
            logger = None
        if self.prefer_arouter_helpers:
            client = self.run_biometric_status_client_get(
                current_client=client,
                client_available=self.asee_client_available,
                status_url=status_url,
                logger=logger,
                resolve_client=self.resolve_remote_status_client
                if self.asee_client_available
                else None,
            )
            self.runtime._biometric_status_client = client
            return client
        if client is not None:
            return client
        if not self.asee_client_available or not callable(self.resolve_remote_status_client):
            return None
        client = self.resolve_remote_status_client(
            current_client=client,
            status_url=status_url,
            timeout_sec=1.5,
            logger=logger,
        )
        self.runtime._biometric_status_client = client
        return client

    def _load_biometric_password_candidates(self) -> list[str]:
        override = self._instance_override("_load_biometric_password_candidates")
        if override is not None:
            return list(override())
        args = self._args()
        if self.prefer_arouter_helpers:
            candidates = self.run_biometric_password_candidate_load(
                cached_candidates=getattr(self.runtime, "_biometric_password_candidates_cache", None),
                args=args,
                debug=getattr(self.runtime, "debug", self._debug),
                log=getattr(self.runtime, "log", self._log),
                resolve_path=self.resolve_biometric_arg_path,
                load_candidates=self.load_password_candidates,
                encrypted_default_path=self.default_password_file,
                private_key_default_path=self.default_password_private_key,
            )
            self.runtime._biometric_password_candidates_cache = list(candidates)
            return list(candidates)
        cached = getattr(self.runtime, "_biometric_password_candidates_cache", None)
        if isinstance(cached, list):
            return list(cached)
        encrypted_path = Path(
            os.path.expanduser(
                str(getattr(args, "biometric_password_file", self.default_password_file))
            )
        )
        private_key_path = Path(
            os.path.expanduser(
                str(
                    getattr(
                        args,
                        "biometric_password_private_key",
                        self.default_password_private_key,
                    )
                )
            )
        )
        if not encrypted_path.exists():
            self._debug(f"biometric password file missing: {encrypted_path}")
            self.runtime._biometric_password_candidates_cache = []
            return []
        if not private_key_path.exists():
            self._debug(f"biometric private key missing: {private_key_path}")
            self.runtime._biometric_password_candidates_cache = []
            return []
        try:
            cipher_text = encrypted_path.read_text(encoding="utf-8").strip()
            cipher_bytes = base64.b64decode(cipher_text)
        except Exception as exc:
            self._log(f"biometric password load failed: {exc}")
            self.runtime._biometric_password_candidates_cache = []
            return []
        with tempfile.TemporaryDirectory(prefix="biometric-password-decrypt-") as tmp_dir:
            tmp_root = Path(tmp_dir)
            cipher_path = tmp_root / "cipher.bin"
            temp_key = tmp_root / "private_key"
            cipher_path.write_bytes(cipher_bytes)
            shutil.copyfile(private_key_path, temp_key)
            temp_key.chmod(0o600)
            try:
                subprocess.run(
                    [
                        "ssh-keygen",
                        "-p",
                        "-m",
                        "PEM",
                        "-N",
                        "",
                        "-P",
                        "",
                        "-f",
                        str(temp_key),
                        "-q",
                    ],
                    check=True,
                    capture_output=True,
                )
                cp = subprocess.run(
                    [
                        "openssl",
                        "pkeyutl",
                        "-decrypt",
                        "-inkey",
                        str(temp_key),
                        "-in",
                        str(cipher_path),
                        "-pkeyopt",
                        "rsa_padding_mode:oaep",
                        "-pkeyopt",
                        "rsa_oaep_md:sha256",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                err = (exc.stderr or exc.stdout or "").strip()
                self._log(f"biometric password decrypt failed: {err}")
                self.runtime._biometric_password_candidates_cache = []
                return []
        candidates = [line.strip() for line in (cp.stdout or "").splitlines() if line.strip()]
        self.runtime._biometric_password_candidates_cache = list(candidates)
        return list(candidates)

    def _verify_unlock_password(self, cmd: Any) -> bool:
        override = self._instance_override("_verify_unlock_password")
        if override is not None:
            return bool(override(cmd))
        if self.prefer_arouter_helpers:
            return bool(
                self.verify_unlock_password_fn(
                    provided_secret=getattr(cmd, "secret_text", ""),
                    candidates=self._load_biometric_password_candidates(),
                    normalize=self.normalize_transcript,
                )
            )
        provided = self.normalize_transcript(getattr(cmd, "secret_text", ""))
        if not provided:
            return False
        for candidate in self._load_biometric_password_candidates():
            if self.normalize_transcript(candidate) == provided:
                return True
        return False

    def _consume_biometric_unlock_signal(self) -> bool:
        override = self._instance_override("_consume_biometric_unlock_signal")
        if override is not None:
            return bool(override())
        args = self._args()
        if self.prefer_arouter_helpers:
            consumed, seen_mtime = self.run_biometric_signal_consume(
                args=args,
                attr_name="biometric_unlock_signal_file",
                default_path=self.default_unlock_signal_file,
                seen_mtime=float(
                    getattr(self.runtime, "_biometric_unlock_signal_seen_mtime", 0.0)
                ),
                resolve_path=self.resolve_biometric_arg_path,
                consume_signal=self.consume_signal_file,
            )
            if consumed:
                self.runtime._biometric_unlock_signal_seen_mtime = seen_mtime
            return bool(consumed)
        signal_path = Path(
            os.path.expanduser(
                str(getattr(args, "biometric_unlock_signal_file", self.default_unlock_signal_file))
            )
        )
        if not signal_path.exists():
            return False
        try:
            stat = signal_path.stat()
        except Exception:
            return False
        if float(stat.st_mtime) <= float(
            getattr(self.runtime, "_biometric_unlock_signal_seen_mtime", 0.0)
        ):
            return False
        self.runtime._biometric_unlock_signal_seen_mtime = float(stat.st_mtime)
        try:
            signal_path.unlink()
        except Exception:
            pass
        return True

    def _consume_biometric_lock_signal(self) -> bool:
        override = self._instance_override("_consume_biometric_lock_signal")
        if override is not None:
            return bool(override())
        args = self._args()
        if self.prefer_arouter_helpers:
            consumed, seen_mtime = self.run_biometric_signal_consume(
                args=args,
                attr_name="biometric_lock_signal_file",
                default_path=self.default_lock_signal_file,
                seen_mtime=float(
                    getattr(self.runtime, "_biometric_lock_signal_seen_mtime", 0.0)
                ),
                resolve_path=self.resolve_biometric_arg_path,
                consume_signal=self.consume_signal_file,
            )
            if consumed:
                self.runtime._biometric_lock_signal_seen_mtime = seen_mtime
            return bool(consumed)
        signal_path = Path(
            os.path.expanduser(
                str(getattr(args, "biometric_lock_signal_file", self.default_lock_signal_file))
            )
        )
        if not signal_path.exists():
            return False
        try:
            stat = signal_path.stat()
        except Exception:
            return False
        if float(stat.st_mtime) <= float(
            getattr(self.runtime, "_biometric_lock_signal_seen_mtime", 0.0)
        ):
            return False
        self.runtime._biometric_lock_signal_seen_mtime = float(stat.st_mtime)
        try:
            signal_path.unlink()
        except Exception:
            pass
        return True

    def _record_successful_command_activity(self) -> None:
        override = self._instance_override("_record_successful_command_activity")
        if override is not None:
            override()
            return
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            self.record_successful_command_activity_fn(self.runtime, now=self.now)
            return
        self.runtime._last_successful_command_at = self.now()

    def _fetch_god_mode_biometric_status(self) -> dict[str, Any] | None:
        override = self._instance_override("_fetch_god_mode_biometric_status")
        if override is not None:
            result = override()
            return result if isinstance(result, dict) else None
        args = self._args()
        logger = getattr(self.runtime, "debug", None)
        if not callable(logger):
            logger = None
        if self.prefer_arouter_helpers:
            client, status = self.run_biometric_status_runtime_fetch(
                current_client=getattr(self.runtime, "_biometric_status_client", None),
                args=args,
                logger=logger,
                client_available=self.asee_client_available,
                fetch_remote_status=self.fetch_remote_status
                if self.asee_client_available
                else None,
                fetch_status_from_url=self._fetch_biometric_status_from_url,
            )
            self.runtime._biometric_status_client = client
            return status if isinstance(status, dict) else None
        status_url = str(
            getattr(args, "god_mode_status_url", "http://127.0.0.1:8765/biometric_status") or ""
        ).strip()
        if self.asee_client_available and callable(self.fetch_remote_status):
            client, status = self.fetch_remote_status(
                current_client=getattr(self.runtime, "_biometric_status_client", None),
                status_url=status_url,
                logger=logger,
                timeout_sec=1.5,
            )
            self.runtime._biometric_status_client = client
            return status if isinstance(status, dict) else None
        return self._fetch_biometric_status_from_url(status_url)

    def _owner_face_absent_for_lock(self) -> bool:
        override = self._instance_override("_owner_face_absent_for_lock")
        if override is not None:
            return bool(override())
        args = self._args()
        threshold_sec = max(0, int(getattr(args, "biometric_face_absent_lock_sec", 120)))
        logger = getattr(self.runtime, "debug", None)
        if not callable(logger):
            logger = None
        if self.prefer_arouter_helpers:
            client, result = self.run_biometric_owner_face_absent_runtime_check(
                current_client=getattr(self.runtime, "_biometric_status_client", None),
                args=args,
                logger=logger,
                client_available=self.asee_client_available,
                resolve_client=self.resolve_remote_status_client
                if self.asee_client_available
                else None,
                fetch_remote_status=self.fetch_remote_status
                if self.asee_client_available
                else None,
                fetch_status_from_url=self._fetch_biometric_status_from_url,
                status_helper=self.owner_face_absent_from_status
                if self.asee_client_available
                else None,
            )
            self.runtime._biometric_status_client = client
            return bool(result)
        client = self._get_biometric_status_client()
        if client is not None:
            helper = getattr(client, "owner_face_absent_for_lock", None)
            if callable(helper):
                try:
                    return bool(helper(absent_lock_sec=threshold_sec))
                except Exception:
                    return False
        status = self._fetch_god_mode_biometric_status()
        if self.asee_client_available and callable(self.owner_face_absent_from_status):
            return bool(
                self.owner_face_absent_from_status(status, absent_lock_sec=threshold_sec)
            )
        if not isinstance(status, dict):
            return False
        if bool(status.get("ownerPresent")):
            return False
        age_ms = status.get("ownerSeenAgoMs")
        if age_ms is None:
            return True
        try:
            return int(age_ms) >= max(0, int(threshold_sec) * 1000)
        except Exception:
            return False

    def _owner_face_recent_for_unlock(self) -> bool:
        override = self._instance_override("_owner_face_recent_for_unlock")
        if override is not None:
            return bool(override())
        args = self._args()
        threshold_ms = max(0, int(getattr(args, "biometric_unlock_face_fresh_ms", 2000)))
        logger = getattr(self.runtime, "debug", None)
        if not callable(logger):
            logger = None
        if self.prefer_arouter_helpers:
            client, result = self.run_biometric_owner_face_recent_runtime_check(
                current_client=getattr(self.runtime, "_biometric_status_client", None),
                args=args,
                logger=logger,
                client_available=self.asee_client_available,
                resolve_client=self.resolve_remote_status_client
                if self.asee_client_available
                else None,
                fetch_remote_status=self.fetch_remote_status
                if self.asee_client_available
                else None,
                fetch_status_from_url=self._fetch_biometric_status_from_url,
                status_helper=self.owner_face_recent_from_status
                if self.asee_client_available
                else None,
            )
            self.runtime._biometric_status_client = client
            return bool(result)
        client = self._get_biometric_status_client()
        if client is not None:
            helper = getattr(client, "owner_face_recent_for_unlock", None)
            if callable(helper):
                try:
                    return bool(helper(fresh_ms=threshold_ms))
                except Exception:
                    return False
        status = self._fetch_god_mode_biometric_status()
        if self.asee_client_available and callable(self.owner_face_recent_from_status):
            return bool(self.owner_face_recent_from_status(status, fresh_ms=threshold_ms))
        if not isinstance(status, dict):
            return False
        if bool(status.get("ownerPresent")):
            return True
        age_ms = status.get("ownerSeenAgoMs")
        if age_ms is None:
            return False
        try:
            return int(age_ms) <= max(0, int(threshold_ms))
        except Exception:
            return False

    def _maybe_unlock_from_signal(self) -> bool:
        override = self._instance_override("_maybe_unlock_from_signal")
        if override is not None:
            return bool(override())
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            return bool(
                self.maybe_unlock_from_signal_fn(self, set_locked=self._set_locked_callback)
            )
        if not self._biometric_lock_enabled() or not bool(getattr(self.runtime, "_system_locked", False)):
            return False
        if not self._consume_biometric_unlock_signal():
            return False
        self._log("biometric unlock signal consumed")
        self._set_system_locked(False, reason="unlock:overlay_password")
        self._record_successful_command_activity()
        return True

    def _maybe_lock_from_signal(self) -> bool:
        override = self._instance_override("_maybe_lock_from_signal")
        if override is not None:
            return bool(override())
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            return bool(
                self.maybe_lock_from_signal_fn(self, set_locked=self._set_locked_callback)
            )
        if not self._biometric_lock_enabled() or bool(getattr(self.runtime, "_system_locked", False)):
            return False
        if not self._consume_biometric_lock_signal():
            return False
        self._log("biometric lock signal consumed")
        return bool(self._set_system_locked(True, reason="manual_signal"))

    def _maybe_auto_lock(self) -> None:
        override = self._instance_override("_maybe_auto_lock")
        if override is not None:
            override()
            return
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            self.maybe_auto_lock_fn(self, set_locked=self._set_locked_callback)
            return
        if not self._biometric_lock_enabled() or bool(self.runtime._system_locked):
            return
        idle_sec = self.now() - float(
            getattr(self.runtime, "_last_successful_command_at", self.now())
        )
        idle_threshold = max(
            0,
            int(getattr(self._args(), "biometric_command_idle_lock_sec", 900)),
        )
        if idle_sec < idle_threshold:
            return
        if not self._owner_face_absent_for_lock():
            return
        self._set_system_locked(True, reason="idle_timeout")

    def _authorize_command(
        self,
        cmd: Any,
        *,
        wav_path: Path | None,
        source: str,
        log_label: str,
    ) -> tuple[bool, str | None]:
        override = self._instance_override("_authorize_command")
        if override is not None:
            return cast(
                tuple[bool, str | None],
                override(cmd, wav_path=wav_path, source=source, log_label=log_label),
            )
        return cast(
            tuple[bool, str | None],
            self.authorize_command_fn(
                self,
                cmd,
                wav_path=wav_path,
                source=source,
                log_label=log_label,
            ),
        )

    def _biometric_poll_interval_sec(self) -> float:
        override = self._instance_override("_biometric_poll_interval_sec")
        if override is not None:
            return float(override())
        if self.prefer_arouter_helpers:
            return float(
                self.resolve_biometric_poll_interval_fn(
                    getattr(self._args(), "biometric_poll_sec", 1.0)
                )
            )
        try:
            val = float(getattr(self._args(), "biometric_poll_sec", 1.0))
        except Exception:
            val = 1.0
        return max(0.2, val)

    def _biometric_lock_poller(self) -> None:
        override = self._instance_override("_biometric_lock_poller")
        if override is not None:
            override()
            return
        self._ensure_biometric_runtime_attrs()
        ev = self.runtime._biometric_poll_stop_event
        interval = self._biometric_poll_interval_sec()
        if self.prefer_arouter_helpers:
            self.run_biometric_poller_loop_fn(
                stop_requested=lambda: bool(getattr(self.runtime, "stop_requested", False)),
                stop_event=ev,
                interval_sec=interval,
                run_iteration=lambda: self.run_biometric_poll_iteration_fn(
                    maybe_unlock_from_signal=self.runtime._maybe_unlock_from_signal,
                    maybe_lock_from_signal=self.runtime._maybe_lock_from_signal,
                    maybe_auto_lock=self.runtime._maybe_auto_lock,
                    debug=getattr(self.runtime, "debug", self._debug),
                ),
            )
            return
        while not bool(getattr(self.runtime, "stop_requested", False)) and not ev.is_set():
            try:
                self._maybe_unlock_from_signal()
                self._maybe_lock_from_signal()
                self._maybe_auto_lock()
            except Exception as exc:
                self._debug(f"biometric poll warning: {exc}")
            ev.wait(interval)

    def _start_biometric_lock_poller(self) -> None:
        override = self._instance_override("_start_biometric_lock_poller")
        if override is not None:
            override()
            return
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            self.runtime._biometric_poll_thread = self.start_biometric_poller_fn(
                enabled=self._biometric_lock_enabled(),
                current_thread=getattr(self.runtime, "_biometric_poll_thread", None),
                stop_event=self.runtime._biometric_poll_stop_event,
                thread_factory=lambda: self.thread_factory(
                    target=self._biometric_lock_poller,
                    name="biometric-lock-poller",
                    daemon=True,
                ),
            )
            return
        if not self._biometric_lock_enabled():
            return
        th = getattr(self.runtime, "_biometric_poll_thread", None)
        if th and th.is_alive():
            return
        self.runtime._biometric_poll_stop_event.clear()
        self.runtime._biometric_poll_thread = self.thread_factory(
            target=self._biometric_lock_poller,
            name="biometric-lock-poller",
            daemon=True,
        )
        self.runtime._biometric_poll_thread.start()

    def _stop_biometric_lock_poller(self) -> None:
        override = self._instance_override("_stop_biometric_lock_poller")
        if override is not None:
            override()
            return
        self._ensure_biometric_runtime_attrs()
        if self.prefer_arouter_helpers:
            self.stop_biometric_poller_fn(
                stop_event=self.runtime._biometric_poll_stop_event,
                current_thread=getattr(self.runtime, "_biometric_poll_thread", None),
            )
            return
        self.runtime._biometric_poll_stop_event.set()
        th = getattr(self.runtime, "_biometric_poll_thread", None)
        if th and th.is_alive():
            th.join(timeout=1.5)
