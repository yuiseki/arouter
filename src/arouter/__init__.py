from .authorization import authorize_command
from .biometric_admin import (
    encrypt_biometric_password_payload,
    request_biometric_lock_payload,
)
from .biometric_bootstrap import ensure_biometric_runtime_attrs
from .biometric_password import (
    encrypt_password_file,
    load_password_candidates,
    read_password_secret_lines,
    verify_unlock_password,
)
from .biometric_paths import resolve_biometric_arg_path
from .biometric_poller import (
    resolve_biometric_poll_interval,
    run_biometric_poll_iteration,
    run_biometric_poller_loop,
    start_biometric_poller,
    stop_biometric_poller,
)
from .biometric_runtime import (
    default_lock_screen_text,
    default_locked_denied_text,
    maybe_auto_lock,
    maybe_lock_from_signal,
    maybe_unlock_from_signal,
    reassert_lock_screen,
    set_system_locked,
)
from .biometric_signal import (
    consume_signal_file,
    current_signal_mtime,
    seed_signal_seen_mtime,
    write_signal_file,
)
from .errors import report_segment_error
from .execution import command_has_system_prefix, execute_command, execute_news_command
from .flow import run_authorized_command_flow
from .live_cam_layout import (
    build_live_cam_layout_targets_compact,
    build_live_cam_layout_targets_full,
    compact_live_cam_region_from_screen_and_work_area,
)
from .load_check import (
    build_load_check_wmctrl_commands,
    find_konsole_rows_for_tmux_client_pids,
    is_vacuumtube_quadrant_mode_for_load_check,
    load_check_bottom_left_geom,
    parse_konsole_window_rows,
    parse_tmux_client_pids,
    pid_ancestor_chain,
    prepare_load_check_konsole_placement,
    run_system_load_check_flow,
    wait_for_new_window_row,
)
from .models import VoiceCommand
from .overlay import build_overlay_ipc_line, compose_overlay_notify_text, trim_notify_text
from .parser import extract_password_unlock_secret, normalize_transcript, parse_command
from .policy import (
    good_night_voice_text,
    post_action_voice_text,
    should_ack_before_action,
    should_wait_ack_before_action,
)
from .reactions import detect_non_command_reaction
from .resolution import SegmentTranscriptResolution, resolve_segment_transcript
from .router import (
    CommandExecutionPayload,
    TextCommandRouter,
    contextualize_command_with_vacuumtube_state,
)
from .segment import process_pcm_segment, process_transcribed_segment
from .storage import handle_authorization_denied, store_authfail_wav, store_authorized_wav
from .window_actions import (
    build_window_activate_command,
    build_window_close_command,
    build_window_fullscreen_command,
    build_window_key_command,
    build_window_minimize_command,
    build_window_move_resize_command,
)
from .window_rows import (
    chromium_window_ids_from_wmctrl_lines,
    detect_new_window_id,
    find_window_geometry_from_wmctrl_lines,
    find_window_id_by_pid_and_title,
    find_window_id_by_title,
    looks_like_weather_chromium_title,
    select_weather_candidate_window_ids,
    wait_for_window_id,
    window_title_from_wmctrl_lines,
)

__all__ = [
    "CommandExecutionPayload",
    "TextCommandRouter",
    "VoiceCommand",
    "authorize_command",
    "encrypt_biometric_password_payload",
    "ensure_biometric_runtime_attrs",
    "build_overlay_ipc_line",
    "build_live_cam_layout_targets_compact",
    "build_live_cam_layout_targets_full",
    "build_load_check_wmctrl_commands",
    "build_window_activate_command",
    "build_window_close_command",
    "build_window_fullscreen_command",
    "build_window_key_command",
    "build_window_move_resize_command",
    "build_window_minimize_command",
    "command_has_system_prefix",
    "chromium_window_ids_from_wmctrl_lines",
    "compact_live_cam_region_from_screen_and_work_area",
    "consume_signal_file",
    "detect_new_window_id",
    "compose_overlay_notify_text",
    "current_signal_mtime",
    "default_lock_screen_text",
    "default_locked_denied_text",
    "encrypt_password_file",
    "resolve_biometric_arg_path",
    "contextualize_command_with_vacuumtube_state",
    "detect_non_command_reaction",
    "execute_command",
    "execute_news_command",
    "extract_password_unlock_secret",
    "find_window_geometry_from_wmctrl_lines",
    "find_window_id_by_pid_and_title",
    "find_window_id_by_title",
    "good_night_voice_text",
    "handle_authorization_denied",
    "find_konsole_rows_for_tmux_client_pids",
    "is_vacuumtube_quadrant_mode_for_load_check",
    "load_password_candidates",
    "load_check_bottom_left_geom",
    "maybe_auto_lock",
    "maybe_lock_from_signal",
    "maybe_unlock_from_signal",
    "normalize_transcript",
    "parse_command",
    "post_action_voice_text",
    "process_pcm_segment",
    "process_transcribed_segment",
    "parse_konsole_window_rows",
    "parse_tmux_client_pids",
    "pid_ancestor_chain",
    "prepare_load_check_konsole_placement",
    "read_password_secret_lines",
    "reassert_lock_screen",
    "request_biometric_lock_payload",
    "resolve_biometric_poll_interval",
    "report_segment_error",
    "run_biometric_poll_iteration",
    "run_biometric_poller_loop",
    "run_authorized_command_flow",
    "resolve_segment_transcript",
    "SegmentTranscriptResolution",
    "looks_like_weather_chromium_title",
    "select_weather_candidate_window_ids",
    "should_ack_before_action",
    "should_wait_ack_before_action",
    "start_biometric_poller",
    "store_authfail_wav",
    "store_authorized_wav",
    "stop_biometric_poller",
    "run_system_load_check_flow",
    "set_system_locked",
    "seed_signal_seen_mtime",
    "wait_for_window_id",
    "wait_for_new_window_row",
    "window_title_from_wmctrl_lines",
    "trim_notify_text",
    "verify_unlock_password",
    "write_signal_file",
]
