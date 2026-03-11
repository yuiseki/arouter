#!/usr/bin/env python3
"""Voice command loop experiment: mic listen + whisper-server + VOICEVOX + VacuumTube control.

This file also supports deterministic one-shot CLI execution via
`--run-command "..."`, which parses and executes a single command text, prints
JSON, and exits without entering the microphone loop. It can also request a
manual biometric lock via `--request-biometric-lock`.

Current scope intentionally focuses on a few safe commands:
- 音楽を再生してください / BGM再生して
- 音楽を停止してください / BGM止めて
- ニュースライブを再生して / 朝のニュース / 夕方のニュース

Latency improvements vs manual polling flow:
- command handling happens inside the microphone listener process (no tmux polling)
- shorter default end-silence for VAD
- VOICEVOX acknowledgement playback overlaps with command execution
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websocket  # type: ignore[import-untyped]

_WORKSPACES_ROOT = Path(
    os.environ.get("YUICLAW_WORKSPACES_ROOT", str(Path(__file__).resolve().parents[3]))
)
_AHEAR_PY_SRC = _WORKSPACES_ROOT / "repos" / "ahear" / "python" / "src"
_AROUTER_SRC = _WORKSPACES_ROOT / "repos" / "arouter" / "src"
_ACAPTION_PY_SRC = _WORKSPACES_ROOT / "repos" / "acaption" / "python" / "src"
_ASEC_PY_SRC = _WORKSPACES_ROOT / "repos" / "asec" / "python" / "src"
_ASEE_PY_SRC = _WORKSPACES_ROOT / "repos" / "asee" / "python" / "src"
_ASAY_PY_SRC = _WORKSPACES_ROOT / "repos" / "asay" / "python" / "src"
_DEFAULT_SPEAKER_MASTER = (
    _WORKSPACES_ROOT
    / "repos"
    / "ahear"
    / "python"
    / "src"
    / "ahear"
    / "models"
    / "master_voiceprint.npy"
)
if _AHEAR_PY_SRC.is_dir():
    ahear_src_str = str(_AHEAR_PY_SRC)
    if ahear_src_str not in sys.path:
        sys.path.insert(0, ahear_src_str)
if _AROUTER_SRC.is_dir():
    arouter_src_str = str(_AROUTER_SRC)
    if arouter_src_str not in sys.path:
        sys.path.insert(0, arouter_src_str)
for _extra_src in (_ACAPTION_PY_SRC, _ASEC_PY_SRC, _ASEE_PY_SRC, _ASAY_PY_SRC):
    if _extra_src.is_dir():
        extra_src_str = str(_extra_src)
        if extra_src_str not in sys.path:
            sys.path.insert(0, extra_src_str)

try:
    from arouter import (
        VoiceCommand as ArouterVoiceCommand,
        authorize_command as arouter_authorize_command,
        build_live_cam_runtime_url_entry as arouter_build_live_cam_runtime_url_entry,
        build_kwin_script_command_plan as arouter_build_kwin_script_command_plan,
        build_live_cam_layout_script as arouter_build_live_cam_layout_script,
        build_live_cam_layout_targets_compact as arouter_build_live_cam_layout_targets_compact,
        build_live_cam_layout_targets_full as arouter_build_live_cam_layout_targets_full,
        build_live_cam_minimize_script as arouter_build_live_cam_minimize_script,
        build_x11_env as arouter_build_x11_env,
        launch_chromium_new_window as arouter_launch_chromium_new_window,
        probe_x11_display_host_runtime as arouter_probe_x11_display_host_runtime,
        resolve_x11_display_host_runtime as arouter_resolve_x11_display_host_runtime,
        run_weather_pages_closed as arouter_run_weather_pages_closed,
        run_weather_pages_tiled as arouter_run_weather_pages_tiled,
        run_system_normal_mode_host_runtime as arouter_run_system_normal_mode_host_runtime,
        run_system_webcam_mode_host_runtime as arouter_run_system_webcam_mode_host_runtime,
        run_tmp_main_layout_host_runtime as arouter_run_tmp_main_layout_host_runtime,
        build_tmux_has_session_command as arouter_build_tmux_has_session_command,
        build_tmux_kill_session_command as arouter_build_tmux_kill_session_command,
        build_vacuumtube_tmux_start_command as arouter_build_vacuumtube_tmux_start_command,
        build_window_frame_geometry_script as arouter_build_window_frame_geometry_script,
        build_window_close_command as arouter_build_window_close_command,
        build_window_fullscreen_command as arouter_build_window_fullscreen_command,
        build_window_key_command as arouter_build_window_key_command,
        build_wmctrl_list_command as arouter_build_wmctrl_list_command,
        build_xprop_wm_state_command as arouter_build_xprop_wm_state_command,
        build_window_move_resize_command as arouter_build_window_move_resize_command,
        build_window_minimize_command as arouter_build_window_minimize_command,
        chromium_window_ids_from_wmctrl_lines as arouter_chromium_window_ids_from_wmctrl_lines,
        compact_live_cam_region_from_screen_and_work_area as arouter_compact_live_cam_region_from_screen_and_work_area,
        consume_signal_file as arouter_consume_signal_file,
        compose_overlay_notify_text as arouter_compose_overlay_notify_text,
        contextualize_command_with_vacuumtube_state_host_runtime as arouter_contextualize_command_with_vacuumtube_state_host_runtime,
        execute_text_command_host_runtime as arouter_execute_text_command_host_runtime,
        run_detect_new_window_id_host_runtime as arouter_run_detect_new_window_id_host_runtime,
        BiometricRuntimeAdapter as ExtractedBiometricRuntimeAdapter,
        DesktopNotifier as ExtractedDesktopNotifier,
        ensure_biometric_runtime_attrs as arouter_ensure_biometric_runtime_attrs,
        seed_signal_seen_mtime as arouter_seed_signal_seen_mtime,
        detect_non_command_reaction as arouter_detect_non_command_reaction,
        encrypt_password_file as arouter_encrypt_password_file,
        execute_command as arouter_execute_command,
        extract_password_unlock_secret as arouter_extract_password_unlock_secret,
        build_live_cam_page_brief as arouter_build_live_cam_page_brief,
        run_live_cam_page_brief_host_runtime_flow as arouter_run_live_cam_page_brief_host_runtime_flow,
        run_live_cam_page_snapshot_query as arouter_run_live_cam_page_snapshot_query,
        run_live_cam_page_snapshot_via_websocket as arouter_run_live_cam_page_snapshot_via_websocket,
        collect_live_cam_runtime_urls as arouter_collect_live_cam_runtime_urls,
        select_live_cam_page_target as arouter_select_live_cam_page_target,
        select_live_cam_page_url as arouter_select_live_cam_page_url,
        select_vacuumtube_page_target as arouter_select_vacuumtube_page_target,
        select_vacuumtube_websocket_url as arouter_select_vacuumtube_websocket_url,
        vacuumtube_is_home_browse_state as arouter_vacuumtube_is_home_browse_state,
        vacuumtube_is_watch_state as arouter_vacuumtube_is_watch_state,
        vacuumtube_needs_hard_reload_home as arouter_vacuumtube_needs_hard_reload_home,
        vacuumtube_video_current_time as arouter_vacuumtube_video_current_time,
        vacuumtube_video_playing as arouter_vacuumtube_video_playing,
        build_vacuumtube_context_base as arouter_build_vacuumtube_context_base,
        finalize_vacuumtube_context as arouter_finalize_vacuumtube_context,
        find_window_geometry_from_wmctrl_lines as arouter_find_window_geometry_from_wmctrl_lines,
        find_window_id_by_pid_and_title as arouter_find_window_id_by_pid_and_title,
        find_window_id_by_title as arouter_find_window_id_by_title,
        find_konsole_rows_for_tmux_session_host_runtime as arouter_find_konsole_rows_for_tmux_session_host_runtime,
        build_live_cam_hide_response as arouter_build_live_cam_hide_response,
        build_live_cam_minimize_response as arouter_build_live_cam_minimize_response,
        build_live_cam_open_result as arouter_build_live_cam_open_result,
        build_live_cam_reopen_result as arouter_build_live_cam_reopen_result,
        build_live_cam_start_command as arouter_build_live_cam_start_command,
        build_live_cam_started_result as arouter_build_live_cam_started_result,
        collect_live_cam_skip_pids as arouter_collect_live_cam_skip_pids,
        collect_window_ids_for_pids as arouter_collect_window_ids_for_pids,
        default_lock_screen_text as arouter_default_lock_screen_text,
        default_locked_denied_text as arouter_default_locked_denied_text,
        biometric_lock_enabled as arouter_biometric_lock_enabled,
        biometric_unlock_success_text as arouter_biometric_unlock_success_text,
        build_vacuumtube_context_error as arouter_build_vacuumtube_context_error,
        good_night_voice_text as arouter_good_night_voice_text,
        is_vacuumtube_quadrant_mode_for_load_check as arouter_is_vacuumtube_quadrant_mode_for_load_check,
        load_password_candidates as arouter_load_password_candidates,
        load_check_bottom_left_geom as arouter_load_check_bottom_left_geom,
        looks_like_weather_chromium_title as arouter_looks_like_weather_chromium_title,
        merge_live_cam_page_snapshot as arouter_merge_live_cam_page_snapshot,
        maybe_auto_lock as arouter_maybe_auto_lock,
        maybe_lock_from_signal as arouter_maybe_lock_from_signal,
        maybe_unlock_from_signal as arouter_maybe_unlock_from_signal,
        is_recoverable_vacuumtube_error as arouter_is_recoverable_vacuumtube_error,
        run_live_cam_payload_selection_host_runtime_flow as arouter_run_live_cam_payload_selection_host_runtime_flow,
        normalize_transcript as arouter_normalize_transcript,
        parse_key_value_stdout as arouter_parse_key_value_stdout,
        parse_konsole_window_rows as arouter_parse_konsole_window_rows,
        parse_command as arouter_parse_command,
        parse_desktop_size_from_wmctrl_output as arouter_parse_desktop_size_from_wmctrl_output,
        parse_screen_size_from_xrandr_output as arouter_parse_screen_size_from_xrandr_output,
        parse_tmux_client_pids as arouter_parse_tmux_client_pids,
        parse_work_area_from_wmctrl_output as arouter_parse_work_area_from_wmctrl_output,
        pid_ancestor_chain as arouter_pid_ancestor_chain,
        page_matches_live_camera_spec as arouter_page_matches_live_camera_spec,
        post_action_voice_text as arouter_post_action_voice_text,
        process_pcm_segment as arouter_process_pcm_segment,
        require_cdp_target_list as arouter_require_cdp_target_list,
        run_cdp_target_list_http_query as arouter_run_cdp_target_list_http_query,
        run_cdp_target_list_query as arouter_run_cdp_target_list_query,
        read_active_window_id as arouter_read_active_window_id,
        read_window_fullscreen_state as arouter_read_window_fullscreen_state,
        read_password_secret_lines as arouter_read_password_secret_lines,
        reassert_lock_screen as arouter_reassert_lock_screen,
        resolve_biometric_arg_path as arouter_resolve_biometric_arg_path,
        resolve_biometric_poll_interval as arouter_resolve_biometric_poll_interval,
        resolve_x11_display as arouter_resolve_x11_display,
        report_segment_error as arouter_report_segment_error,
        record_successful_command_activity as arouter_record_successful_command_activity,
        resolve_live_cam_action_state as arouter_resolve_live_cam_action_state,
        run_live_cam_existing_windowed_pids_host_runtime_query as arouter_run_live_cam_existing_windowed_pids_host_runtime_query,
        resolve_vacuumtube_context_cache_host_runtime as arouter_resolve_vacuumtube_context_cache_host_runtime,
        resolve_vacuumtube_context_poll_interval as arouter_resolve_vacuumtube_context_poll_interval,
        run_live_cam_hide_host_runtime_flow as arouter_run_live_cam_hide_host_runtime_flow,
        run_live_cam_parallel as arouter_run_live_cam_parallel,
        run_live_cam_close_windows as arouter_run_live_cam_close_windows,
        run_live_cam_close_windows_host_runtime_flow as arouter_run_live_cam_close_windows_host_runtime_flow,
        run_live_cam_layout_host_runtime_flow as arouter_run_live_cam_layout_host_runtime_flow,
        run_live_cam_reopen_specs_flow as arouter_run_live_cam_reopen_specs_flow,
        run_live_cam_minimize_host_runtime_flow as arouter_run_live_cam_minimize_host_runtime_flow,
        run_live_cam_layout_script as arouter_run_live_cam_layout_script,
        run_live_cam_minimize_windows as arouter_run_live_cam_minimize_windows,
        run_live_cam_minimize_windows_host_runtime_flow as arouter_run_live_cam_minimize_windows_host_runtime_flow,
        run_live_cam_open_flow as arouter_run_live_cam_open_flow,
        run_live_cam_open_instances_host_runtime_flow as arouter_run_live_cam_open_instances_host_runtime_flow,
        run_live_cam_runtime_state_cdp_runtime as arouter_run_live_cam_runtime_state_cdp_runtime,
        run_live_cam_runtime_state_host_runtime_query as arouter_run_live_cam_runtime_state_host_runtime_query,
        run_live_cam_page_brief_cdp_runtime as arouter_run_live_cam_page_brief_cdp_runtime,
        run_live_cam_stuck_specs_host_runtime_query as arouter_run_live_cam_stuck_specs_host_runtime_query,
        run_live_cam_raise_windows as arouter_run_live_cam_raise_windows,
        run_live_cam_raise_windows_host_runtime_flow as arouter_run_live_cam_raise_windows_host_runtime_flow,
        run_live_cam_start_flow as arouter_run_live_cam_start_flow,
        run_live_cam_start_instances_host_runtime_flow as arouter_run_live_cam_start_instances_host_runtime_flow,
        run_live_cam_start_script_flow as arouter_run_live_cam_start_script_flow,
        run_live_cam_start_script_host_runtime_flow as arouter_run_live_cam_start_script_host_runtime_flow,
        run_live_cam_window_action_flow as arouter_run_live_cam_window_action_flow,
        run_listen_pid_host_runtime_query as arouter_run_listen_pid_host_runtime_query,
        run_minimize_other_windows_host_runtime_flow as arouter_run_minimize_other_windows_host_runtime_flow,
        run_desktop_size_host_runtime_query as arouter_run_desktop_size_host_runtime_query,
        run_desktop_size_query as arouter_run_desktop_size_query,
        run_active_window_id_host_runtime_query as arouter_run_active_window_id_host_runtime_query,
        run_active_window_id_query as arouter_run_active_window_id_query,
        run_kwin_shortcut as arouter_run_kwin_shortcut,
        run_kwin_shortcut_host_runtime as arouter_run_kwin_shortcut_host_runtime,
        run_launch_chromium_new_window_host_runtime as arouter_run_launch_chromium_new_window_host_runtime,
        run_live_cam_layout_host_runtime as arouter_run_live_cam_layout_host_runtime,
        run_live_cam_layout_runtime as arouter_run_live_cam_layout_runtime,
        run_load_check_konsole_placement_host_runtime as arouter_run_load_check_konsole_placement_host_runtime,
        run_screen_size_host_runtime_query as arouter_run_screen_size_host_runtime_query,
        run_screen_size_query as arouter_run_screen_size_query,
        run_tmux_client_pid_query_host_runtime as arouter_run_tmux_client_pid_query_host_runtime,
        run_tmux_has_session_host_runtime as arouter_run_tmux_has_session_host_runtime,
        run_tmux_has_session_query as arouter_run_tmux_has_session_query,
        run_window_frame_geometry_runtime as arouter_run_window_frame_geometry_runtime,
        run_window_frame_geometry_host_runtime as arouter_run_window_frame_geometry_host_runtime,
        run_vacuumtube_window_id_query as arouter_run_vacuumtube_window_id_query,
        run_vacuumtube_window_id_host_runtime_query as arouter_run_vacuumtube_window_id_host_runtime_query,
        run_window_geometry_query as arouter_run_window_geometry_query,
        run_window_geometry_host_runtime_query as arouter_run_window_geometry_host_runtime_query,
        run_window_id_by_pid_title_host_runtime_query as arouter_run_window_id_by_pid_title_host_runtime_query,
        run_window_id_query_by_pid_title as arouter_run_window_id_query_by_pid_title,
        run_window_title_query as arouter_run_window_title_query,
        run_window_title_host_runtime_query as arouter_run_window_title_host_runtime_query,
        run_window_rows_for_pids_host_runtime_query as arouter_run_window_rows_for_pids_host_runtime_query,
        run_window_rows_query_for_pids as arouter_run_window_rows_query_for_pids,
        run_window_row_by_listen_port_host_runtime as arouter_run_window_row_by_listen_port_host_runtime,
        read_window_fullscreen_state_host_runtime as arouter_read_window_fullscreen_state_host_runtime,
        run_work_area_host_runtime_query as arouter_run_work_area_host_runtime_query,
        run_work_area_query as arouter_run_work_area_query,
        run_wmctrl_list_host_runtime_query as arouter_run_wmctrl_list_host_runtime_query,
        run_wmctrl_list_query as arouter_run_wmctrl_list_query,
        run_system_load_check_host_runtime as arouter_run_system_load_check_host_runtime,
        run_system_load_check_monitor_open_host_runtime as arouter_run_system_load_check_monitor_open_host_runtime,
        run_system_status_report_host_runtime as arouter_run_system_status_report_host_runtime,
        run_system_weather_mode_host_runtime as arouter_run_system_weather_mode_host_runtime,
        run_system_world_situation_mode_host_runtime as arouter_run_system_world_situation_mode_host_runtime,
        run_show_weather_pages_today_host_runtime as arouter_run_show_weather_pages_today_host_runtime,
        execute_news_command as arouter_execute_news_command,
        run_god_mode_layout_host_runtime as arouter_run_god_mode_layout_host_runtime,
        run_good_morning_host_runtime as arouter_run_good_morning_host_runtime,
        run_good_night_host_runtime as arouter_run_good_night_host_runtime,
        run_system_live_camera_show_host_runtime as arouter_run_system_live_camera_show_host_runtime,
        run_system_live_camera_compact_host_runtime as arouter_run_system_live_camera_compact_host_runtime,
        run_system_live_camera_hide_host_runtime as arouter_run_system_live_camera_hide_host_runtime,
        run_system_street_camera_mode_host_runtime as arouter_run_system_street_camera_mode_host_runtime,
        run_biometric_poll_iteration as arouter_run_biometric_poll_iteration,
        run_biometric_poller_loop as arouter_run_biometric_poller_loop,
        run_biometric_owner_face_absent_check as arouter_run_biometric_owner_face_absent_check,
        run_biometric_owner_face_absent_runtime_check as arouter_run_biometric_owner_face_absent_runtime_check,
        run_biometric_owner_face_recent_check as arouter_run_biometric_owner_face_recent_check,
        run_biometric_owner_face_recent_runtime_check as arouter_run_biometric_owner_face_recent_runtime_check,
        run_biometric_password_candidate_load as arouter_run_biometric_password_candidate_load,
        run_biometric_signal_consume as arouter_run_biometric_signal_consume,
        run_biometric_status_client_get as arouter_run_biometric_status_client_get,
        run_biometric_status_fetch as arouter_run_biometric_status_fetch,
        run_biometric_status_runtime_fetch as arouter_run_biometric_status_runtime_fetch,
        run_biometric_status_url_fetch as arouter_run_biometric_status_url_fetch,
        run_speaker_auth_enabled as arouter_run_speaker_auth_enabled,
        run_speaker_auth_initialization as arouter_run_speaker_auth_initialization,
        run_speaker_identity_verification as arouter_run_speaker_identity_verification,
        run_vacuumtube_cdp_client as arouter_run_vacuumtube_cdp_client,
        run_vacuumtube_page_cdp_host_runtime as arouter_run_vacuumtube_page_cdp_host_runtime,
        run_vacuumtube_page_cdp_runtime as arouter_run_vacuumtube_page_cdp_runtime,
        run_vacuumtube_page_target_host_runtime_query as arouter_run_vacuumtube_page_target_host_runtime_query,
        run_vacuumtube_page_target_query as arouter_run_vacuumtube_page_target_query,
        run_vacuumtube_target_list_host_runtime_query as arouter_run_vacuumtube_target_list_host_runtime_query,
        run_vacuumtube_context_poller_loop_host_runtime as arouter_run_vacuumtube_context_poller_loop_host_runtime,
        run_vacuumtube_ensure_home as arouter_run_vacuumtube_ensure_home,
        run_vacuumtube_ensure_home_host_runtime as arouter_run_vacuumtube_ensure_home_host_runtime,
        run_vacuumtube_hide_overlay_host_runtime as arouter_run_vacuumtube_hide_overlay_host_runtime,
        run_vacuumtube_state_query as arouter_run_vacuumtube_state_query,
        run_vacuumtube_state_host_runtime_query as arouter_run_vacuumtube_state_host_runtime_query,
        ensure_vacuumtube_started_and_positioned_host_runtime as arouter_ensure_vacuumtube_started_and_positioned_host_runtime,
        ensure_vacuumtube_runtime_ready as arouter_ensure_vacuumtube_runtime_ready,
        run_vacuumtube_recover_from_unresponsive_host_runtime as arouter_run_vacuumtube_recover_from_unresponsive_host_runtime,
        restart_vacuumtube_tmux_session as arouter_restart_vacuumtube_tmux_session,
        run_vacuumtube_runtime_ready_host_runtime as arouter_run_vacuumtube_runtime_ready_host_runtime,
        run_vacuumtube_tmux_restart_host_runtime as arouter_run_vacuumtube_tmux_restart_host_runtime,
        run_vacuumtube_tmux_start_host_runtime as arouter_run_vacuumtube_tmux_start_host_runtime,
        run_vacuumtube_action_with_recovery as arouter_run_vacuumtube_action_with_recovery,
        run_encrypt_biometric_password_stdin_cli_flow as arouter_run_encrypt_biometric_password_stdin_cli_flow,
        run_request_biometric_lock_cli_flow as arouter_run_request_biometric_lock_cli_flow,
        run_vacuumtube_fullscreen_host_runtime as arouter_run_vacuumtube_fullscreen_host_runtime,
        run_vacuumtube_play_bgm_host_runtime as arouter_run_vacuumtube_play_bgm_host_runtime,
        run_vacuumtube_click_tile_center_host_runtime as arouter_run_vacuumtube_click_tile_center_host_runtime,
        run_vacuumtube_confirm_watch_playback as arouter_run_vacuumtube_confirm_watch_playback,
        run_vacuumtube_confirm_watch_playback_host_runtime as arouter_run_vacuumtube_confirm_watch_playback_host_runtime,
        run_vacuumtube_context_host_runtime_flow as arouter_run_vacuumtube_context_host_runtime_flow,
        run_vacuumtube_context_runtime_flow as arouter_run_vacuumtube_context_runtime_flow,
        run_vacuumtube_dom_click_tile_host_runtime as arouter_run_vacuumtube_dom_click_tile_host_runtime,
        run_vacuumtube_enumerate_tiles_host_runtime as arouter_run_vacuumtube_enumerate_tiles_host_runtime,
        run_vacuumtube_good_night_pause_host_runtime as arouter_run_vacuumtube_good_night_pause_host_runtime,
        run_vacuumtube_go_home_host_runtime as arouter_run_vacuumtube_go_home_host_runtime,
        run_vacuumtube_hard_reload_home_host_runtime as arouter_run_vacuumtube_hard_reload_home_host_runtime,
        run_vacuumtube_minimize_host_runtime as arouter_run_vacuumtube_minimize_host_runtime,
        run_vacuumtube_open_from_home_host_runtime as arouter_run_vacuumtube_open_from_home_host_runtime,
        run_vacuumtube_quadrant_host_runtime as arouter_run_vacuumtube_quadrant_host_runtime,
        run_vacuumtube_play_news_host_runtime as arouter_run_vacuumtube_play_news_host_runtime,
        run_vacuumtube_resume_playback_host_runtime as arouter_run_vacuumtube_resume_playback_host_runtime,
        run_vacuumtube_route_to_home_host_runtime as arouter_run_vacuumtube_route_to_home_host_runtime,
        run_vacuumtube_select_account_if_needed_host_runtime as arouter_run_vacuumtube_select_account_if_needed_host_runtime,
        run_vacuumtube_snapshot_state as arouter_run_vacuumtube_snapshot_state,
        run_vacuumtube_snapshot_state_host_runtime as arouter_run_vacuumtube_snapshot_state_host_runtime,
        run_vacuumtube_stop_music_host_runtime as arouter_run_vacuumtube_stop_music_host_runtime,
        run_vacuumtube_try_resume_current_video_host_runtime as arouter_run_vacuumtube_try_resume_current_video_host_runtime,
        run_vacuumtube_wait_watch_route as arouter_run_vacuumtube_wait_watch_route,
        run_vacuumtube_wait_watch_route_host_runtime as arouter_run_vacuumtube_wait_watch_route_host_runtime,
        run_weather_pages_closed_host_runtime as arouter_run_weather_pages_closed_host_runtime,
        run_weather_pages_tiled_host_runtime as arouter_run_weather_pages_tiled_host_runtime,
        start_vacuumtube_tmux_session as arouter_start_vacuumtube_tmux_session,
        resolve_live_cam_layout_plan as arouter_resolve_live_cam_layout_plan,
        select_weather_candidate_window_ids as arouter_select_weather_candidate_window_ids,
        should_ack_before_action as arouter_should_ack_before_action,
        should_wait_ack_before_action as arouter_should_wait_ack_before_action,
        suppress_transcribed_command_reason as arouter_suppress_transcribed_command_reason,
        start_biometric_poller as arouter_start_biometric_poller,
        start_vacuumtube_context_poller_host_runtime as arouter_start_vacuumtube_context_poller_host_runtime,
        set_system_locked as arouter_set_system_locked,
        unlock_requires_face_auth_text as arouter_unlock_requires_face_auth_text,
        unlock_requires_live_voice_text as arouter_unlock_requires_live_voice_text,
        unlock_requires_password_text as arouter_unlock_requires_password_text,
        unlock_requires_speaker_auth_text as arouter_unlock_requires_speaker_auth_text,
        select_live_cam_payload as arouter_select_live_cam_payload,
        stop_biometric_poller as arouter_stop_biometric_poller,
        stop_vacuumtube_context_poller as arouter_stop_vacuumtube_context_poller,
        build_kwin_invoke_shortcut_command as arouter_build_kwin_invoke_shortcut_command,
        build_top_right_position_attempt_plan as arouter_build_top_right_position_attempt_plan,
        build_top_right_position_result as arouter_build_top_right_position_result,
        build_window_presentation_snapshot as arouter_build_window_presentation_snapshot,
        finalize_top_right_position_result as arouter_finalize_top_right_position_result,
        geometry_close as arouter_geometry_close,
        merge_vacuumtube_cdp_state as arouter_merge_vacuumtube_cdp_state,
        merge_vacuumtube_window_snapshot as arouter_merge_vacuumtube_window_snapshot,
        resolve_expected_top_right_geometry as arouter_resolve_expected_top_right_geometry,
        top_right_region_from_screen_and_work_area as arouter_top_right_region_from_screen_and_work_area,
        run_top_right_position_host_runtime_flow as arouter_run_top_right_position_host_runtime_flow,
        run_top_right_position_flow as arouter_run_top_right_position_flow,
        run_window_restore_flow as arouter_run_window_restore_flow,
        run_window_restore_host_runtime_flow as arouter_run_window_restore_host_runtime_flow,
        run_window_activate as arouter_run_window_activate,
        run_window_activate_host_runtime as arouter_run_window_activate_host_runtime,
        run_window_close as arouter_run_window_close,
        run_window_close_host_runtime as arouter_run_window_close_host_runtime,
        run_window_fullscreen as arouter_run_window_fullscreen,
        run_window_fullscreen_host_runtime as arouter_run_window_fullscreen_host_runtime,
        run_window_key as arouter_run_window_key,
        run_window_key_host_runtime as arouter_run_window_key_host_runtime,
        run_window_move_resize as arouter_run_window_move_resize,
        run_window_move_resize_host_runtime as arouter_run_window_move_resize_host_runtime,
        wait_for_new_window_row_host_runtime as arouter_wait_for_new_window_row_host_runtime,
        run_wait_for_window_id_host_runtime as arouter_run_wait_for_window_id_host_runtime,
        is_window_fullscreenish as arouter_is_window_fullscreenish,
        resolve_window_restore_plan as arouter_resolve_window_restore_plan,
        trim_notify_text as arouter_trim_notify_text,
        window_rows_for_pids_from_wmctrl_lines as arouter_window_rows_for_pids_from_wmctrl_lines,
        verify_unlock_password as arouter_verify_unlock_password,
        window_title_from_wmctrl_lines as arouter_window_title_from_wmctrl_lines,
        write_signal_file as arouter_write_signal_file,
    )
    from arouter.entrypoint import (
        run_voice_command_entrypoint_host_runtime as arouter_run_voice_command_entrypoint_host_runtime,
    )
    _AROUTER_AVAILABLE = True
except Exception:
    _AROUTER_AVAILABLE = False

try:
    from acaption import (
        AcaptionIpcClient as ExtractedCaptionOverlayIpcClient,
    )
    _ACAPTION_CLIENT_AVAILABLE = True
except Exception:
    _ACAPTION_CLIENT_AVAILABLE = False

try:
    from ahear.speaker_auth import (
        initialize_speaker_auth_runtime as extracted_initialize_speaker_auth_runtime,
        speaker_auth_enabled as extracted_speaker_auth_enabled,
        verify_speaker_identity as extracted_verify_speaker_identity,
    )
    _AHEAR_SPEAKER_AUTH_AVAILABLE = True
except Exception:
    _AHEAR_SPEAKER_AUTH_AVAILABLE = False

try:
    from asec import (
        AsecLockScreenIpcClient as ExtractedLockScreenIpcClient,
    )
    _ASEC_CLIENT_AVAILABLE = True
except Exception:
    _ASEC_CLIENT_AVAILABLE = False

try:
    from asee import (
        fetch_remote_biometric_status as asee_fetch_remote_biometric_status,
        owner_face_absent_for_lock_from_status as asee_owner_face_absent_for_lock_from_status,
        owner_face_recent_for_unlock_from_status as asee_owner_face_recent_for_unlock_from_status,
        resolve_remote_biometric_status_client as asee_resolve_remote_biometric_status_client,
    )
    _ASEE_BIOMETRIC_CLIENT_AVAILABLE = True
except Exception:
    try:
        _asee_python_src = _WORKSPACES_ROOT / "repos" / "asee" / "python" / "src"
        if str(_asee_python_src) not in sys.path:
            sys.path.insert(0, str(_asee_python_src))
        from asee.biometric_client import (
            fetch_remote_biometric_status as asee_fetch_remote_biometric_status,
            owner_face_absent_for_lock_from_status as asee_owner_face_absent_for_lock_from_status,
            owner_face_recent_for_unlock_from_status as asee_owner_face_recent_for_unlock_from_status,
            resolve_remote_biometric_status_client as asee_resolve_remote_biometric_status_client,
        )
        _ASEE_BIOMETRIC_CLIENT_AVAILABLE = True
    except Exception:
        asee_fetch_remote_biometric_status = None
        asee_owner_face_absent_for_lock_from_status = None
        asee_owner_face_recent_for_unlock_from_status = None
        asee_resolve_remote_biometric_status_client = None
        _ASEE_BIOMETRIC_CLIENT_AVAILABLE = False

try:
    from asay import (
        VoiceVoxSpeaker as ExtractedVoiceVoxSpeaker,
    )
    _ASAY_VOICEVOX_AVAILABLE = True
except Exception:
    _ASAY_VOICEVOX_AVAILABLE = False


def _write_temp_js_script(script_text: str, prefix: str) -> str:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".js",
        prefix=prefix,
        delete=False,
    ) as tf:
        tf.write(script_text)
        return tf.name

# ── STT backend selection ─────────────────────────────────────────────────────
# Resolved at import time (before parse_args) because the base class hierarchy
# depends on which module is imported as `base`.
# Priority: --stt-backend CLI flag > STT_BACKEND env var > 'moonshine' (default)
def _detect_stt_backend() -> str:
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--stt-backend" and i + 1 < len(argv):
            return argv[i + 1].lower()
        if arg.startswith("--stt-backend="):
            return arg.split("=", 1)[1].lower()
    return os.environ.get("STT_BACKEND", "moonshine").lower()

_STT_BACKEND = _detect_stt_backend()
if _STT_BACKEND == "moonshine":
    from ahear import moonshine_listener as base  # type: ignore[no-redef]
else:
    from ahear import whisper_listener as base

DEFAULT_STT_PROMPT_JA = (
    "日本語の音声コマンド。"
    "システム 状況報告。"
    "システム 通常モード。"
    "システム 世界情勢モード。"
    "システム 天気予報モード。"
    "システム ロックモード。"
    "システム 今日の天気。"
    "システム 街頭カメラモード。"
    "システム 街頭カメラ確認したい。"
    "システム 街頭カメラを見せて。"
    "システム 街頭カメラを大きくして。"
    "システム 街頭カメラを最大化して。"
    "システム 街頭カメラ小さくして。"
    "システム 街頭カメラ非表示にして。"
    "システム ウェブカメラモード。"
    "システム ウェブカメラが見たい。"
    "システム ウェブカメラを最大化。"
    "システム ウェブカメラを小さくして。"
    "システム ウェブカメラを背景にして。"
    "システム 負荷を確認。"
    "システム 負荷チェック。"
    "ニュースライブを再生して。"
    "朝のニュースを見せて。"
    "夕方のニュースが見たい。"
    "YouTubeのホームに移動して。"
    "YouTubeを全画面にして。"
    "YouTubeを最大化して。"
    "YouTubeを小さくして。"
    "システム YouTubeを最小化して。"
    "システム YouTubeを非表示にして。"
    "システム YouTubeを隠して。"
    "システム YouTubeをバックグラウンドにして。"
    "おはよう。おやすみ。"
)
DEFAULT_BIOMETRIC_PASSWORD_FILE = os.path.expanduser(
    "~/.config/yuiclaw/biometric-password.enc"
)
DEFAULT_BIOMETRIC_PASSWORD_PUBLIC_KEY = os.path.expanduser(
    "~/.ssh/google_compute_engine.pub"
)
DEFAULT_BIOMETRIC_PASSWORD_PRIVATE_KEY = os.path.expanduser(
    "~/.ssh/google_compute_engine"
)
DEFAULT_BIOMETRIC_UNLOCK_SIGNAL_FILE = os.path.expanduser(
    "~/.cache/yuiclaw/biometric-unlock.signal"
)
DEFAULT_BIOMETRIC_LOCK_SIGNAL_FILE = os.path.expanduser(
    "~/.cache/yuiclaw/biometric-lock.signal"
)


def switchbot_lights_on() -> str:
    """Turn on living room lights via SwitchBot CLI. Returns result string."""
    try:
        cp = subprocess.run(
            ["switchbot", "lights", "on"],
            capture_output=True, text=True, check=False,
        )
        if cp.returncode == 0:
            return f"switchbot lights on: {cp.stdout.strip()}"
        return f"switchbot lights on error (rc={cp.returncode}): {cp.stderr.strip()}"
    except Exception as e:
        return f"switchbot lights on exception: {e}"


def switchbot_lights_off() -> str:
    """Turn off living room lights via SwitchBot CLI. Returns result string."""
    try:
        cp = subprocess.run(
            ["switchbot", "lights", "off"],
            capture_output=True, text=True, check=False,
        )
        if cp.returncode == 0:
            return f"switchbot lights off: {cp.stdout.strip()}"
        return f"switchbot lights off error (rc={cp.returncode}): {cp.stderr.strip()}"
    except Exception as e:
        return f"switchbot lights off exception: {e}"


BGM_POSITIVE_KEYWORDS = [
    "ambient",
    "ambience",
    "relax",
    "relaxing",
    "study",
    "focus",
    "music",
    "bgm",
    "lofi",
    "jazz",
    "piano",
    "chill",
    "sleep",
    "deep work",
    "flow state",
    "calm",
    "serene",
    "snow",
    "cabin",
]

BGM_NEGATIVE_KEYWORDS = [
    "news",
    "breaking",
    "速報",
    "ニュース",
    "会見",
    "ann",
    "nhk",
    "reuters",
    "bbc",
]

NEWS_POSITIVE_KEYWORDS = [
    "news",
    "ニュース",
    "live",
    "ライブ",
    "速報",
    "breaking",
    "配信中",
    "生放送",
    "ann",
    "annnews",
    "annnewsch",
    "tbs",
    "nhk",
    "fnn",
    "jnn",
    "bbc",
    "reuters",
    "日テレnews",
    "テレ朝news",
    "abema news",
    "news live",
    "live news",
]

NEWS_MORNING_KEYWORDS = [
    "朝",
    "morning",
    "モーニング",
    "おはよう",
    "めざまし",
    "zip",
    "the time",
    "モーサテ",
]

NEWS_EVENING_KEYWORDS = [
    "夕方",
    "夜",
    "evening",
    "night",
    "イブニング",
    "news zero",
    "news23",
    "報道ステーション",
    "nスタ",
    "news every",
    "newsevery",
    "live news イット",
    "wbs",
    "ニュース7",
    "news7",
]

WEATHER_EN_TO_JA_EXACT = {
    "clear sky": "快晴",
    "clear": "晴れ",
    "mainly clear": "おおむね晴れ",
    "partly cloudy": "晴れ時々くもり",
    "cloudy": "くもり",
    "overcast": "曇り",
    "fog": "霧",
    "depositing rime fog": "着氷性の霧",
    "light drizzle": "弱い霧雨",
    "moderate drizzle": "霧雨",
    "dense drizzle": "強い霧雨",
    "light freezing drizzle": "弱い着氷性の霧雨",
    "dense freezing drizzle": "強い着氷性の霧雨",
    "slight rain": "弱い雨",
    "moderate rain": "雨",
    "heavy rain": "強い雨",
    "heavy rain showers": "強いにわか雨",
    "light rain showers": "弱いにわか雨",
    "rain showers": "にわか雨",
    "slight snow fall": "弱い雪",
    "moderate snow fall": "雪",
    "heavy snow fall": "強い雪",
    "snow fall": "雪",
    "snow grains": "雪あられ",
    "thunderstorm": "雷雨",
    "thunderstorm with slight hail": "ひょうを伴う雷雨",
    "thunderstorm with heavy hail": "強いひょうを伴う雷雨",
}

CITY_EN_TO_JA = {
    "tokyo": "東京",
    "osaka": "大阪",
    "nagoya": "名古屋",
    "sapporo": "札幌",
    "fukuoka": "福岡",
}

WEATHER_DESKTOP_TILES = [
    {
        "label": "jwa_amesh",
        "url": "https://tokyo-ame.jwa.or.jp/",
        "geom": {"x": 0, "y": 28, "w": 2048, "h": 1052},  # left-top
    },
    {
        "label": "yahoo_weather_tokyo",
        "url": "https://weather.yahoo.co.jp/weather/jp/13/4410.html",
        "geom": {"x": 0, "y": 1108, "w": 2048, "h": 1008},  # left-bottom
    },
    {
        "label": "tenkijp_taito",
        "url": "https://tenki.jp/forecast/3/16/4410/13106/",
        "geom": {"x": 2048, "y": 1108, "w": 2048, "h": 1008},  # right-bottom
    },
]


def _norm_blob(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _blob_has_keyword(blob: str, keyword: str) -> bool:
    if not blob or not keyword:
        return False
    kw = keyword.lower()

    # Avoid false-positive "ライブ" hit from "ドライブ" in music titles.
    if kw == "ライブ":
        return re.search(r"(?<!ド)ライブ", blob) is not None

    # ASCII alphabetic keywords should match token-like boundaries.
    if re.fullmatch(r"[a-z][a-z0-9 .-]*", kw):
        pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
        return re.search(pattern, blob) is not None

    return kw in blob


def _count_hits(blob: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if _blob_has_keyword(blob, kw))


def geometry_close(actual: dict[str, Any], expected: dict[str, Any], *, tol: int = 24) -> bool:
    return arouter_geometry_close(actual, expected, tol=tol)


def _build_top_right_position_result(
    *,
    window_id: str,
    target: dict[str, Any],
    before: dict[str, Any] | None,
    tolerance: int,
) -> dict[str, Any]:
    return arouter_build_top_right_position_result(
        window_id=window_id,
        target=target,
        before=before,
        tolerance=tolerance,
    )


def _build_top_right_position_attempt_plan(
    *,
    retries: int,
    has_main_pid: bool,
) -> list[dict[str, Any]]:
    return arouter_build_top_right_position_attempt_plan(
        retries=retries,
        has_main_pid=has_main_pid,
    )


def _finalize_top_right_position_result(
    result: dict[str, Any],
    *,
    geom: dict[str, Any] | None,
    expected: dict[str, Any],
    tol: int,
    method: str,
) -> dict[str, Any]:
    return arouter_finalize_top_right_position_result(
        result,
        geom=geom,
        expected=expected,
        tol=tol,
        method=method,
    )


def weather_desc_to_ja(desc: str) -> str:
    raw = (desc or "").strip()
    if not raw:
        return "不明"
    key = raw.lower()
    if key in WEATHER_EN_TO_JA_EXACT:
        return WEATHER_EN_TO_JA_EXACT[key]
    return raw


def _fmt_num_ja(value: Any) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.1f}"


def parse_weathercli_output(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    out: dict[str, Any] = {"forecasts": []}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Date:"):
            out["date"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Location:"):
            out["location"] = line.split(":", 1)[1].strip()
            continue
        m = re.match(r"^Current:\s*([-+]?\d+(?:\.\d+)?)°C,\s*(.+)$", line)
        if m:
            out["current_temp_c"] = float(m.group(1))
            out["current_desc"] = m.group(2).strip()
            continue
        m = re.match(r"^Wind:\s*([-+]?\d+(?:\.\d+)?)\s*km/h$", line)
        if m:
            out["wind_kmh"] = float(m.group(1))
            continue
        m = re.match(
            r"^-\s*(\d{4}-\d{2}-\d{2}):\s*([-+]?\d+(?:\.\d+)?)°C\s*/\s*([-+]?\d+(?:\.\d+)?)°C\s*-\s*(.+)$",
            line,
        )
        if m:
            out["forecasts"].append(
                {
                    "date": m.group(1),
                    "max_c": float(m.group(2)),
                    "min_c": float(m.group(3)),
                    "desc": m.group(4).strip(),
                }
            )
    if "current_temp_c" not in out and not out.get("forecasts"):
        return None
    return out


def build_weather_today_voice_ja(parsed: dict[str, Any]) -> str:
    location_raw = str(parsed.get("location") or "").strip()
    location_head = location_raw.split("(", 1)[0].strip()
    loc_ja = CITY_EN_TO_JA.get(location_head.lower(), location_head or "現在地")

    parts: list[str] = ["今日の天気です。"]
    if loc_ja:
        parts.append(f"{loc_ja}は")

    current_desc = weather_desc_to_ja(str(parsed.get("current_desc") or ""))
    current_temp = parsed.get("current_temp_c")
    if current_temp is not None:
        parts.append(f"現在{_fmt_num_ja(current_temp)}度、{current_desc}です。")
    elif current_desc:
        parts.append(f"{current_desc}です。")

    wind = parsed.get("wind_kmh")
    if wind is not None:
        parts.append(f"風は{_fmt_num_ja(wind)}キロ毎時です。")

    forecasts = parsed.get("forecasts") or []
    date_str = str(parsed.get("date") or "")
    today_fc = None
    if isinstance(forecasts, list):
        for fc in forecasts:
            if isinstance(fc, dict) and str(fc.get("date") or "") == date_str:
                today_fc = fc
                break
        if today_fc is None and forecasts and isinstance(forecasts[0], dict):
            today_fc = forecasts[0]
    if isinstance(today_fc, dict):
        hi = _fmt_num_ja(today_fc.get("max_c"))
        lo = _fmt_num_ja(today_fc.get("min_c"))
        fc_desc = weather_desc_to_ja(str(today_fc.get("desc") or ""))
        parts.append(f"きょうの予報は最高{hi}度、最低{lo}度、{fc_desc}です。")

    return "".join(parts)


def _weathercli_repo_dir() -> Path:
    root = _WORKSPACES_ROOT
    candidates = [
        root / "repos" / "weathercli",
        root / "repos" / "_cli" / "weathercli",
    ]
    for p in candidates:
        if (p / "Makefile").exists():
            return p
    raise FileNotFoundError("weathercli repository not found (expected repos/weathercli or repos/_cli/weathercli)")


def _tmux_htop_nvitop_konsole_script() -> Path:
    root = _WORKSPACES_ROOT
    p = root / ".codex" / "skills" / "tmux-htop-nvitop-konsole" / "scripts" / "tmux_htop_nvitop_konsole.sh"
    if p.exists():
        return p
    raise FileNotFoundError(f"tmux htop+nvitop konsole script not found: {p}")


def detect_non_command_reaction(text: str) -> str | None:
    """Detect non-command vocal reactions for future personalization hooks.

    Current policy:
    - Do not trust "(笑)" because sneezes can be transcribed that way.
    - Treat repeated "はっ" (>=2) as a reliable laugh signal.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    compact = re.sub(r"[\s、,。．!！?？・…]+", "", raw)
    if re.search(r"(?:[はハ][っッ]){2,}", compact):
        return "laugh"
    return None


def watch_playback_confirmed(
    first_watch_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
    *,
    min_current_time: float = 0.5,
    min_delta: float = 0.15,
) -> bool:
    video = current_snapshot.get("video")
    if not isinstance(video, dict):
        return False
    if bool(video.get("paused", True)):
        return False
    try:
        ct_now = float(video.get("currentTime") or 0.0)
    except Exception:
        ct_now = 0.0
    if ct_now >= min_current_time:
        return True
    if not isinstance(first_watch_snapshot, dict):
        return False
    first_video = first_watch_snapshot.get("video")
    if not isinstance(first_video, dict):
        return False
    try:
        ct_first = float(first_video.get("currentTime") or 0.0)
    except Exception:
        ct_first = 0.0
    return (ct_now - ct_first) >= min_delta


def looks_like_news_blob(text: str, *, slot: str = "generic", has_ja_live_badge: bool = False) -> bool:
    blob = _norm_blob(text)
    if not blob:
        return False

    core_news_keywords = [kw for kw in NEWS_POSITIVE_KEYWORDS if kw not in ("live", "ライブ")]
    news_hits = _count_hits(blob, core_news_keywords)
    bgm_hits = _count_hits(blob, BGM_POSITIVE_KEYWORDS)
    live_text_hits = _count_hits(blob, ["live", "ライブ", "生放送", "配信中"])
    fresh_hits = _count_hits(blob, ["速報", "分前", "時間前", "minutes ago", "hours ago"])
    morning_hits = _count_hits(blob, NEWS_MORNING_KEYWORDS)
    evening_hits = _count_hits(blob, NEWS_EVENING_KEYWORDS)
    live_signal = live_text_hits + (1 if has_ja_live_badge else 0)

    if news_hits <= 0 and live_signal <= 0 and fresh_hits <= 0:
        return False
    if bgm_hits >= 2 and news_hits == 0:
        return False

    if slot == "morning":
        if morning_hits > 0 and news_hits > 0:
            return True
        # If not explicitly morning, still allow clearly news/live content.
        return news_hits >= 1 and (live_signal + fresh_hits >= 1) and evening_hits == 0

    if slot == "evening":
        if evening_hits > 0 and news_hits > 0:
            return True
        return news_hits >= 1 and (live_signal + fresh_hits >= 1) and morning_hits == 0

    # Generic news playback should still require some news-like signal.
    # Freshness text alone (e.g. "7時間前") appears on music tiles too often.
    return news_hits >= 1 and (live_signal >= 1 or fresh_hits >= 1)


@dataclass
class VoiceCommand:
    intent: str
    normalized_text: str
    raw_text: str
    secret_text: str = ""

    @property
    def ack_text(self) -> str:
        if self.intent == "music_play":
            return "承知しました、音楽を再生します。"
        if self.intent == "music_stop":
            return "承知しました、音楽を停止します。"
        if self.intent == "playback_resume":
            return "承知しました、動画の再生を再開します。"
        if self.intent == "playback_stop":
            return "承知しました、動画の再生を停止します。"
        if self.intent == "news_live":
            return "承知しました、ニュースライブを再生します。"
        if self.intent == "news_morning":
            return "承知しました、朝のニュースを再生します。"
        if self.intent == "news_evening":
            n = (self.normalized_text or "").lower()
            if any(k in n for k in ("夜", "night")):
                return "承知しました、夜のニュースを再生します。"
            return "承知しました、夕方のニュースを再生します。"
        if self.intent == "youtube_fullscreen":
            return "承知しました、YouTubeを全画面にします。"
        if self.intent == "youtube_quadrant":
            return "承知しました、YouTubeを小さくします。"
        if self.intent == "youtube_minimize":
            return "承知しました、YouTubeを最小化します。"
        if self.intent == "youtube_home":
            return "承知しました、YouTubeのホーム画面に戻ります。"
        if self.intent == "system_status_report":
            return "システムチェック完了 オールグリーン 通常モード"
        if self.intent == "system_weather_today":
            return "承知しました、今日の天気を確認します。"
        if self.intent == "weather_pages_today":
            return "承知しました、天気予報ページを表示します。"
        if self.intent == "system_live_camera_show":
            return "承知しました、街頭カメラを表示します。"
        if self.intent == "system_live_camera_compact":
            return "承知しました、街頭カメラを小さくします。"
        if self.intent == "system_live_camera_hide":
            return "承知しました、街頭カメラを閉じます。"
        if self.intent == "system_street_camera_mode":
            return "承知しました。街頭カメラモードへ移行します。"
        if self.intent == "system_webcam_mode":
            return "承知しました。ウェブカメラモードへ移行します。"
        if self.intent == "god_mode_show":
            return "承知しました、ウェブカメラを表示します。"
        if self.intent == "god_mode_fullscreen":
            return "承知しました、ウェブカメラを最大化します。"
        if self.intent == "god_mode_compact":
            return "承知しました、ウェブカメラを小さくします。"
        if self.intent == "god_mode_background":
            return "承知しました、ウェブカメラを背景にします。"
        if self.intent == "system_normal_mode":
            return "承知しました。通常モードに移行します。"
        if self.intent == "system_world_situation_mode":
            return "承知しました。世界情勢モードへ移行します。"
        if self.intent == "system_weather_mode":
            return "承知しました。天気予報モードへ移行します。"
        if self.intent == "system_lock_mode":
            return "承知しました。ロックモードへ移行します。"
        if self.intent == "system_load_check":
            return "承知しました、負荷を確認します。"
        if self.intent == "system_biometric_auth":
            return "承知しました。バイオメトリクス認証を確認します。"
        if self.intent == "system_password_unlock":
            return "承知しました。パスワードを確認します。"
        if self.intent == "good_morning":
            return "おはようございます、ユイさま。朝のニュースを再生しますね。"
        if self.intent == "good_night":
            return "おやすみなさいませ。どうぞ良い夢を。"
        return "承知しました。"


def normalize_transcript(text: str) -> str:
    s = (text or "").strip()
    s = s.replace("\u3000", " ")
    s = s.replace("|", " ").replace("｜", " ")
    s = s.lower()
    s = re.sub(r"[\s\t\r\n]+", "", s)
    s = re.sub(r"[。．！？!?,，、・]+$", "", s)
    # Normalize full-width ASCII alphanumerics to half-width
    # (moonshine models sometimes output ＢＧＭ / ＣＳＴＭ etc.)
    s = "".join(
        chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c
        for c in s
    )
    return s


def extract_password_unlock_secret(normalized_text: str) -> str:
    s = normalize_transcript(normalized_text)
    for prefix in (
        "システムパスワード",
        "systempassword",
        "システムロック解除パスワード",
        "systemunlockpassword",
    ):
        if s.startswith(prefix):
            return s[len(prefix) :]
    return ""


def _read_password_secret_lines_from_stdin() -> list[str]:
    raw = sys.stdin.read()
    return arouter_read_password_secret_lines(raw)


def encrypt_biometric_password_file(
    *,
    public_key_path: Path,
    output_path: Path,
    password_lines: list[str],
) -> Path:
    return arouter_encrypt_password_file(
        public_key_path=public_key_path,
        output_path=output_path,
        password_lines=password_lines,
    )


def write_biometric_signal_file(*, signal_path: Path, action: str) -> Path:
    return arouter_write_signal_file(signal_path=signal_path, action=action)


def parse_command(text: str) -> VoiceCommand | None:
    raw = (text or "").strip()
    if not raw:
        return None

    normalized = normalize_transcript(raw)
    if not normalized:
        return None

    # Domain-specific corrections observed with smaller Japanese models.
    normalized_alias = normalized
    normalized_alias = normalized_alias.replace("本部", "音楽")
    normalized_alias = normalized_alias.replace("vgm", "bgm")
    normalized_alias = normalized_alias.replace("水銭も", "bgmを")
    normalized_alias = normalized_alias.replace("水銭を", "bgmを")
    normalized_alias = normalized_alias.replace("水銭", "bgm")
    normalized_alias = normalized_alias.replace("天気おほう", "天気予報")
    normalized_alias = normalized_alias.replace("テンキをほう", "天気予報")
    normalized_alias = normalized_alias.replace("テンキ予報", "天気予報")
    normalized_alias = normalized_alias.replace("ロイブカメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("ワイブカメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("レイブカメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("フェイブカメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("ライブカカメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("ライブカメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("外当カメラ", "街頭カメラ")
    normalized_alias = normalized_alias.replace("だいぶカメラ", "街頭カメラ")  # moonshine misrecognition of ライブ
    normalized_alias = normalized_alias.replace("ダイブカメラ", "街頭カメラ")  # whisper misrecognition of ライブ
    normalized_alias = normalized_alias.replace("ウェブカーメラ", "ウェブカメラ")
    normalized_alias = normalized_alias.replace("ウエブカメラ", "ウェブカメラ")
    # System wake word variants observed in whisper.cpp / moonshine Japanese transcription.
    normalized_alias = normalized_alias.replace("スステム", "システム")
    normalized_alias = normalized_alias.replace("リステム", "システム")
    normalized_alias = normalized_alias.replace("エステム", "システム")
    normalized_alias = normalized_alias.replace("チステム", "システム")
    normalized_alias = normalized_alias.replace("フィスペム", "システム")
    normalized_alias = normalized_alias.replace("フィクテム", "システム")
    normalized_alias = normalized_alias.replace("cstm", "システム")  # moonshine full-width ＣＳＴＭ→cstm after normalize
    # moonshine drops the initial シ from システム, outputting ステム... at start of utterance.
    normalized_alias = re.sub(r"^ステム", "システム", normalized_alias)
    # セステム -> スステム -> システム (double-hop fix for セ→ス→シ variants)
    normalized_alias = normalized_alias.replace("セステム", "システム")
    normalized_alias = normalized_alias.replace("バイオメデリックス", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バイオメテリクス", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バイオメテリクシン", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バイオメティクセニーショー", "バイオメトリクス認証")
    normalized_alias = normalized_alias.replace("バイオメテルクセ", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バイオミテリクス", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バイオミテリックス", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バヤメテリクス", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("バイラメテリクス", "バイオメトリクス")
    normalized_alias = normalized_alias.replace("認証開始", "認証")
    normalized_alias = re.sub(r"バイオメトリクス認$", "バイオメトリクス認証", normalized_alias)
    normalized_alias = re.sub(r"バイオメトリクス$", "バイオメトリクス認証", normalized_alias)
    normalized_alias = normalized_alias.replace("フカ", "負荷")
    normalized_alias = normalized_alias.replace("深を確認", "負荷を確認")
    normalized_alias = normalized_alias.replace("負荷チェック", "負荷を確認")
    # moonshine word-ending truncation补完: long utterances often lose trailing mora(s).
    # e.g. YouTubeを全画[面にして] / YouTubeのホーム画面に戻[って] / YouTubeを大[きくして]
    normalized_alias = re.sub(r"全画(?!面)", "全画面にして", normalized_alias)
    normalized_alias = re.sub(r"ホーム画面に戻$", "ホーム画面に戻って", normalized_alias)
    normalized_alias = re.sub(r"(youtube[をのはが]?)大$", r"\1大きくして", normalized_alias)
    normalized_alias = normalized_alias.replace("災害化", "最大化")
    normalized_alias = re.sub(r"(youtube[をのはが]?)最大$", r"\1最大化して", normalized_alias)
    normalized_alias = re.sub(r"(youtube[をのはが]?)小$", r"\1小さくして", normalized_alias)

    has_music_subject = any(k in normalized_alias for k in ("音楽", "bgm", "ミュージック"))
    is_play = any(k in normalized_alias for k in ("再生", "流して", "流す", "かけて", "かける", "掛けて", "掛ける"))
    is_stop = any(k in normalized_alias for k in ("停止", "止め", "とめ", "止ま", "一時停止"))
    is_resume = any(k in normalized_alias for k in ("再開", "再生再開"))
    has_news_subject = any(k in normalized_alias for k in ("ニュース", "news"))
    has_video_subject = any(k in normalized_alias for k in ("動画", "ビデオ", "video"))
    has_youtube_subject = any(k in normalized_alias for k in ("youtube", "ユーチューブ", "ようつべ"))
    has_home_subject = any(k in normalized_alias for k in ("ホーム画面", "ホーム"))
    has_fullscreen_subject = any(
        k in normalized_alias for k in ("全画面", "フルスクリーン", "大きく", "おおきく", "最大化", "さいだいか")
    )
    has_small_subject = any(k in normalized_alias for k in ("小さく", "ちいさく"))
    has_quadrant_subject = any(k in normalized_alias for k in ("4分割", "四分割"))
    wants_move_home = any(k in normalized_alias for k in ("戻って", "戻る", "移動して", "移動", "行って", "行く"))
    wants_watch = any(k in normalized_alias for k in ("見たい", "みたい", "見せて", "みせて", "再生", "流して", "流す", "つけて", "つける"))
    wants_resize_mode = any(k in normalized_alias for k in ("して", "にして", "にする", "戻して", "戻す", "モード"))
    news_live_hint = any(k in normalized_alias for k in ("ライブ", "live", "最新", "速報", "生放送"))
    news_morning_hint = any(k in normalized_alias for k in ("朝", "morning", "モーニング", "おはよう"))
    news_evening_hint = any(k in normalized_alias for k in ("夕方", "夜", "evening", "night", "イブニング"))
    has_weather_subject = any(k in normalized_alias for k in ("天気", "weather"))
    has_forecast_subject = ("天気予報" in normalized_alias) or ("予報" in normalized_alias)
    wants_weather_report = any(k in normalized_alias for k in ("教えて", "おしえて", "は", "確認", "報告", "チェック"))
    has_today_hint = any(k in normalized_alias for k in ("今日", "きょう", "本日"))
    has_live_camera_subject = any(k in normalized_alias for k in ("街頭カメラ", "ライブカメラ", "livecamera", "livecam"))
    has_webcam_subject = any(k in normalized_alias for k in ("ウェブカメラ", "webカメラ", "webcam", "ウェブカム"))
    has_load_subject = any(k in normalized_alias for k in ("負荷", "load"))
    wants_hide = any(k in normalized_alias for k in ("終了", "終わ", "閉じて", "閉じる", "非表示", "隠して", "かくして"))
    wants_background = any(k in normalized_alias for k in ("背景", "バックグラウンド"))
    wants_confirm = any(k in normalized_alias for k in ("確認", "見たい", "みたい", "見せて", "みせて", "表示", "確認したい"))
    playback_object_hint = any(
        k in normalized_alias for k in ("再生を", "再生の", "動画を", "動画の", "ニュースを", "ニュースの", "再生中")
    )
    has_system_subject = ("システム" in normalized_alias) or ("system" in normalized_alias)
    wants_load_check = wants_confirm or ("チェック" in normalized_alias) or ("買ってみ" in normalized_alias)
    # 負荷 is specific enough that システム prefix is not required.
    if has_load_subject and wants_load_check:
        return VoiceCommand(intent="system_load_check", normalized_text=normalized_alias, raw_text=raw)

    # 通常モード / 世界情勢モード accept without システム prefix:
    # - these phrases are unique enough that false-positive risk is negligible.
    # - moonshine sometimes drops the システム prefix entirely.
    if "通常モード" in normalized_alias:
        return VoiceCommand(intent="system_normal_mode", normalized_text=normalized_alias, raw_text=raw)

    if "世界情勢モード" in normalized_alias:
        return VoiceCommand(intent="system_world_situation_mode", normalized_text=normalized_alias, raw_text=raw)

    if "天気予報モード" in normalized_alias:
        return VoiceCommand(intent="system_weather_mode", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and ("ロックモード" in normalized_alias or "lockmode" in normalized_alias):
        return VoiceCommand(intent="system_lock_mode", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and ("街頭カメラモード" in normalized_alias):
        return VoiceCommand(intent="system_street_camera_mode", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and ("ウェブカメラモード" in normalized_alias):
        return VoiceCommand(intent="system_webcam_mode", normalized_text=normalized_alias, raw_text=raw)

    if (
        ("システム" in normalized_alias or "system" in normalized_alias)
        and any(
            k in normalized_alias
            for k in (
                "状況報告",
                "状態報告",
                "現状報告",
                "状況教えて",
                "状態教えて",
                "現状教えて",
                "ステータス",
                "ステータスチェック",
                "ステータス確認",
                "チェック",
                "status",
            )
        )
    ) or normalized_alias in (
        "システム状況報告",
        "システム状態報告",
        "システム現状報告",
        "システム状況教えて",
        "システム状態教えて",
        "システム現状教えて",
        "システムステータス",
        "システムチェック",
        "システムステータスチェック",
        "システムステータス報告",
        "システムステータス確認",
        "状況報告",
        "状態教えて",
        "statusreport",
    ):
        return VoiceCommand(intent="system_status_report", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and has_live_camera_subject:
        if wants_hide:
            return VoiceCommand(intent="system_live_camera_hide", normalized_text=normalized_alias, raw_text=raw)
        if has_small_subject or has_quadrant_subject or ("小さく" in normalized_alias) or ("ちいさく" in normalized_alias):
            return VoiceCommand(intent="system_live_camera_compact", normalized_text=normalized_alias, raw_text=raw)
        if wants_confirm or wants_watch or has_fullscreen_subject:
            return VoiceCommand(intent="system_live_camera_show", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and has_webcam_subject:
        if wants_background:
            return VoiceCommand(intent="god_mode_background", normalized_text=normalized_alias, raw_text=raw)
        if has_fullscreen_subject:
            return VoiceCommand(intent="god_mode_fullscreen", normalized_text=normalized_alias, raw_text=raw)
        if has_small_subject or ("小さく" in normalized_alias) or ("ちいさく" in normalized_alias):
            return VoiceCommand(intent="god_mode_compact", normalized_text=normalized_alias, raw_text=raw)
        if wants_confirm or wants_watch:
            return VoiceCommand(intent="god_mode_show", normalized_text=normalized_alias, raw_text=raw)

    # "システム 天気予報を表示/見せて" should open forecast pages (weather skill workflow)
    # instead of the spoken weather summary intent.
    if has_system_subject and has_forecast_subject and (wants_confirm or wants_watch or ("開いて" in normalized_alias)):
        return VoiceCommand(intent="weather_pages_today", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and has_weather_subject and has_today_hint and wants_weather_report:
        return VoiceCommand(intent="system_weather_today", normalized_text=normalized_alias, raw_text=raw)
    if (not has_system_subject) and has_weather_subject and has_today_hint and wants_weather_report:
        return VoiceCommand(intent="weather_pages_today", normalized_text=normalized_alias, raw_text=raw)

    if any(k in normalized_alias for k in (
        "バイオメトリクス認証", "バイオメトリクス", "バイオメトリック",
        "バイアメテリクス",  # whisper 誤認識パターン
        "生体認証", "biometricauth", "biometrics",
        "認証解除", "ロック解除",
    )):
        return VoiceCommand(intent="system_biometric_auth", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and any(k in normalized_alias for k in ("パスワード", "password")):
        secret_text = extract_password_unlock_secret(normalized_alias)
        if secret_text:
            return VoiceCommand(
                intent="system_password_unlock",
                normalized_text=normalized_alias,
                raw_text=raw,
                secret_text=secret_text,
            )

    if has_system_subject and any(k in normalized_alias for k in ("おはよう", "おはよ", "お早う", "goodmorning")):
        return VoiceCommand(intent="good_morning", normalized_text=normalized_alias, raw_text=raw)

    if has_system_subject and (
        normalized_alias in (
            "システムおやすみ",
            "システムおやすみなさい",
            "システムおやすみなさいませ",
            "システムお休み",
            "システムお休みなさい",
            "システム寝る",
            "システム寝ます",
            "systemgoodnight",
            "systemsleep",
        )
        or any(
            normalized_alias.endswith(s)
            for s in (
                "システムおやすみ",
                "システムおやすみなさい",
                "システム寝る",
                "システム寝ます",
                "systemgoodnight",
                "systemsleep",
            )
        )
    ):
        return VoiceCommand(intent="good_night", normalized_text=normalized_alias, raw_text=raw)

    if has_youtube_subject and has_fullscreen_subject and wants_resize_mode and not is_stop:
        return VoiceCommand(intent="youtube_fullscreen", normalized_text=normalized_alias, raw_text=raw)

    if (
        (has_youtube_subject and has_small_subject and wants_resize_mode)
        or (has_quadrant_subject and wants_resize_mode)
    ):
        return VoiceCommand(intent="youtube_quadrant", normalized_text=normalized_alias, raw_text=raw)

    if has_youtube_subject and any(k in normalized_alias for k in ("最小化", "非表示", "隠して", "バックグラウンド")):
        return VoiceCommand(intent="youtube_minimize", normalized_text=normalized_alias, raw_text=raw)

    # YouTube home navigation must be explicit to avoid colliding with other apps' "home".
    if has_youtube_subject and has_home_subject and wants_move_home:
        return VoiceCommand(intent="youtube_home", normalized_text=normalized_alias, raw_text=raw)

    # Generic playback stop (news/video/music playback). Evaluate before news-play parsing.
    if is_stop and (
        has_music_subject
        or has_news_subject
        or has_video_subject
        or playback_object_hint
        or "再生停止" in normalized_alias
    ):
        if has_music_subject:
            return VoiceCommand(intent="music_stop", normalized_text=normalized_alias, raw_text=raw)
        return VoiceCommand(intent="playback_stop", normalized_text=normalized_alias, raw_text=raw)

    if not is_stop and (is_resume or (has_video_subject and is_play and not has_news_subject)):
        return VoiceCommand(intent="playback_resume", normalized_text=normalized_alias, raw_text=raw)

    if has_music_subject and is_play and not is_stop:
        return VoiceCommand(intent="music_play", normalized_text=normalized_alias, raw_text=raw)

    if has_news_subject and (wants_watch or news_live_hint):
        if news_morning_hint and not news_evening_hint:
            return VoiceCommand(intent="news_morning", normalized_text=normalized_alias, raw_text=raw)
        if news_evening_hint:
            return VoiceCommand(intent="news_evening", normalized_text=normalized_alias, raw_text=raw)
        return VoiceCommand(intent="news_live", normalized_text=normalized_alias, raw_text=raw)

    # Slightly permissive commands when the user omits the subject but still clearly says music/BGM style.
    if normalized_alias in ("再生して", "再生してください", "音楽再生", "bgm再生"):
        return VoiceCommand(intent="music_play", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("停止して", "停止してください", "止めて", "止めてください", "音楽停止", "bgm停止"):
        return VoiceCommand(intent="music_stop", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("動画再開", "動画を再開して", "動画を再生して", "再開して", "再開してください", "動画を再生再開して"):
        return VoiceCommand(intent="playback_resume", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("動画停止", "動画を止めて", "再生を止めて", "再生停止", "ニュース動画再生を止めて"):
        return VoiceCommand(intent="playback_stop", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in (
        "youtubeを全画面にして",
        "youtube全画面",
        "youtubeをフルスクリーンにして",
        "youtubeを大きくして",
        "youtubeを最大化して",
    ):
        return VoiceCommand(intent="youtube_fullscreen", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("youtubeを小さくして", "youtube小さく", "4分割モード", "四分割モード", "4分割にして", "四分割にして"):
        return VoiceCommand(intent="youtube_quadrant", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in (
        "youtubeを最小化して",
        "youtubeを非表示にして",
        "youtubeを隠して",
        "youtubeをバックグラウンドにして",
        "youtubeをバックグラウンドに",
        "システムyoutubeを最小化して",
        "システムyoutubeを非表示にして",
        "システムyoutubeを隠して",
        "システムyoutubeをバックグラウンドにして",
    ):
        return VoiceCommand(intent="youtube_minimize", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("youtubeホーム", "youtubeホーム画面", "youtubeのホーム画面に戻って", "youtubeのホームに移動して"):
        return VoiceCommand(intent="youtube_home", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("ニュースライブ", "ニュースライブ再生", "ライブニュース再生", "ニュース再生", "ニュースを再生して"):
        return VoiceCommand(intent="news_live", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("朝のニュース", "朝ニュース", "朝のニュース再生", "朝のニュースを見たい"):
        return VoiceCommand(intent="news_morning", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in ("夕方のニュース", "夕方ニュース", "夕方のニュース再生", "夕方のニュースを見たい"):
        return VoiceCommand(intent="news_evening", normalized_text=normalized_alias, raw_text=raw)
    if normalized_alias in (
        "システム状況報告",
        "システム状態報告",
        "システム現状報告",
        "システム状況教えて",
        "システム状態教えて",
        "システム現状教えて",
        "システムステータス",
    ):
        return VoiceCommand(intent="system_status_report", normalized_text=normalized_alias, raw_text=raw)

    return None


VoiceCommand = ArouterVoiceCommand
normalize_transcript = arouter_normalize_transcript
extract_password_unlock_secret = arouter_extract_password_unlock_secret
parse_command = arouter_parse_command
detect_non_command_reaction = arouter_detect_non_command_reaction


def run_cmd(cmd: list[str], *, check: bool = True, capture_output: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=capture_output, env=env)


def shell_join(args: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in args)


def http_json(url: str, *, timeout: float = 2.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_ok(url: str, *, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def desktop_env(*, display: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    if "XDG_RUNTIME_DIR" not in env:
        candidate = f"/run/user/{os.getuid()}"
        if os.path.isdir(candidate):
            env["XDG_RUNTIME_DIR"] = candidate
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        xdg_runtime = env.get("XDG_RUNTIME_DIR")
        if xdg_runtime:
            bus = os.path.join(xdg_runtime, "bus")
            if os.path.exists(bus):
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    return env


def trim_notify_text(text: str, *, limit: int = 240) -> str:
    return arouter_trim_notify_text(text, limit=limit)


def compose_overlay_notify_text(title: str, body: str) -> str:
    return arouter_compose_overlay_notify_text(title, body)


def build_overlay_ipc_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class OverlayWaitHandle:
    def __init__(self, thread: threading.Thread) -> None:
        self._thread = thread

    def wait(self, timeout: float | None = None) -> None:
        self._thread.join(timeout=timeout)


class CaptionOverlayIpcClient:
    def __init__(
        self,
        *,
        enabled: bool,
        host: str,
        port: int,
        timeout_sec: float,
        logger,
    ) -> None:
        self.enabled = enabled
        self.host = host
        self.port = int(port)
        self.timeout_sec = float(timeout_sec)
        self.log = logger

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    def prepare(self) -> None:
        if not self.enabled:
            return
        self.log(f"caption overlay IPC enabled: {self.endpoint} timeoutSec={self.timeout_sec:.1f}")

    def _request(self, payload: dict[str, Any], *, timeout_sec: float | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("caption overlay IPC disabled")
        timeout = float(timeout_sec if timeout_sec is not None else self.timeout_sec)
        with socket.create_connection((self.host, self.port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(build_overlay_ipc_line(payload))
            sock.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                try:
                    part = sock.recv(4096)
                except socket.timeout as e:
                    raise RuntimeError(f"overlay IPC timeout waiting response from {self.endpoint}") from e
                if not part:
                    break
                chunks.append(part)
                if b"\n" in part:
                    break
        raw = b"".join(chunks).strip()
        if not raw:
            raise RuntimeError("overlay IPC empty response")
        try:
            resp = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"overlay IPC invalid JSON response: {raw[:200]!r}") from e
        if not bool(resp.get("ok", False)):
            msg = resp.get("error") or "unknown overlay IPC error"
            raise RuntimeError(f"overlay IPC request failed: {msg}")
        return resp

    def speak(self, *, text: str, wav_path: Path, wait: bool = False) -> OverlayWaitHandle | None:
        payload = {
            "type": "speak",
            "text": str(text),
            "wav_path": str(wav_path),
            # Use completion wait on the server side so Python can optionally wait later.
            "wait": True,
        }
        timeout = max(self.timeout_sec, 45.0)
        if wait:
            self._request(payload, timeout_sec=timeout)
            return None

        err_box: dict[str, str] = {}

        def _runner() -> None:
            try:
                self._request(payload, timeout_sec=timeout)
            except Exception as e:  # pragma: no cover - desktop IPC failures are environment-dependent
                err_box["error"] = str(e)
                self.log(f"overlay speak request error: {e}")

        th = threading.Thread(target=_runner, name="caption-overlay-ipc-speak", daemon=True)
        th.start()
        return OverlayWaitHandle(th)

    def notify(self, *, text: str, duration_ms: int) -> None:
        payload = {
            "type": "notify",
            "text": str(text),
            "duration_ms": max(300, int(duration_ms)),
        }
        self._request(payload, timeout_sec=max(self.timeout_sec, 5.0))

    def show_lock_screen(self, *, text: str) -> None:
        if not self.enabled:
            return
        payload = {
            "type": "lock_screen_show",
            "text": str(text),
        }
        self._request(payload, timeout_sec=max(self.timeout_sec, 5.0))

    def hide_lock_screen(self) -> None:
        if not self.enabled:
            return
        payload = {
            "type": "lock_screen_hide",
        }
        self._request(payload, timeout_sec=max(self.timeout_sec, 5.0))


class CdpClient:
    def __init__(self, ws_url: str, *, timeout_sec: float = 5.0) -> None:
        self.ws_url = ws_url
        self.timeout_sec = timeout_sec
        # Chrome/Chromium DevTools can reject websocket Origin headers unless
        # --remote-allow-origins is set. Suppress Origin to work with VacuumTube's
        # current remote debugging setup.
        self.ws = websocket.create_connection(ws_url, timeout=timeout_sec, suppress_origin=True)
        self.ws.settimeout(timeout_sec)
        self._id = 0

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def __enter__(self) -> "CdpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        req_id = self._id
        payload = {"id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.ws.send(json.dumps(payload))
        while True:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                raise RuntimeError(f"CDP {method} error: {msg['error']}")
            return msg

    def enable_basics(self) -> None:
        for method in ("Runtime.enable", "Page.enable"):
            try:
                self.call(method)
            except Exception:
                pass

    def evaluate(self, expression: str, *, await_promise: bool = True) -> Any:
        msg = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
        )
        result = (msg.get("result") or {}).get("result") or {}
        if "value" in result:
            return result["value"]
        return result

    def mouse_click(self, x: float, y: float) -> None:
        self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})
        self.call(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
        )
        self.call(
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
        )


class VoiceVoxSpeaker:
    def __init__(
        self,
        *,
        base_url: str,
        speaker: int,
        volume_scale: float,
        speed_scale: float,
        sink: str | None,
        cache_dir: str,
        enabled: bool,
        overlay_client: CaptionOverlayIpcClient | None,
        logger,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.speaker = speaker
        self.volume_scale = volume_scale
        self.speed_scale = speed_scale
        self.log = logger
        self.sink = sink or self._default_sink()
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.overlay = overlay_client
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _audio_env(self) -> dict[str, str]:
        return desktop_env()

    def _default_sink(self) -> str | None:
        env = self._audio_env()
        try:
            cp = run_cmd(["pactl", "info"], env=env)
            for line in cp.stdout.splitlines():
                if line.startswith("Default Sink: "):
                    sink = line.split(": ", 1)[1].strip()
                    if sink:
                        return sink
        except Exception:
            pass
        try:
            cp = run_cmd(["pactl", "list", "short", "sinks"], env=env)
            sinks: list[str] = []
            for line in cp.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    sinks.append(parts[1])
            for s in sinks:
                if "hdmi" in s.lower():
                    return s
            for s in sinks:
                if ".monitor" not in s.lower():
                    return s
        except Exception:
            pass
        return None

    def ready(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/version", timeout=2.0) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    def _synth_to_file(self, text: str, out_path: Path) -> None:
        q_url = (
            f"{self.base_url}/audio_query?text={urllib.parse.quote(text)}&speaker={self.speaker}"
        )
        q_req = urllib.request.Request(q_url, method="POST")
        with urllib.request.urlopen(q_req, timeout=10.0) as resp:
            query = json.loads(resp.read().decode("utf-8"))
        query["volumeScale"] = self.volume_scale
        query["speedScale"] = self.speed_scale
        body = json.dumps(query).encode("utf-8")
        s_url = f"{self.base_url}/synthesis?speaker={self.speaker}"
        s_req = urllib.request.Request(
            s_url,
            method="POST",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(s_req, timeout=20.0) as resp:
            wav = resp.read()
        out_path.write_bytes(wav)

    def _cache_path(self, text: str) -> Path:
        key = hashlib.sha1(
            f"{self.speaker}|{self.volume_scale}|{self.speed_scale}|{text}".encode("utf-8")
        ).hexdigest()[:16]
        return self.cache_dir / f"ack-{key}.wav"

    def prepare(self, texts: list[str]) -> None:
        if not self.enabled:
            return
        if self.overlay and self.overlay.enabled:
            self.log(f"VOICEVOX overlay IPC target: {self.overlay.endpoint}")
        self.log(f"VOICEVOX audio sink: {self.sink or '<none>'}")
        self.log(f"VOICEVOX params: speaker={self.speaker} volumeScale={self.volume_scale} speedScale={self.speed_scale}")
        if not self.ready():
            self.log("VOICEVOX not ready; continuing without voice")
            self.enabled = False
            return
        for t in texts:
            p = self._cache_path(t)
            if p.exists() and p.stat().st_size > 44:
                continue
            try:
                self._synth_to_file(t, p)
                self.log(f"VOICEVOX cached: {p}")
            except Exception as e:
                self.log(f"VOICEVOX cache error: {e}")
                self.enabled = False
                return

    def speak(self, text: str, *, wait: bool = False) -> Any | None:
        if not self.enabled:
            return None
        wav = self._cache_path(text)
        try:
            if not wav.exists() or wav.stat().st_size <= 44:
                self._synth_to_file(text, wav)
        except Exception as e:
            self.log(f"VOICEVOX synth error: {e}")
            return None
        if self.overlay and self.overlay.enabled:
            try:
                return self.overlay.speak(text=text, wav_path=wav, wait=wait)
            except Exception as e:
                self.log(f"overlay speak failed; fallback to paplay: {e}")
        if not self.sink:
            self.sink = self._default_sink()
        if not self.sink:
            self.log("VOICEVOX speak skipped: no sink")
            return None
        cmd = ["paplay", "--device", self.sink, str(wav)]
        env = self._audio_env()
        try:
            if wait:
                run_cmd(cmd, capture_output=True, env=env)
                return None
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except Exception as e:
            self.log(f"paplay error: {e}")
            return None


class DesktopNotifier:
    def __init__(
        self,
        *,
        enabled: bool,
        display: str | None,
        timeout_ms: int,
        app_name: str,
        overlay_client: CaptionOverlayIpcClient | None,
        logger,
        find_binary=shutil.which,
        run_command=run_cmd,
        env_builder=desktop_env,
    ) -> None:
        self.log = logger
        self.enabled = enabled
        self.display = display
        self.timeout_ms = max(0, int(timeout_ms))
        self.app_name = app_name
        self.overlay = overlay_client
        self._run_command = run_command
        self._env_builder = env_builder
        self._notify_send = find_binary("notify-send") if enabled else None
        if self.enabled and not self._notify_send and not (self.overlay and self.overlay.enabled):
            self.log("notify-send not found; desktop notifications disabled")
            self.enabled = False

    def prepare(self) -> None:
        if not self.enabled:
            return
        if self.overlay and self.overlay.enabled:
            self.log(f"desktop overlay notify enabled: endpoint={self.overlay.endpoint} timeoutMs={self.timeout_ms}")
        self.log(f"desktop notify enabled: display={self.display or '<inherit>'} timeoutMs={self.timeout_ms}")

    def notify(self, title: str, body: str = "", *, urgency: str = "normal") -> None:
        if not self.enabled:
            return
        if self.overlay and self.overlay.enabled:
            try:
                self.overlay.notify(
                    text=compose_overlay_notify_text(title, body),
                    duration_ms=self.timeout_ms,
                )
                return
            except Exception as e:
                self.log(f"overlay notify failed; fallback to notify-send: {e}")
        if not self._notify_send:
            return
        cmd = [
            self._notify_send,
            "-a",
            self.app_name,
            "-u",
            urgency,
            "-t",
            str(self.timeout_ms),
            "-h",
            "string:x-canonical-private-synchronous:voice-command-loop",
            trim_notify_text(title, limit=80) or "音声コマンド",
        ]
        body_trimmed = trim_notify_text(body, limit=240)
        if body_trimmed:
            cmd.append(body_trimmed)
        try:
            self._run_command(
                cmd,
                check=True,
                text=True,
                capture_output=True,
                timeout=2.0,
                env=self._env_builder(display=self.display),
            )
        except Exception as e:
            self.log(f"notify-send error: {e}")


class VacuumTubeController:
    def __init__(
        self,
        *,
        cdp_host: str,
        cdp_port: int,
        start_script: str,
        tmux_session: str,
        display: str,
        xauthority: str | None,
        target_x: int,
        target_y: int,
        target_w: int,
        target_h: int,
        geometry_tolerance: int,
        logger,
    ) -> None:
        self.cdp_host = cdp_host
        self.cdp_port = cdp_port
        self.start_script = str(Path(start_script).expanduser())
        self.tmux_session = tmux_session
        self.display = display
        self.xauthority = str(Path(xauthority).expanduser()) if xauthority else None
        self.target_geometry = {"x": target_x, "y": target_y, "w": target_w, "h": target_h}
        self.geometry_tolerance = geometry_tolerance
        self.log = logger
        self._last_weather_window_ids: list[str] = []
        self._resolved_display: str | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.cdp_host}:{self.cdp_port}"

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    @property
    def _weather_desktop_tiles(self) -> list[dict[str, Any]]:
        return WEATHER_DESKTOP_TILES

    def _http_json(self, url: str, *, timeout: float = 2.0) -> Any:
        return http_json(url, timeout=timeout)

    def _create_cdp_client(self, ws_url: str) -> CdpClient:
        return CdpClient(ws_url)

    def _time_now(self) -> float:
        return time.time()

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def _send_return_key(self) -> None:
        self.send_key("Return")

    def _send_space_key(self) -> None:
        self.send_key("space")

    def _open_bgm_from_home(self, cdp: CdpClient) -> str:
        return arouter_run_vacuumtube_open_from_home_host_runtime(
            cdp=cdp,
            runtime=self,
            label="BGM",
            scorer=score_vacuumtube_bgm_tile,
            filter_fn=None,
            allow_soft_playback_confirm=True,
        )

    def _open_news_from_home(
        self,
        cdp: CdpClient,
        *,
        slot: str,
    ) -> str:
        return arouter_run_vacuumtube_open_from_home_host_runtime(
            cdp=cdp,
            runtime=self,
            label=f"NEWS-{slot.upper()}",
            scorer=lambda tile: score_vacuumtube_news_tile(tile, slot=slot),
            filter_fn=lambda tile: looks_like_vacuumtube_news_blob(
                f"{tile.get('title') or ''} {tile.get('text') or ''}",
                slot=slot,
                has_ja_live_badge=bool(tile.get("hasJaLiveBadge")),
            ),
            allow_soft_playback_confirm=True,
        )

    def cdp_ready(self) -> bool:
        return http_get_ok(self._url("/json/version"), timeout=1.5)

    def wait_cdp_ready(self, timeout_sec: float = 25.0) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.cdp_ready():
                return True
            time.sleep(0.4)
        return False

    def _tmux_has(self) -> bool:
        return arouter_run_tmux_has_session_host_runtime(runtime=self)

    def _env_for_display(self, display: str) -> dict[str, str]:
        return arouter_build_x11_env(display=display, xauthority=self.xauthority)

    def _probe_display(self, display: str) -> bool:
        return arouter_probe_x11_display_host_runtime(runtime=self, display=display)

    def _resolve_display(self) -> str:
        return arouter_resolve_x11_display_host_runtime(runtime=self, label="VACUUMTUBE")

    def _start_in_tmux(self) -> None:
        return arouter_run_vacuumtube_tmux_start_host_runtime(runtime=self)

    def _restart_tmux_session(self) -> None:
        return arouter_run_vacuumtube_tmux_restart_host_runtime(runtime=self)

    def ensure_running(self) -> None:
        return arouter_run_vacuumtube_runtime_ready_host_runtime(runtime=self)

    def recover_from_unresponsive_state(self) -> dict[str, Any]:
        return arouter_run_vacuumtube_recover_from_unresponsive_host_runtime(runtime=self)

    def _wmctrl_lines(self, *, geometry: bool = False) -> list[str]:
        return arouter_run_wmctrl_list_host_runtime_query(
            runtime=self,
            geometry=geometry,
            with_pid=False,
        )

    def _x11_env(self) -> dict[str, str]:
        return self._env_for_display(self._resolve_display())

    def _live_camera_instance_specs(self) -> list[dict[str, Any]]:
        return list(self.instances)

    def _chromium_window_ids(self) -> set[str]:
        return arouter_chromium_window_ids_from_wmctrl_lines(self._wmctrl_lines())

    def _window_title_from_wmctrl(self, win_id: str) -> str:
        return arouter_run_window_title_host_runtime_query(runtime=self, win_id=win_id)

    def _launch_chromium_new_window(self, url: str) -> None:
        return arouter_run_launch_chromium_new_window_host_runtime(runtime=self, url=url)

    def _detect_new_chromium_window(self, before_ids: set[str], *, timeout_sec: float = 15.0) -> str:
        return arouter_run_detect_new_window_id_host_runtime(
            runtime=self,
            before_ids=before_ids,
            timeout_sec=timeout_sec,
        )

    def _active_window_id_from_xdotool(self) -> str | None:
        return arouter_run_active_window_id_host_runtime_query(runtime=self)

    def _move_window_to_geometry(self, win_id: str, geom: dict[str, int]) -> dict[str, Any]:
        self._clear_fullscreen_if_needed(win_id)
        self.activate_window(win_id)
        time.sleep(0.15)
        self._wmctrl_move_resize(win_id, geom)
        time.sleep(0.25)
        self._wmctrl_move_resize(win_id, geom)
        time.sleep(0.2)
        return {
            "window_id": win_id,
            "target": dict(geom),
            "actual": self.get_window_geometry(win_id),
            "title": self._window_title_from_wmctrl(win_id),
        }

    def open_weather_pages_tiled(self) -> str:
        return arouter_run_weather_pages_tiled_host_runtime(runtime=self)

    def _wmctrl_close_window(self, win_id: str) -> None:
        return arouter_run_window_close_host_runtime(runtime=self, win_id=win_id)

    def _looks_like_weather_chromium_title(self, title: str) -> bool:
        return arouter_looks_like_weather_chromium_title(title)

    def close_weather_pages_tiled(self) -> str:
        return arouter_run_weather_pages_closed_host_runtime(runtime=self)

    def find_window_id(self) -> str | None:
        return arouter_run_vacuumtube_window_id_host_runtime_query(
            runtime=self,
            listen_port=int(self.cdp_port),
        )

    def get_window_geometry(self, win_id: str | None = None) -> dict[str, int] | None:
        target = (win_id or self.find_window_id() or "").lower()
        if not target:
            return None
        return arouter_run_window_geometry_host_runtime_query(runtime=self, win_id=target)

    def wait_window(self, timeout_sec: float = 20.0) -> str:
        return arouter_run_wait_for_window_id_host_runtime(
            runtime=self,
            timeout_sec=timeout_sec,
        )

    def activate_window(self, win_id: str) -> None:
        return arouter_run_window_activate_host_runtime(runtime=self, win_id=win_id)

    def send_key(self, key: str) -> None:
        win_id = self.wait_window()
        self.activate_window(win_id)
        return arouter_run_window_key_host_runtime(
            runtime=self,
            win_id=win_id,
            key=key,
        )

    def tile_top_right(self) -> None:
        win_id = self.wait_window()
        self.activate_window(win_id)
        return arouter_run_kwin_shortcut_host_runtime(
            runtime=self,
            shortcut_name="Window Quick Tile Top Right",
        )

    def _wmctrl_move_resize(self, win_id: str, geom: dict[str, int]) -> None:
        return arouter_run_window_move_resize_host_runtime(
            runtime=self,
            win_id=win_id,
            geom=geom,
        )

    def _clear_fullscreen_if_needed(self, win_id: str) -> None:
        return arouter_run_window_fullscreen_host_runtime(
            runtime=self,
            win_id=win_id,
            enabled=False,
        )

    def _set_fullscreen(self, win_id: str, *, enabled: bool) -> None:
        return arouter_run_window_fullscreen_host_runtime(
            runtime=self,
            win_id=win_id,
            enabled=enabled,
        )

    def _is_fullscreen(self, win_id: str) -> bool:
        return arouter_read_window_fullscreen_state_host_runtime(
            runtime=self,
            win_id=win_id,
        )

    def _wait_fullscreen(self, win_id: str, *, enabled: bool, timeout_sec: float = 3.0) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                if self._is_fullscreen(win_id) == enabled:
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _capture_window_presentation(self, win_id: str | None = None) -> dict[str, Any]:
        wid = win_id or self.find_window_id()
        if not wid:
            return arouter_build_window_presentation_snapshot(window_id=None, fullscreen=False)
        fullscreen = False
        try:
            fullscreen = self._is_fullscreen(wid)
        except Exception:
            fullscreen = False
        return arouter_build_window_presentation_snapshot(window_id=wid, fullscreen=bool(fullscreen))

    def _desktop_size(self) -> tuple[int, int] | None:
        try:
            return arouter_run_desktop_size_host_runtime_query(runtime=self)
        except Exception:
            return None

    def _detect_screen_size(self) -> tuple[int, int] | None:
        try:
            return arouter_run_screen_size_host_runtime_query(runtime=self)
        except Exception:
            return self._desktop_size()

    def _detect_work_area(self) -> tuple[int, int, int, int] | None:
        return arouter_run_work_area_host_runtime_query(runtime=self)

    def _top_right_region_from_screen_and_work_area(
        self,
        *,
        screen_w: int,
        screen_h: int,
        work_area: tuple[int, int, int, int] | None,
    ) -> tuple[int, int, int, int]:
        return arouter_top_right_region_from_screen_and_work_area(
            screen_w=screen_w,
            screen_h=screen_h,
            work_area=work_area,
        )

    def expected_top_right_geometry(self) -> dict[str, int]:
        return arouter_resolve_expected_top_right_geometry(
            screen=self._detect_screen_size(),
            work_area=self._detect_work_area(),
            fallback_geometry=dict(self.target_geometry),
        )

    def _pid_listening_on_tcp_port(self, port: int) -> int | None:
        return arouter_run_listen_pid_host_runtime_query(port)

    def _kwin_set_frame_geometry_for_pid(
        self,
        *,
        pid: int,
        geom: dict[str, int],
        no_border: bool = True,
    ) -> None:
        plugin_name = f"codex_vacuumtube_main_{int(pid)}_{int(time.time() * 1000) % 1000000}"
        return arouter_run_window_frame_geometry_host_runtime(
            runtime=self,
            pid=pid,
            geom=geom,
            no_border=no_border,
            plugin_name=plugin_name,
        )

    def _current_window_is_fullscreenish(self, win_id: str, *, tol: int = 32) -> bool:
        try:
            if self._is_fullscreen(win_id):
                return True
        except Exception:
            pass

        geom = self.get_window_geometry(win_id)
        desktop = self._desktop_size()
        return arouter_is_window_fullscreenish(geom, desktop, tol=tol)

    def _restore_window_presentation(self, presentation: dict[str, Any] | None, *, label: str = "VacuumTube") -> None:
        fallback_window_id = self.find_window_id() or self.wait_window()
        flow = arouter_run_window_restore_host_runtime_flow(
            runtime=self,
            presentation=presentation,
            fallback_window_id=str(fallback_window_id),
        )
        action = str(flow["action"])
        win_id = str(flow["window_id"])

        if action == "fullscreen":
            self.log(
                f"{label} presentation restore fullscreen: "
                + json.dumps(
                    {
                        "window_id": win_id,
                        "fullscreen": bool(flow.get("fullscreen")),
                        "after": flow.get("after"),
                    },
                    ensure_ascii=False,
                )
            )
            return

        if action == "skip_top_right":
            self.log(
                f"{label} presentation restore guard: current window looks fullscreen; skip top-right resize"
            )
            return

        pos = flow.get("position")
        self.log(f"{label} presentation restore top-right: {json.dumps(pos, ensure_ascii=False)}")

    def ensure_top_right_position(self, *, retries: int = 2) -> dict[str, Any]:
        win_id = self.wait_window()
        self.activate_window(win_id)
        target = self.expected_top_right_geometry()
        before = self.get_window_geometry(win_id)
        main_pid = self._pid_listening_on_tcp_port(int(self.cdp_port))
        return arouter_run_top_right_position_host_runtime_flow(
            runtime=self,
            win_id=win_id,
            target=target,
            before=before,
            retries=retries,
            main_pid=main_pid,
        )

    def _json_list(self) -> list[dict[str, Any]]:
        return arouter_run_vacuumtube_target_list_host_runtime_query(runtime=self)

    def _pick_page_target(self) -> dict[str, Any]:
        return arouter_run_vacuumtube_page_target_host_runtime_query(runtime=self)

    def _cdp(self) -> CdpClient:
        return arouter_run_vacuumtube_page_cdp_host_runtime(runtime=self)

    def _state(self, cdp: CdpClient) -> dict[str, Any]:
        return arouter_run_vacuumtube_state_host_runtime_query(cdp=cdp)

    def _hide_overlay_if_needed(self, cdp: CdpClient) -> None:
        try:
            arouter_run_vacuumtube_hide_overlay_host_runtime(cdp=cdp)
        except Exception:
            pass

    def _enumerate_tiles(self, cdp: CdpClient) -> list[dict[str, Any]]:
        return arouter_run_vacuumtube_enumerate_tiles_host_runtime(cdp=cdp)

    def _score_bgm_tile(self, tile: dict[str, Any]) -> float:
        title = str(tile.get("title") or "")
        text = str(tile.get("text") or "")
        blob = _norm_blob(title + " " + text)
        score = 0.0
        if tile.get("visible"):
            score += 5.0
        # Prefer title-rich rows.
        score += min(len(title), 120) / 40.0
        for kw in BGM_POSITIVE_KEYWORDS:
            if kw in blob:
                score += 3.0
        for kw in BGM_NEGATIVE_KEYWORDS:
            if kw in blob:
                score -= 4.0
        # Slight bias toward upper rows on the home screen.
        try:
            y = float(tile.get("y") or 0)
            score += max(0.0, 2.0 - min(y, 1600.0) / 800.0)
        except Exception:
            pass
        return score

    def _score_news_tile(self, tile: dict[str, Any], *, slot: str = "generic") -> float:
        title = str(tile.get("title") or "")
        text = str(tile.get("text") or "")
        blob = _norm_blob(title + " " + text)
        has_ja_live_badge = bool(tile.get("hasJaLiveBadge"))
        has_ja_live_badge_bottom_right = bool(tile.get("hasJaLiveBadgeBottomRight"))
        score = 0.0
        if tile.get("visible"):
            score += 5.0
        score += min(len(title), 120) / 45.0

        news_hits = _count_hits(blob, NEWS_POSITIVE_KEYWORDS)
        bgm_hits = _count_hits(blob, BGM_POSITIVE_KEYWORDS)
        score += news_hits * 3.0
        score -= bgm_hits * 4.0
        # Freshness/live hints.
        fresh_hits = _count_hits(blob, ["ライブ", "live", "生放送", "配信中", "分前", "時間前", "minutes ago", "hours ago"])
        score += fresh_hits * 2.0
        if has_ja_live_badge:
            score += 5.0
        if has_ja_live_badge_bottom_right:
            score += 4.0

        if slot == "morning":
            score += _count_hits(blob, NEWS_MORNING_KEYWORDS) * 3.0
            score -= _count_hits(blob, NEWS_EVENING_KEYWORDS) * 1.5
        elif slot == "evening":
            score += _count_hits(blob, NEWS_EVENING_KEYWORDS) * 3.0
            score -= _count_hits(blob, NEWS_MORNING_KEYWORDS) * 1.5

        if not looks_like_news_blob(blob, slot=slot, has_ja_live_badge=has_ja_live_badge):
            score -= 10.0

        try:
            y = float(tile.get("y") or 0)
            score += max(0.0, 2.0 - min(y, 1600.0) / 850.0)
        except Exception:
            pass
        return score

    def _route_to_home(self, cdp: CdpClient) -> None:
        arouter_run_vacuumtube_route_to_home_host_runtime(cdp=cdp)

    def _hard_reload_home(self, cdp: CdpClient) -> None:
        arouter_run_vacuumtube_hard_reload_home_host_runtime(cdp=cdp)

    def _snapshot_state(self, cdp: CdpClient) -> dict[str, Any]:
        return arouter_run_vacuumtube_snapshot_state_host_runtime(runtime=self, cdp=cdp)

    def _is_watch_state(self, snapshot: dict[str, Any]) -> bool:
        return arouter_vacuumtube_is_watch_state(snapshot)

    def _video_playing(self, snapshot: dict[str, Any]) -> bool:
        return arouter_vacuumtube_video_playing(snapshot)

    def _video_current_time(self, snapshot: dict[str, Any]) -> float:
        return arouter_vacuumtube_video_current_time(snapshot)

    def _is_home_browse_state(self, snapshot: dict[str, Any]) -> bool:
        return arouter_vacuumtube_is_home_browse_state(snapshot)

    def _needs_hard_reload_home(self, snapshot: dict[str, Any]) -> bool:
        return arouter_vacuumtube_needs_hard_reload_home(snapshot)

    def _select_account_if_needed(self) -> None:
        arouter_run_vacuumtube_select_account_if_needed_host_runtime(runtime=self)

    def _ensure_home(self, cdp: CdpClient, *, timeout_sec: float = 8.0) -> dict[str, Any]:
        return arouter_run_vacuumtube_ensure_home_host_runtime(
            runtime=self,
            cdp=cdp,
            timeout_sec=timeout_sec,
        )

    def _try_resume_current_video(self, cdp: CdpClient) -> bool:
        return arouter_run_vacuumtube_try_resume_current_video_host_runtime(cdp=cdp)

    def _wait_confirmed_watch_playback(
        self,
        cdp: CdpClient,
        *,
        timeout_sec: float = 8.0,
        allow_resume_attempts: bool = True,
        allow_soft_confirm_when_unpaused: bool = False,
    ) -> dict[str, Any]:
        return arouter_run_vacuumtube_confirm_watch_playback_host_runtime(
            runtime=self,
            cdp=cdp,
            playback_confirmed=watch_playback_confirmed,
            timeout_sec=timeout_sec,
            allow_resume_attempts=allow_resume_attempts,
            allow_soft_confirm_when_unpaused=allow_soft_confirm_when_unpaused,
        )

    def _wait_watch_route(self, cdp: CdpClient, timeout_sec: float = 8.0) -> bool:
        return arouter_run_vacuumtube_wait_watch_route_host_runtime(
            runtime=self,
            cdp=cdp,
            timeout_sec=timeout_sec,
        )

    def _click_tile_center(self, cdp: CdpClient, tile: dict[str, Any]) -> None:
        arouter_run_vacuumtube_click_tile_center_host_runtime(cdp=cdp, tile=tile)

    def _dom_click_tile(self, cdp: CdpClient, tile: dict[str, Any]) -> bool:
        return arouter_run_vacuumtube_dom_click_tile_host_runtime(
            runtime=self,
            cdp=cdp,
            tile=tile,
        )

    def _open_from_home_by_score(
        self,
        cdp: CdpClient,
        *,
        label: str,
        scorer,
        filter_fn=None,
        allow_soft_playback_confirm: bool = False,
    ) -> str:
        return arouter_run_vacuumtube_open_from_home_host_runtime(
            cdp=cdp,
            runtime=self,
            label=label,
            scorer=scorer,
            filter_fn=filter_fn,
            allow_soft_playback_confirm=allow_soft_playback_confirm,
        )

    def ensure_started_and_positioned(self) -> dict[str, Any]:
        return arouter_ensure_vacuumtube_started_and_positioned_host_runtime(runtime=self)

    def play_bgm(self) -> str:
        self.ensure_started_and_positioned()
        return arouter_run_vacuumtube_play_bgm_host_runtime(runtime=self)

    def resume_playback(self) -> str:
        return arouter_run_vacuumtube_resume_playback_host_runtime(runtime=self)

    def play_news(self, *, slot: str = "generic") -> str:
        self.ensure_started_and_positioned()
        return arouter_run_vacuumtube_play_news_host_runtime(runtime=self, slot=slot)

    def go_youtube_home(self) -> str:
        presentation_before = self.ensure_started_and_positioned()
        return arouter_run_vacuumtube_go_home_host_runtime(
            runtime=self,
            presentation_before=presentation_before,
        )

    def youtube_fullscreen(self) -> str:
        return arouter_run_vacuumtube_fullscreen_host_runtime(runtime=self)

    def youtube_quadrant(self) -> str:
        return arouter_run_vacuumtube_quadrant_host_runtime(runtime=self)

    def youtube_minimize(self) -> str:
        return arouter_run_vacuumtube_minimize_host_runtime(runtime=self)

    def stop_music(self) -> str:
        return arouter_run_vacuumtube_stop_music_host_runtime(runtime=self)

    def good_night_pause(self) -> str:
        return arouter_run_vacuumtube_good_night_pause_host_runtime(runtime=self)


class LiveCamWallController:
    """Controls multiple silent VacuumTube instances for live camera wall layouts."""

    def __init__(
        self,
        *,
        display: str,
        xauthority: str | None,
        logger,
    ) -> None:
        self.display = display
        self.xauthority = str(Path(xauthority).expanduser()) if xauthority else None
        self.log = logger
        self._resolved_display: str | None = None
        self.workspace_root = _WORKSPACES_ROOT
        self.start_silent_script = (
            self.workspace_root
            / ".codex"
            / "skills"
            / "vacuumtube-silent-live-cam"
            / "scripts"
            / "start_silent_instance.sh"
        )
        self.fast_open_script = (
            self.workspace_root
            / ".codex"
            / "skills"
            / "vacuumtube-silent-live-cam"
            / "scripts"
            / "open_tv_channel_live_tile_fast.js"
        )
        self.instances: list[dict[str, Any]] = [
            {
                "label": "shibuya",
                "port": 9993,
                "session": "vacuumtube-bg-2",
                "instance_dir": str(Path.home() / ".cache/yuiclaw/vacuumtube-multi/instance2"),
                "keyword": "いまの渋谷",
                "browse_url": "https://www.youtube.com/tv/@FNNnewsCH/streams#/browse?c=UCoQBJMzcwmXrRSHBFAlTsIw",
                "verify_regex": "渋谷|スクランブル交差点|Shibuya",
            },
            {
                "label": "akihabara",
                "port": 9994,
                "session": "vacuumtube-bg-3",
                "instance_dir": str(Path.home() / ".cache/yuiclaw/vacuumtube-multi/instance3"),
                "keyword": "秋葉原ライブカメラ",
                "browse_url": "https://www.youtube.com/tv/@Cerevolivecamera/streams#/browse?c=UCrGS8VyrgCqYwaogH5bQpxQ",
                "verify_regex": "秋葉原|Akihabara",
            },
            {
                "label": "ikebukuro",
                "port": 9995,
                "session": "vacuumtube-bg-4",
                "instance_dir": str(Path.home() / ".cache/yuiclaw/vacuumtube-multi/instance4"),
                "keyword": "サンシャイン60通りライブカメラ",
                "browse_url": "https://www.youtube.com/tv/@%E3%82%B5%E3%83%B3%E3%82%B7%E3%83%A3%E3%82%A4%E3%83%B360%E9%80%9A%E3%82%8A%E3%83%A9%E3%82%A4%E3%83%96%E3%82%AB%E3%83%A1%E3%83%A9/streams#/browse?c=UCEloGRn_GCcr-I_6f5MYJPw",
                "verify_regex": "サンシャイン60通り|池袋|Sunshine|ikebukuro",
            },
            {
                "label": "asakusa",
                "port": 9996,
                "session": "vacuumtube-bg-5",
                "instance_dir": str(Path.home() / ".cache/yuiclaw/vacuumtube-multi/instance5"),
                "force_video_id": "urE7veQRlrQ",
                "keyword": "浅草・雷門前の様子",
                "browse_url": "https://www.youtube.com/tv/@tbsnewsdig/streams#/browse?c=UC6AG81pAkf6Lbi_1VC5NmPA",
                "verify_regex": "浅草|雷門|Asakusa",
                "fallbacks": [
                    {
                        "label": "minowa",
                        "keyword": "【LIVE】東京都台東区 大関横丁交差点(三ノ輪駅前) ライブカメラ",
                        "browse_url": "https://www.youtube.com/tv/@%E4%B8%89%E3%83%8E%E8%BC%AA%E9%A7%85%E5%89%8D%E3%83%A9%E3%82%A4%E3%83%96%E3%82%AB%E3%83%A1%E3%83%A9/streams#/browse?c=UC8HLYEGSvHBroUqZMcGaSHg",
                        "verify_regex": "大関横丁|東京都台東区",
                    },
                    {
                        "label": "yokohama",
                        "keyword": "横浜 みなとみらいのライブカメラ",
                        "verify_regex": "横浜|みなとみらい|Yokohama|Minatomirai",
                    },
                ],
            },
        ]

    def _env_for_display(self, display: str) -> dict[str, str]:
        return arouter_build_x11_env(display=display, xauthority=self.xauthority)

    def _probe_display(self, display: str) -> bool:
        return arouter_probe_x11_display_host_runtime(runtime=self, display=display)

    def _resolve_display(self) -> str:
        return arouter_resolve_x11_display_host_runtime(runtime=self, label="LIVE_CAM")

    def _x11_env(self) -> dict[str, str]:
        return self._env_for_display(self._resolve_display())

    def _live_camera_instance_specs(self) -> list[dict[str, Any]]:
        return list(self.instances)

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def _after_window_action_pause(self) -> None:
        self._sleep(0.2)

    def _run(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.log(f"LIVE_CAM exec: {shell_join(args)}")
        return subprocess.run(
            args,
            check=check,
            text=True,
            capture_output=True,
            env=env,
            cwd=cwd,
            timeout=timeout,
        )

    def _run_x11_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self._run(command, env=self._x11_env(), timeout=8.0)

    def _run_live_cam_start_command(
        self,
        command: list[str],
    ) -> subprocess.CompletedProcess[str]:
        return self._run(command, timeout=90.0)

    def _cleanup_temp_path(self, path: str) -> None:
        os.unlink(path)

    def _reopen_live_camera_specs(
        self,
        specs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return arouter_run_live_cam_reopen_specs_flow(
            specs,
            assign_live_camera=self._assign_live_camera,
            parallel_runner=self._run_instances_parallel,
        )

    def _resolve_layout_plan(
        self,
        mode: str,
        screen_w: int,
        screen_h: int,
        work_area: tuple[int, int, int, int] | None,
        pids_by_port: dict[int, int],
    ) -> dict[str, Any]:
        return arouter_resolve_live_cam_layout_plan(
            mode=mode,
            screen_w=screen_w,
            screen_h=screen_h,
            work_area=work_area,
            pids_by_port=pids_by_port,
            full_target_builder=self._layout_targets_full,
            compact_target_builder=self._layout_targets_compact,
        )

    def _apply_live_cam_layout(
        self,
        targets: list[dict[str, Any]],
        plugin_name: str,
        keep_above: bool,
        no_border: bool,
    ) -> None:
        self._kwin_apply_layout(
            targets=targets,
            plugin_name=plugin_name,
            keep_above=keep_above,
            no_border=no_border,
        )

    def _parse_kv_stdout(self, text: str) -> dict[str, str]:
        return arouter_parse_key_value_stdout(text)

    def _ensure_scripts_present(self) -> None:
        if not self.start_silent_script.exists():
            raise FileNotFoundError(f"start_silent_instance.sh not found: {self.start_silent_script}")
        if not self.fast_open_script.exists():
            raise FileNotFoundError(f"open_tv_channel_live_tile_fast.js not found: {self.fast_open_script}")

    def _start_instance(self, spec: dict[str, Any]) -> dict[str, Any]:
        return arouter_run_live_cam_start_script_host_runtime_flow(spec=spec, runtime=self)

    def _assign_live_camera(self, spec: dict[str, Any]) -> dict[str, Any]:
        return arouter_run_live_cam_payload_selection_host_runtime_flow(spec, runtime=self)

    def _pid_for_port(self, port: int) -> int | None:
        return arouter_run_listen_pid_host_runtime_query(port)

    def _http_json(self, url: str, *, timeout: float = 2.0) -> Any:
        return http_json(url, timeout=timeout)

    def _create_cdp_client(self, ws_url: str, *, timeout_sec: float = 4.0) -> CdpClient:
        return CdpClient(ws_url, timeout_sec=timeout_sec)

    def _fetch_live_cam_target_list(self, port: int) -> Any:
        return self._http_json(f"http://127.0.0.1:{int(port)}/json", timeout=2.0)

    def _open_live_cam_cdp_client(self, ws_url: str) -> CdpClient:
        return self._create_cdp_client(ws_url, timeout_sec=4.0)

    def _inspect_live_cam_target(self, target: dict[str, Any]) -> dict[str, Any] | None:
        return arouter_run_live_cam_target_snapshot_cdp_runtime(
            target=target,
            create_client=self._open_live_cam_cdp_client,
        )

    def _wmctrl_rows(self, *, geometry: bool = False, with_pid: bool = False) -> list[str]:
        return arouter_run_wmctrl_list_host_runtime_query(
            runtime=self,
            geometry=geometry,
            with_pid=with_pid,
        )

    def _window_id_for_pid(self, pid: int) -> str | None:
        return arouter_run_window_id_by_pid_title_host_runtime_query(
            runtime=self,
            pid=int(pid),
            title_hint="VacuumTube",
        )

    def _window_rows_by_pids(self, pids: list[int]) -> list[dict[str, Any]]:
        return list(arouter_run_window_rows_for_pids_host_runtime_query(runtime=self, pids=pids))

    def _detect_screen_size(self) -> tuple[int, int]:
        return arouter_run_screen_size_host_runtime_query(runtime=self)

    def _detect_work_area(self) -> tuple[int, int, int, int] | None:
        return arouter_run_work_area_host_runtime_query(runtime=self)

    def _kwin_apply_layout(
        self,
        *,
        targets: list[dict[str, Any]],
        plugin_name: str,
        keep_above: bool = True,
        no_border: bool = True,
    ) -> None:
        if not targets:
            raise RuntimeError("no layout targets")
        return arouter_run_live_cam_layout_host_runtime(
            targets,
            runtime=self,
            plugin_name=plugin_name,
            keep_above=keep_above,
            no_border=no_border,
        )

    def _raise_windows_for_pids(self, pids: list[int]) -> None:
        arouter_run_live_cam_raise_windows_host_runtime_flow(runtime=self, pids=pids)

    def _minimize_windows_for_pids(self, pids: list[int]) -> list[str]:
        return arouter_run_live_cam_minimize_windows_host_runtime_flow(runtime=self, pids=pids)

    def _close_windows_for_pids(self, pids: list[int]) -> list[str]:
        return arouter_run_live_cam_close_windows_host_runtime_flow(runtime=self, pids=pids)

    def _run_instances_parallel(
        self,
        specs: list[dict[str, Any]],
        *,
        worker,
        label: str,
    ) -> list[dict[str, Any]]:
        return arouter_run_live_cam_parallel(specs, worker=worker, label=label)

    def _ensure_instances_started(self) -> list[dict[str, Any]]:
        return arouter_run_live_cam_start_instances_host_runtime_flow(runtime=self)

    def _ensure_tokyo_targets_opened(self) -> list[dict[str, Any]]:
        return arouter_run_live_cam_open_instances_host_runtime_flow(runtime=self)

    def _layout_targets_full(
        self,
        *,
        screen_w: int,
        screen_h: int,
        pids_by_port: dict[int, int],
        origin_x: int = 0,
        origin_y: int = 0,
    ) -> list[dict[str, Any]]:
        return arouter_build_live_cam_layout_targets_full(
            screen_w=screen_w,
            screen_h=screen_h,
            pids_by_port=pids_by_port,
            origin_x=origin_x,
            origin_y=origin_y,
        )

    def _layout_targets_compact(
        self,
        *,
        screen_w: int,
        screen_h: int,
        pids_by_port: dict[int, int],
        origin_x: int = 0,
        origin_y: int = 0,
    ) -> list[dict[str, Any]]:
        return arouter_build_live_cam_layout_targets_compact(
            screen_w=screen_w,
            screen_h=screen_h,
            pids_by_port=pids_by_port,
            origin_x=origin_x,
            origin_y=origin_y,
        )

    def _compact_region_from_screen_and_work_area(
        self,
        *,
        screen_w: int,
        screen_h: int,
        work_area: tuple[int, int, int, int] | None,
    ) -> tuple[int, int, int, int]:
        return arouter_compact_live_cam_region_from_screen_and_work_area(
            screen_w=screen_w,
            screen_h=screen_h,
            work_area=work_area,
        )

    def _collect_runtime_state(self, pids_by_port: dict[int, int]) -> dict[str, Any]:
        return arouter_run_live_cam_runtime_state_host_runtime_query(
            runtime=self,
            pids_by_port=pids_by_port,
        )

    def _page_brief_for_port(self, port: int) -> dict[str, Any]:
        return arouter_run_live_cam_page_brief_host_runtime_flow(
            runtime=self,
            port=int(port),
        )

    def _page_matches_live_camera_spec(self, spec: dict[str, Any], page: dict[str, Any]) -> bool:
        return arouter_page_matches_live_camera_spec(spec, page)

    def _find_stuck_instances(self) -> list[dict[str, Any]]:
        """Return instances that are not on the expected live-camera watch page."""
        return arouter_run_live_cam_stuck_specs_host_runtime_query(runtime=self)

    def _existing_windowed_pids_by_port(self) -> dict[int, int] | None:
        return arouter_run_live_cam_existing_windowed_pids_host_runtime_query(runtime=self)

    def _apply_layout(self, *, mode: str) -> str:
        return arouter_run_live_cam_layout_host_runtime_flow(mode=mode, runtime=self)

    def show_full(self) -> str:
        return self._apply_layout(mode="full")

    def show_compact(self) -> str:
        return self._apply_layout(mode="compact")

    def hide(self) -> str:
        return arouter_run_live_cam_hide_host_runtime_flow(runtime=self)

    def minimize(self) -> str:
        return arouter_run_live_cam_minimize_host_runtime_flow(runtime=self)


class VoiceCommandLoop(base.ListenLoop):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        overlay_client_cls = (
            ExtractedCaptionOverlayIpcClient if _ACAPTION_CLIENT_AVAILABLE else CaptionOverlayIpcClient
        )
        self.overlay = overlay_client_cls(
            enabled=not getattr(args, "no_overlay", False),
            host=args.overlay_ipc_host,
            port=args.overlay_ipc_port,
            timeout_sec=args.overlay_ipc_timeout_sec,
            logger=self.log,
        )
        lock_overlay_client_cls = (
            ExtractedLockScreenIpcClient if _ASEC_CLIENT_AVAILABLE else CaptionOverlayIpcClient
        )
        lock_ipc_port = getattr(args, "lock_screen_ipc_port", None)
        if lock_ipc_port and not getattr(args, "no_overlay", False):
            self.lock_overlay = lock_overlay_client_cls(
                enabled=True,
                host=args.overlay_ipc_host,
                port=lock_ipc_port,
                timeout_sec=args.overlay_ipc_timeout_sec,
                logger=self.log,
            )
        else:
            self.lock_overlay = None
        notifier_cls = ExtractedDesktopNotifier
        self.notifier = notifier_cls(
            enabled=not args.no_notify,
            display=args.notify_display or args.vacuumtube_display,
            timeout_ms=args.notify_timeout_ms,
            app_name=args.notify_app_name,
            overlay_client=self.overlay,
            logger=self.log,
            env_builder=desktop_env,
        )
        voice_speaker_cls = ExtractedVoiceVoxSpeaker if _ASAY_VOICEVOX_AVAILABLE else VoiceVoxSpeaker
        self.voice = voice_speaker_cls(
            base_url=args.voicevox_url,
            speaker=args.voicevox_speaker,
            volume_scale=args.voicevox_volume_scale,
            speed_scale=args.voicevox_speed_scale,
            sink=args.audio_sink,
            cache_dir=args.voice_cache_dir,
            enabled=not args.no_voice,
            overlay_client=self.overlay,
            logger=self.log,
        )
        self.vacuumtube = VacuumTubeController(
            cdp_host=args.vacuumtube_cdp_host,
            cdp_port=args.vacuumtube_cdp_port,
            start_script=args.vacuumtube_start_script,
            tmux_session=args.vacuumtube_tmux_session,
            display=args.vacuumtube_display,
            xauthority=args.vacuumtube_xauthority,
            target_x=args.vacuumtube_target_x,
            target_y=args.vacuumtube_target_y,
            target_w=args.vacuumtube_target_w,
            target_h=args.vacuumtube_target_h,
            geometry_tolerance=args.vacuumtube_geometry_tolerance,
            logger=self.log,
        )
        self.live_cam_wall = LiveCamWallController(
            display=args.vacuumtube_display,
            xauthority=args.vacuumtube_xauthority,
            logger=self.log,
        )
        self._last_ack_proc: Any | None = None
        self._action_error_voice_text = "操作に失敗しました。もう一度試してください。"
        self._god_mode_last_layout: str | None = None
        self._live_cam_last_layout: str | None = None
        self._vacuumtube_context_lock = threading.Lock()
        self._vacuumtube_context: dict[str, Any] = {"ts": 0.0}
        self._vacuumtube_context_stop_event = threading.Event()
        self._vacuumtube_context_thread: threading.Thread | None = None

        # ── Speaker ID (ECAPA-TDNN) initialization ────────────────────────────
        self._initialize_speaker_auth(args)

        self._ensure_biometric_runtime_attrs()
        if self._biometric_lock_enabled() and bool(getattr(args, "biometric_start_locked", False)):
            self._set_system_locked(True, reason="startup")

    def _initialize_speaker_auth(self, args: argparse.Namespace) -> None:
        self.speaker_classifier = None
        self.master_voiceprint = None
        self._speaker_np = None
        self._speaker_torch = None
        self._speaker_torchaudio = None
        self._speaker_device = getattr(args, "speaker_device", "cpu")
        if _AHEAR_SPEAKER_AUTH_AVAILABLE:
            runtime = arouter_run_speaker_auth_initialization(
                enabled=bool(getattr(args, "speaker_id", False)),
                requested_device=self._speaker_device,
                speaker_master=str(getattr(args, "speaker_master", "")),
                logger=self.log,
                initialize_runtime=extracted_initialize_speaker_auth_runtime,
            )
            self.speaker_classifier = runtime["classifier"]
            self.master_voiceprint = runtime["voiceprint"]
            self._speaker_np = runtime["np_module"]
            self._speaker_torch = runtime["torch_module"]
            self._speaker_torchaudio = runtime["torchaudio_module"]
            self._speaker_device = runtime["device"]

    def _biometric_runtime_adapter(self) -> Any:
        return ExtractedBiometricRuntimeAdapter(
            runtime=self,
            prefer_arouter_helpers=_AROUTER_AVAILABLE,
            asee_client_available=_ASEE_BIOMETRIC_CLIENT_AVAILABLE,
            default_lock_signal_file=DEFAULT_BIOMETRIC_LOCK_SIGNAL_FILE,
            default_unlock_signal_file=DEFAULT_BIOMETRIC_UNLOCK_SIGNAL_FILE,
            default_password_file=DEFAULT_BIOMETRIC_PASSWORD_FILE,
            default_password_private_key=DEFAULT_BIOMETRIC_PASSWORD_PRIVATE_KEY,
            default_lock_screen_text=arouter_default_lock_screen_text,
            default_locked_denied_text=arouter_default_locked_denied_text,
            biometric_lock_enabled=arouter_biometric_lock_enabled,
            biometric_unlock_success_text=arouter_biometric_unlock_success_text,
            ensure_biometric_runtime_attrs=arouter_ensure_biometric_runtime_attrs,
            resolve_biometric_arg_path=arouter_resolve_biometric_arg_path,
            seed_signal_seen_mtime=arouter_seed_signal_seen_mtime,
            set_system_locked=arouter_set_system_locked,
            reassert_lock_screen=arouter_reassert_lock_screen,
            unlock_requires_live_voice_text=arouter_unlock_requires_live_voice_text,
            unlock_requires_speaker_auth_text=arouter_unlock_requires_speaker_auth_text,
            unlock_requires_face_auth_text=arouter_unlock_requires_face_auth_text,
            unlock_requires_password_text=arouter_unlock_requires_password_text,
            run_biometric_status_url_fetch=arouter_run_biometric_status_url_fetch,
            run_biometric_status_client_get=arouter_run_biometric_status_client_get,
            run_biometric_status_runtime_fetch=arouter_run_biometric_status_runtime_fetch,
            run_biometric_password_candidate_load=arouter_run_biometric_password_candidate_load,
            load_password_candidates=arouter_load_password_candidates,
            verify_unlock_password=arouter_verify_unlock_password,
            run_biometric_signal_consume=arouter_run_biometric_signal_consume,
            consume_signal_file=arouter_consume_signal_file,
            record_successful_command_activity=arouter_record_successful_command_activity,
            run_biometric_owner_face_absent_runtime_check=arouter_run_biometric_owner_face_absent_runtime_check,
            run_biometric_owner_face_recent_runtime_check=arouter_run_biometric_owner_face_recent_runtime_check,
            maybe_unlock_from_signal=arouter_maybe_unlock_from_signal,
            maybe_lock_from_signal=arouter_maybe_lock_from_signal,
            maybe_auto_lock=arouter_maybe_auto_lock,
            authorize_command=arouter_authorize_command,
            resolve_biometric_poll_interval=arouter_resolve_biometric_poll_interval,
            run_biometric_poller_loop=arouter_run_biometric_poller_loop,
            run_biometric_poll_iteration=arouter_run_biometric_poll_iteration,
            start_biometric_poller=arouter_start_biometric_poller,
            stop_biometric_poller=arouter_stop_biometric_poller,
            resolve_remote_status_client=asee_resolve_remote_biometric_status_client,
            fetch_remote_status=asee_fetch_remote_biometric_status,
            owner_face_absent_from_status=asee_owner_face_absent_for_lock_from_status,
            owner_face_recent_from_status=asee_owner_face_recent_for_unlock_from_status,
            request_builder=urllib.request.Request,
            urlopen=urllib.request.urlopen,
            json_loads=json.loads,
            normalize_transcript=normalize_transcript,
            now=time.time,
            lock_factory=threading.Lock,
            event_factory=threading.Event,
            thread_factory=threading.Thread,
        )

    def _biometric_lock_enabled(self) -> bool:
        return self._biometric_runtime_adapter()._biometric_lock_enabled()

    def _ensure_biometric_runtime_attrs(self) -> None:
        self._biometric_runtime_adapter()._ensure_biometric_runtime_attrs()

    def _seed_signal_seen_mtime(self, *, signal_arg_name: str, default_path: str) -> float:
        return self._biometric_runtime_adapter()._seed_signal_seen_mtime(
            signal_arg_name=signal_arg_name,
            default_path=default_path,
        )

    def _lock_screen_text(self) -> str:
        return self._biometric_runtime_adapter()._lock_screen_text()

    def _set_system_locked(self, locked: bool, *, reason: str) -> bool:
        return self._biometric_runtime_adapter()._set_system_locked(locked, reason=reason)

    def _locked_denied_text(self) -> str:
        return self._biometric_runtime_adapter()._locked_denied_text()

    def _reassert_lock_screen(self, *, reason: str) -> bool:
        return self._biometric_runtime_adapter()._reassert_lock_screen(reason=reason)

    def _log_auth_decision(
        self,
        *,
        cmd: VoiceCommand,
        source: str,
        outcome: str,
        detail: str,
    ) -> None:
        self._biometric_runtime_adapter()._log_auth_decision(
            cmd=cmd,
            source=source,
            outcome=outcome,
            detail=detail,
        )

    def _unlock_requires_live_voice_text(self) -> str:
        return self._biometric_runtime_adapter()._unlock_requires_live_voice_text()

    def _unlock_requires_speaker_auth_text(self) -> str:
        return self._biometric_runtime_adapter()._unlock_requires_speaker_auth_text()

    def _unlock_requires_face_auth_text(self) -> str:
        return self._biometric_runtime_adapter()._unlock_requires_face_auth_text()

    def _unlock_requires_password_text(self) -> str:
        return self._biometric_runtime_adapter()._unlock_requires_password_text()

    def _speaker_auth_error_text(self) -> str:
        return "声紋認証に失敗しました。もう一度お試しください。"

    def _biometric_unlock_success_text(self) -> str:
        return self._biometric_runtime_adapter()._biometric_unlock_success_text()

    def _fetch_biometric_status_from_url(self, status_url: str) -> dict[str, Any] | None:
        return self._biometric_runtime_adapter()._fetch_biometric_status_from_url(status_url)

    def _get_biometric_status_client(self) -> Any | None:
        return self._biometric_runtime_adapter()._get_biometric_status_client()

    def _load_biometric_password_candidates(self) -> list[str]:
        return self._biometric_runtime_adapter()._load_biometric_password_candidates()

    def _verify_unlock_password(self, cmd: VoiceCommand) -> bool:
        return self._biometric_runtime_adapter()._verify_unlock_password(cmd)

    def _consume_biometric_unlock_signal(self) -> bool:
        return self._biometric_runtime_adapter()._consume_biometric_unlock_signal()

    def _consume_biometric_lock_signal(self) -> bool:
        return self._biometric_runtime_adapter()._consume_biometric_lock_signal()

    def _maybe_unlock_from_signal(self) -> bool:
        return self._biometric_runtime_adapter()._maybe_unlock_from_signal()

    def _maybe_lock_from_signal(self) -> bool:
        return self._biometric_runtime_adapter()._maybe_lock_from_signal()

    def _speaker_auth_enabled(self) -> bool:
        return arouter_run_speaker_auth_enabled(
            classifier=getattr(self, "speaker_classifier", None),
            voiceprint=getattr(self, "master_voiceprint", None),
            enabled_check=(
                extracted_speaker_auth_enabled
                if _AHEAR_SPEAKER_AUTH_AVAILABLE
                else None
            ),
        )

    def _verify_speaker_identity(
        self,
        wav_path: Path,
        *,
        cmd: VoiceCommand,
        log_label: str,
    ) -> tuple[bool, str | None]:
        return arouter_run_speaker_identity_verification(
            wav_path=wav_path,
            classifier=getattr(self, "speaker_classifier", None),
            voiceprint=getattr(self, "master_voiceprint", None),
            torchaudio_module=getattr(self, "_speaker_torchaudio", None),
            torch_module=getattr(self, "_speaker_torch", None),
            np_module=getattr(self, "_speaker_np", None),
            device=getattr(self, "_speaker_device", getattr(getattr(self, "args", None), "speaker_device", "cpu")),
            threshold=getattr(getattr(self, "args", None), "speaker_threshold", 0.5),
            topk=getattr(getattr(self, "args", None), "speaker_topk", 5),
            auth_error_text=self._speaker_auth_error_text(),
            logger=self.log,
            log_label=log_label,
            intent=cmd.intent,
            verify_identity=(
                extracted_verify_speaker_identity
                if _AHEAR_SPEAKER_AUTH_AVAILABLE
                else None
            ),
        )

    def _fetch_god_mode_biometric_status(self) -> dict[str, Any] | None:
        return self._biometric_runtime_adapter()._fetch_god_mode_biometric_status()

    def _owner_face_absent_for_lock(self) -> bool:
        return self._biometric_runtime_adapter()._owner_face_absent_for_lock()

    def _owner_face_recent_for_unlock(self) -> bool:
        return self._biometric_runtime_adapter()._owner_face_recent_for_unlock()

    def _record_successful_command_activity(self) -> None:
        self._biometric_runtime_adapter()._record_successful_command_activity()

    def _maybe_auto_lock(self) -> None:
        self._biometric_runtime_adapter()._maybe_auto_lock()

    def _authorize_command(
        self,
        cmd: VoiceCommand,
        *,
        wav_path: Path | None,
        source: str,
        log_label: str,
    ) -> tuple[bool, str | None]:
        return self._biometric_runtime_adapter()._authorize_command(
            cmd,
            wav_path=wav_path,
            source=source,
            log_label=log_label,
        )

    def _biometric_poll_interval_sec(self) -> float:
        return self._biometric_runtime_adapter()._biometric_poll_interval_sec()

    def _biometric_lock_poller(self) -> None:
        self._biometric_runtime_adapter()._biometric_lock_poller()

    def _start_biometric_lock_poller(self) -> None:
        self._biometric_runtime_adapter()._start_biometric_lock_poller()

    def _stop_biometric_lock_poller(self) -> None:
        self._biometric_runtime_adapter()._stop_biometric_lock_poller()

    def _should_suppress_transcribed_command(self, cmd: VoiceCommand, *, dur_sec: float) -> str | None:
        fullscreenish = False
        try:
            ctx = self._get_vacuumtube_context(max_age_sec=5.0, refresh_if_stale=False)
        except Exception:
            ctx = {}
        if isinstance(ctx, dict):
            fullscreenish = bool(ctx.get("fullscreenish"))
        return arouter_suppress_transcribed_command_reason(
            cmd,
            dur_sec=dur_sec,
            fullscreenish=fullscreenish,
        )

    def _is_recoverable_vacuumtube_error(self, err: Exception) -> bool:
        timeout_exc = getattr(websocket, "WebSocketTimeoutException", None)
        return arouter_is_recoverable_vacuumtube_error(
            err,
            timeout_exception_type=timeout_exc,
        )

    def _run_vacuumtube_action(self, action, *, label: str) -> str:
        vac = getattr(self, "vacuumtube", None)
        recover = getattr(vac, "recover_from_unresponsive_state", None) if vac is not None else None
        return arouter_run_vacuumtube_action_with_recovery(
            action=action,
            label=label,
            is_recoverable_error=self._is_recoverable_vacuumtube_error,
            recover=recover,
            log=self.log,
        )

    def _ensure_vacuumtube_context_runtime_attrs(self) -> None:
        if not hasattr(self, "_vacuumtube_context_lock"):
            self._vacuumtube_context_lock = threading.Lock()
        if not hasattr(self, "_vacuumtube_context") or not isinstance(getattr(self, "_vacuumtube_context"), dict):
            self._vacuumtube_context = {"ts": 0.0}
        if not hasattr(self, "_vacuumtube_context_stop_event"):
            self._vacuumtube_context_stop_event = threading.Event()
        if not hasattr(self, "_vacuumtube_context_thread"):
            self._vacuumtube_context_thread = None

    def _collect_vacuumtube_context(self) -> dict[str, Any]:
        return arouter_run_vacuumtube_context_host_runtime_flow(
            ts=time.time(),
            runtime=getattr(self, "vacuumtube", None),
            host_runtime=self,
        )

    def _refresh_vacuumtube_context_cache(self, *, reason: str = "manual") -> dict[str, Any]:
        self._ensure_vacuumtube_context_runtime_attrs()
        try:
            ctx = self._collect_vacuumtube_context()
        except Exception as e:
            ctx = arouter_build_vacuumtube_context_error(ts=time.time(), error=e)
        with self._vacuumtube_context_lock:
            self._vacuumtube_context = dict(ctx)
        return dict(ctx)

    def _get_vacuumtube_context(self, *, max_age_sec: float = 3.0, refresh_if_stale: bool = True) -> dict[str, Any]:
        self._ensure_vacuumtube_context_runtime_attrs()
        with self._vacuumtube_context_lock:
            cached = dict(self._vacuumtube_context)
        return arouter_resolve_vacuumtube_context_cache_host_runtime(
            runtime=self,
            cached=cached,
            now_ts=time.time(),
            max_age_sec=float(max_age_sec),
            refresh_if_stale=bool(refresh_if_stale),
        )

    def _vacuumtube_context_poll_interval_sec(self) -> float:
        return arouter_resolve_vacuumtube_context_poll_interval(
            getattr(self.args, "vacuumtube_state_poll_sec", 2.5)
        )

    def _vacuumtube_context_poller(self) -> None:
        self._ensure_vacuumtube_context_runtime_attrs()
        ev = self._vacuumtube_context_stop_event
        interval = self._vacuumtube_context_poll_interval_sec()
        return arouter_run_vacuumtube_context_poller_loop_host_runtime(
            runtime=self,
            stop_event=ev,
            interval_sec=interval,
        )

    def _start_vacuumtube_context_poller(self) -> None:
        self._ensure_vacuumtube_context_runtime_attrs()
        self._vacuumtube_context_thread = arouter_start_vacuumtube_context_poller_host_runtime(
            runtime=self,
            current_thread=self._vacuumtube_context_thread,
            stop_event=self._vacuumtube_context_stop_event,
        )

    def _stop_vacuumtube_context_poller(self) -> None:
        self._ensure_vacuumtube_context_runtime_attrs()
        arouter_stop_vacuumtube_context_poller(
            stop_event=self._vacuumtube_context_stop_event,
            current_thread=self._vacuumtube_context_thread,
        )

    def _contextualize_command_with_vacuumtube_state(
        self,
        text: str,
        cmd: VoiceCommand | None,
    ) -> VoiceCommand | None:
        return arouter_contextualize_command_with_vacuumtube_state_host_runtime(
            runtime=self,
            text=text,
            cmd=cmd,
        )

    def _transcribe_segment(self, wav_path: Path) -> str:
        return base.transcribe_with_server(
            wav_path,
            base_url=self.base_url,
            language=self.args.language,
            prompt=getattr(self.args, "stt_prompt", ""),
            response_format="json",
        )

    def _execute_command(self, cmd: VoiceCommand) -> str:
        return arouter_execute_command(self, cmd)

    def _command_has_system_prefix(self, cmd: VoiceCommand) -> bool:
        normalized = str(cmd.normalized_text or "")
        if not normalized:
            normalized = normalize_transcript(cmd.raw_text or "")
        return ("システム" in normalized) or ("system" in normalized)

    def _execute_news_command(self, cmd: VoiceCommand, *, slot: str) -> str:
        return arouter_execute_news_command(self, cmd, slot=slot)

    def system_status_report(self) -> str:
        return arouter_run_system_status_report_host_runtime(runtime=self)

    def system_weather_today(self) -> str:
        repo_dir = _weathercli_repo_dir()
        cp = subprocess.run(
            ["make", "run"],
            cwd=str(repo_dir),
            check=True,
            text=True,
            capture_output=True,
        )
        parsed = parse_weathercli_output(cp.stdout)
        if not parsed:
            raise RuntimeError("weathercli output parse failed")
        return build_weather_today_voice_ja(parsed)

    def show_weather_pages_today(self) -> str:
        return arouter_run_show_weather_pages_today_host_runtime(runtime=self)

    def _lights_on(self) -> str:
        return switchbot_lights_on()

    def _lights_off(self) -> str:
        return switchbot_lights_off()

    def _run_command(self, command: list[str], **kwargs: Any) -> Any:
        return run_cmd(command, **kwargs)

    def _close_weather_pages_tiled(self) -> str:
        return self.vacuumtube.close_weather_pages_tiled()

    def _open_weather_pages_tiled(self) -> str:
        return self.vacuumtube.open_weather_pages_tiled()

    def _play_music(self) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.play_bgm,
            label="music_play",
        )

    def _stop_music(self, *, label: str) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.stop_music,
            label=label,
        )

    def _resume_playback(self) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.resume_playback,
            label="playback_resume",
        )

    def _play_news_slot(self, *, slot: str, label: str | None = None) -> str:
        return self._run_vacuumtube_action(
            lambda: self.vacuumtube.play_news(slot=slot),
            label=label or f"news_{slot}",
        )

    def _play_morning_news(self) -> str:
        return self._play_news_slot(
            slot="morning",
            label="good_morning_news",
        )

    def _play_news_command(self, *, slot: str) -> str:
        return self._play_news_slot(
            slot=slot,
            label=f"news_{slot}",
        )

    def _fullscreen_vacuumtube(self, *, label: str) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.youtube_fullscreen,
            label=label,
        )

    def _fullscreen_morning_news(self) -> str:
        return self._fullscreen_vacuumtube(
            label="good_morning_fullscreen",
        )

    def _fullscreen_news_command(self, *, slot: str) -> str:
        return self._fullscreen_vacuumtube(
            label=f"news_{slot}_fullscreen",
        )

    def _youtube_quadrant(self) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.youtube_quadrant,
            label="youtube_quadrant",
        )

    def _youtube_minimize(self) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.youtube_minimize,
            label="youtube_minimize",
        )

    def _go_youtube_home(self) -> str:
        return self._run_vacuumtube_action(
            self.vacuumtube.go_youtube_home,
            label="youtube_home",
        )

    def _pause_for_night(self) -> str:
        return self.vacuumtube.good_night_pause()

    def _show_live_camera_full(self) -> str:
        return self.live_cam_wall.show_full()

    def _show_live_camera_compact(self) -> str:
        return self.live_cam_wall.show_compact()

    def _hide_live_camera(self) -> str:
        return self.live_cam_wall.hide()

    def _minimize_live_camera(self) -> str:
        return self.live_cam_wall.minimize()

    def _live_camera_instance_specs(self) -> list[dict[str, Any]]:
        return list(self.live_cam_wall.instances)

    def _live_camera_pid_for_port(self, port: int) -> int | None:
        return self.live_cam_wall._pid_for_port(port)

    def _vacuumtube_x11_env(self) -> dict[str, str]:
        return self.vacuumtube._x11_env()

    def _vacuumtube_desktop_size(self) -> tuple[int, int] | None:
        return self.vacuumtube._desktop_size()

    def _world_situation_mode_script_path(self) -> str:
        return str(
            _WORKSPACES_ROOT
            / ".codex"
            / "skills"
            / "world-situation-monitor"
            / "scripts"
            / "arrange_world_situation_monitor.sh"
        )

    def _weather_mode_script_path(self) -> str:
        return str(
            _WORKSPACES_ROOT
            / ".codex"
            / "skills"
            / "local-weather-monitor"
            / "scripts"
            / "arrange_local_weather_monitor.sh"
        )

    def _god_mode_layout_script_path(self) -> str:
        return str(
            _WORKSPACES_ROOT
            / "repos"
            / "asee"
            / "tmp_main.sh"
        )

    def good_morning(self) -> str:
        return arouter_run_good_morning_host_runtime(runtime=self)

    def good_night(self) -> str:
        return arouter_run_good_night_host_runtime(runtime=self)

    def system_live_camera_show(self) -> str:
        return arouter_run_system_live_camera_show_host_runtime(runtime=self)

    def system_live_camera_compact(self) -> str:
        return arouter_run_system_live_camera_compact_host_runtime(runtime=self)

    def system_live_camera_hide(self) -> str:
        return arouter_run_system_live_camera_hide_host_runtime(runtime=self)

    def system_street_camera_mode(self) -> str:
        return arouter_run_system_street_camera_mode_host_runtime(runtime=self)

    def system_webcam_mode(self) -> str:
        return arouter_run_system_webcam_mode_host_runtime(runtime=self)

    def god_mode_layout(self, mode: str) -> str:
        return arouter_run_god_mode_layout_host_runtime(
            runtime=self,
            mode=mode,
        )

    def system_normal_mode(self) -> str:
        """通常モード: GOD_MODE→全画面→背景、街頭カメラ→右下コンパクト、その他→最小化。"""
        return arouter_run_system_normal_mode_host_runtime(runtime=self)

    def system_world_situation_mode(self) -> str:
        return arouter_run_system_world_situation_mode_host_runtime(runtime=self)

    def system_weather_mode(self) -> str:
        return arouter_run_system_weather_mode_host_runtime(runtime=self)

    def _minimize_other_windows(self) -> str:
        """KWin スクリプトでライブカメラ・パネル以外の全ウィンドウを最小化する。
        xdotool windowminimize はフルスクリーンウィンドウに効かないため KWin scripting を使用。
        """
        return arouter_run_minimize_other_windows_host_runtime_flow(runtime=self)

    def _load_check_bottom_left_geom(self, *, screen_w: int, screen_h: int) -> dict[str, int]:
        return arouter_load_check_bottom_left_geom(screen_w=screen_w, screen_h=screen_h)

    def _pid_listening_on_tcp_port(self, port: int) -> int | None:
        return arouter_run_listen_pid_host_runtime_query(port)

    def _vacuumtube_main_window_row_by_cdp_port(self, port: int) -> dict[str, Any] | None:
        return arouter_run_window_row_by_listen_port_host_runtime(
            runtime=self,
            port=int(port),
        )

    def _is_vacuumtube_quadrant_mode_for_load_check(self) -> bool:
        return arouter_is_vacuumtube_quadrant_mode_for_load_check(
            self.vacuumtube,
            row_by_cdp_port=self._vacuumtube_main_window_row_by_cdp_port,
        )

    def _konsole_window_rows(self) -> list[dict[str, Any]]:
        lines = self._wmctrl_rows(geometry=True, with_pid=True)
        return arouter_parse_konsole_window_rows("\n".join(lines))

    def _tmux_client_pids_for_session(self, session_name: str) -> list[int]:
        return arouter_run_tmux_client_pid_query_host_runtime(
            runtime=self,
            session_name=session_name,
        )

    def _parent_pid(self, pid: int) -> int | None:
        try:
            with open(f"/proc/{int(pid)}/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("PPid:"):
                        return int(line.split(":", 1)[1].strip())
        except Exception:
            return None
        return None

    def _pid_ancestor_chain(self, pid: int, *, max_depth: int = 32) -> list[int]:
        return arouter_pid_ancestor_chain(
            pid,
            parent_pid_for_pid=self._parent_pid,
            max_depth=max_depth,
        )

    def _find_konsole_rows_for_tmux_session(self, session_name: str) -> list[dict[str, Any]]:
        return arouter_find_konsole_rows_for_tmux_session_host_runtime(
            runtime=self,
            session_name=session_name,
        )

    def _raise_window_by_id(self, wid: str) -> None:
        return arouter_run_window_activate_host_runtime(
            runtime=self.vacuumtube,
            win_id=str(wid),
        )

    def _wait_new_konsole_window(self, *, before_ids: set[str], timeout_sec: float = 8.0) -> dict[str, Any] | None:
        return arouter_wait_for_new_window_row_host_runtime(
            runtime=self,
            before_ids=before_ids,
            timeout_sec=timeout_sec,
        )

    def _position_load_check_konsole_left_bottom_if_quadrant(
        self,
        *,
        before_konsole_ids: set[str] | None = None,
        row: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return arouter_run_load_check_konsole_placement_host_runtime(
            runtime=self,
            before_konsole_ids=before_konsole_ids,
            row=row,
        )

    def system_load_check(self) -> str:
        return arouter_run_system_load_check_host_runtime(runtime=self)

    def _open_system_load_check_monitor(self) -> str:
        return arouter_run_system_load_check_monitor_open_host_runtime(
            script_path=str(_tmux_htop_nvitop_konsole_script()),
            cwd=str(_WORKSPACES_ROOT),
        )

    def _start_ack(self, cmd: VoiceCommand) -> None:
        try:
            self._last_ack_proc = self.voice.speak(cmd.ack_text, wait=False)
            headstart_ms = max(0, int(self.args.ack_headstart_ms))
            if self._last_ack_proc is not None and headstart_ms > 0:
                time.sleep(headstart_ms / 1000.0)
        except Exception as e:
            self.log(f"ack speak error: {e}")
            self._last_ack_proc = None

    def _wait_current_ack(self, *, timeout_sec: float = 8.0) -> None:
        proc = self._last_ack_proc
        if not proc:
            return
        try:
            proc.wait(timeout=timeout_sec)
        except Exception:
            pass

    def _should_wait_ack_before_action(self, cmd: VoiceCommand) -> bool:
        return arouter_should_wait_ack_before_action(cmd)

    def _should_ack_before_action(self, cmd: VoiceCommand) -> bool:
        return arouter_should_ack_before_action(cmd)

    def _good_night_voice_text(self, action_result: str) -> str:
        return arouter_good_night_voice_text(action_result)

    def _post_action_voice_text(self, cmd: VoiceCommand, action_result: str) -> str | None:
        return arouter_post_action_voice_text(
            cmd,
            action_result,
            biometric_unlock_success_text_provider=self._biometric_unlock_success_text,
        )

    def _wait_ack_if_requested(self) -> None:
        if not self.args.wait_ack_after_action:
            return
        self._wait_current_ack(timeout_sec=8.0)

    def _speak_action_error(self) -> None:
        try:
            text = getattr(self, "_action_error_voice_text", "操作に失敗しました。もう一度試してください。")
            self.voice.speak(text, wait=False)
        except Exception as e:
            self.log(f"error speak failed: {e}")

    def execute_text_command(self, text: str) -> dict[str, Any]:
        return arouter_execute_text_command_host_runtime(runtime=self, text=text)

    def _handle_segment(self, raw_pcm: bytes, *, reason: str) -> None:  # override
        self.segments_seen += 1
        arouter_process_pcm_segment(
            self,
            raw_pcm=raw_pcm,
            reason=reason,
            seg_id=self.segments_seen,
            min_segment_bytes=self.min_speech_chunks * self.chunk_bytes,
            bytes_per_sample=base.BYTES_PER_SAMPLE,
            sample_rate=base.SAMPLE_RATE,
            tmp_dir=Path(self.args.tmp_dir),
            wav_encoder=base.wav_bytes_from_pcm,
            transcriber=self._transcribe_segment,
            notify_progress=bool(getattr(self.args, "notify_progress", False)),
        )

    def run(self) -> int:
        self.log("voice command loop starting (auto wait -> respond -> execute -> wait)")
        self.log(
            "latency mode: internal dispatch + overlapped VOICEVOX ack + end_silence_ms="
            f"{self.args.end_silence_ms}"
        )
        self.overlay.prepare()
        if self.lock_overlay is not None:
            prepare_lock_overlay = getattr(self.lock_overlay, "prepare", None)
            if callable(prepare_lock_overlay):
                prepare_lock_overlay()
        self.notifier.prepare()
        self.voice.prepare([
            "承知しました、音楽を再生します。",
            "承知しました、音楽を停止します。",
            "承知しました、動画の再生を再開します。",
            "承知しました、動画の再生を停止します。",
            "承知しました、ニュースライブを再生します。",
            "承知しました、朝のニュースを再生します。",
            "承知しました、夕方のニュースを再生します。",
            "承知しました、YouTubeを全画面にします。",
            "承知しました、YouTubeを小さくします。",
            "承知しました、YouTubeのホーム画面に戻ります。",
            "システムチェック完了 オールグリーン 通常モード",
            "承知しました。通常モードに移行します",
            "承知しました。世界情勢モードへ移行します。",
            "承知しました。ロックモードへ移行します。",
            "承知しました、今日の天気を確認します。",
            "承知しました、天気予報ページを表示します。",
            "承知しました、街頭カメラを表示します。",
            "承知しました、街頭カメラを小さくします。",
            "承知しました、街頭カメラを閉じます。",
            "承知しました。街頭カメラモードへ移行します。",
            "承知しました。ウェブカメラモードへ移行します。",
            "承知しました、負荷を確認します。",
            self._biometric_unlock_success_text(),
            "承知しました。パスワードを確認します。",
            "おはようございます。まず朝のニュースを再生します。",
            "おやすみなさいませ。YouTubeを停止いたしました。どうぞ良い夢を。",
            "おやすみなさいませ。YouTubeは停止済みのようです。どうぞ良い夢を。",
            "おやすみなさいませ。YouTubeの停止対象は見つかりませんでしたが、どうぞ良い夢を。",
            "おやすみなさいませ。YouTubeの停止を試みました。どうぞ良い夢を。",
            self._locked_denied_text(),
            self._unlock_requires_live_voice_text(),
            self._unlock_requires_speaker_auth_text(),
            self._unlock_requires_face_auth_text(),
            self._unlock_requires_password_text(),
            self._speaker_auth_error_text(),
            self._action_error_voice_text,
        ])
        if self._biometric_lock_enabled() and bool(getattr(self, "_system_locked", False)):
            self._set_system_locked(True, reason="run_start_sync")
        self._start_vacuumtube_context_poller()
        self._start_biometric_lock_poller()
        try:
            return super().run()
        finally:
            try:
                self._set_system_locked(False, reason="shutdown")
            except Exception:
                pass
            self._stop_biometric_lock_poller()
            self._stop_vacuumtube_context_poller()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Voice command loop using whisper-server + VOICEVOX + VacuumTube")

    # ── STT backend selection ─────────────────────────────────────────────
    p.add_argument(
        "--stt-backend",
        default=_STT_BACKEND,
        choices=["whisper", "moonshine"],
        help="STT backend: 'whisper' (default, uses whisper-server HTTP) or 'moonshine' (in-process, ~17x faster)",
    )
    p.add_argument(
        "--model-size",
        default="base",
        choices=["tiny", "base"],
        help="moonshine model size (only used when --stt-backend=moonshine): tiny (~170ms) or base (~270ms, default)",
    )

    # Base listen-only options (defaults tuned for lower latency).
    p.add_argument("--server", default="http://127.0.0.1:18080", help="whisper-server base URL (whisper backend only)")
    p.add_argument("--language", default="ja", help="Whisper language code (whisper backend only)")
    p.add_argument("--source", default=None, help="Pulse/PipeWire source name (auto-detect if omitted)")
    p.add_argument("--tmp-dir", default="/tmp/whisper-listen-segments", help="Directory to write temp WAV segments")
    p.add_argument(
        "--stt-prompt",
        default=DEFAULT_STT_PROMPT_JA,
        help="Initial prompt (vocabulary hint) passed to whisper-server /inference",
    )
    p.add_argument("--chunk-ms", type=int, default=80)
    p.add_argument("--pre-roll-ms", type=int, default=240)
    p.add_argument("--start-ms", type=int, default=160)
    p.add_argument("--end-silence-ms", type=int, default=400)
    p.add_argument("--min-speech-ms", type=int, default=250)
    p.add_argument("--max-speech-ms", type=int, default=10000)
    p.add_argument("--calibration-ms", type=int, default=600)
    p.add_argument("--start-rms", type=float, default=0.020)
    p.add_argument("--stop-rms", type=float, default=0.010)
    p.add_argument("--start-rms-min", type=float, default=0.010)
    # Keep interactive agent VAD conservative so a noisy calibration burst does not
    # make the wake threshold too high and effectively disable voice commands.
    p.add_argument("--start-rms-max", type=float, default=0.020)
    # [B] moonshine backend: Japanese word-endings (て, ね, よ) dip to ~0.003 RMS;
    # lower stop_rms_min so they survive the energy VAD before Silero VAD refines.
    _stop_rms_min_default = 0.002 if _STT_BACKEND == "moonshine" else 0.006
    p.add_argument("--stop-rms-min", type=float, default=_stop_rms_min_default)
    p.add_argument("--stop-rms-max", type=float, default=0.014)
    p.add_argument("--server-ready-timeout-sec", type=float, default=10.0)
    p.add_argument("--max-run-sec", type=int, default=0, help="0 means run forever")
    p.add_argument("--max-segments", type=int, default=0, help="0 means unlimited")
    p.add_argument("--run-command", default=None, help="Parse and execute a single command text, then exit")
    p.add_argument("--debug", action="store_true")

    # VOICEVOX output options.
    p.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    p.add_argument("--voicevox-speaker", type=int, default=89)
    p.add_argument("--voicevox-volume-scale", type=float, default=2.5)
    p.add_argument("--voicevox-speed-scale", type=float, default=1.25)
    p.add_argument("--audio-sink", default=None, help="PipeWire/PulseAudio sink name; default uses pactl info")
    p.add_argument("--voice-cache-dir", default="/tmp/voice-command-acks")
    p.add_argument("--no-voice", action="store_true", help="Disable VOICEVOX ack playback")
    p.add_argument("--wait-ack-after-action", action="store_true", help="Wait for ack audio playback before returning to listen")
    p.add_argument("--ack-headstart-ms", type=int, default=120, help="Small delay after starting ack audio before executing action")
    p.add_argument("--no-notify", action="store_true", help="Disable desktop notifications via notify-send")
    p.add_argument("--notify-display", default=None, help="DISPLAY for notify-send (default: vacuumtube-display)")
    p.add_argument("--notify-timeout-ms", type=int, default=5000)
    p.add_argument("--notify-app-name", default="voice-command-loop")
    p.add_argument("--notify-progress", action="store_true", help="Show routine recognition/completion notifications (default: off; errors only)")
    p.add_argument("--no-overlay", action="store_true", help="Disable Tauri caption overlay IPC (use paplay/notify-send directly)")
    p.add_argument("--overlay-ipc-host", default="127.0.0.1")
    p.add_argument("--overlay-ipc-port", type=int, default=47832)
    p.add_argument("--overlay-ipc-timeout-sec", type=float, default=2.0)
    p.add_argument("--lock-screen-ipc-port", type=int, default=47833,
                   help="TCP port for Chromium lock screen bridge (default: 47833; 0 to disable)")

    # VacuumTube control options.
    p.add_argument("--vacuumtube-cdp-host", default="127.0.0.1")
    p.add_argument("--vacuumtube-cdp-port", type=int, default=9992)
    p.add_argument("--vacuumtube-start-script", default=str(Path.home() / "vacuumtube.sh"))
    p.add_argument("--vacuumtube-tmux-session", default="vacuumtube-bg")
    p.add_argument("--vacuumtube-display", default=":1")
    p.add_argument("--vacuumtube-xauthority", default=str(Path.home() / ".Xauthority"))
    p.add_argument("--vacuumtube-target-x", type=int, default=2048)
    p.add_argument("--vacuumtube-target-y", type=int, default=28)
    p.add_argument("--vacuumtube-target-w", type=int, default=2048)
    p.add_argument("--vacuumtube-target-h", type=int, default=1052)
    p.add_argument("--vacuumtube-geometry-tolerance", type=int, default=24)

    # Speaker Identification (ECAPA-TDNN)
    p.add_argument("--speaker-id", action="store_true", help="Enable speaker authentication")
    p.add_argument("--speaker-master", default=str(_DEFAULT_SPEAKER_MASTER), help="Path to master voiceprint .npy file")
    p.add_argument("--speaker-threshold", type=float, default=0.5, help="Cosine similarity threshold for authentication")
    p.add_argument("--speaker-topk", type=int, default=5,
                   help="Number of top similarities to average when using multi-center (2D) voiceprint (default: 5)")
    p.add_argument("--speaker-device", default="cpu",
                   help="Device for speaker verification (e.g. cpu, cuda:0). "
                        "Auto-upgraded to cuda:0 at runtime if CUDA is available.")
    p.add_argument("--biometric-lock", action="store_true", help="Require face + speaker auth to unlock commands after idle lock")
    p.add_argument("--biometric-start-locked", action="store_true", help="Start in locked state when biometric lock is enabled")
    p.add_argument("--biometric-command-idle-lock-sec", type=int, default=1800, help="Lock after this many idle seconds")
    p.add_argument("--biometric-face-absent-lock-sec", type=int, default=120, help="Require owner face absence for at least this many seconds before auto-lock")
    p.add_argument("--biometric-unlock-face-fresh-ms", type=int, default=2000, help="Maximum owner face age to accept during unlock")
    p.add_argument("--biometric-poll-sec", type=float, default=1.0, help="Polling interval for biometric auto-lock checks")
    p.add_argument("--god-mode-status-url", default="http://127.0.0.1:8765/biometric_status", help="GOD_MODE biometric status endpoint")
    p.add_argument("--biometric-password-file", default=DEFAULT_BIOMETRIC_PASSWORD_FILE, help="Encrypted password fallback file (base64 RSA-OAEP)")
    p.add_argument("--biometric-password-public-key", default=DEFAULT_BIOMETRIC_PASSWORD_PUBLIC_KEY, help="SSH RSA public key used to encrypt password fallback")
    p.add_argument("--biometric-password-private-key", default=DEFAULT_BIOMETRIC_PASSWORD_PRIVATE_KEY, help="SSH RSA private key used to decrypt password fallback")
    p.add_argument("--biometric-lock-signal-file", default=DEFAULT_BIOMETRIC_LOCK_SIGNAL_FILE, help="File touched to request a manual lock without restarting the agent")
    p.add_argument("--biometric-unlock-signal-file", default=DEFAULT_BIOMETRIC_UNLOCK_SIGNAL_FILE, help="File touched by the overlay keyboard fallback to request unlock")
    p.add_argument("--request-biometric-lock", action="store_true", help="Touch the biometric lock signal file, print JSON, and exit")
    p.add_argument("--encrypt-biometric-password-stdin", action="store_true", help="Read password fallback lines from stdin and write the encrypted file, then exit")

    return p.parse_args(argv)


def main() -> int:
    args = parse_args()

    def _emit_json(payload: dict[str, Any]) -> None:
        print(json.dumps(payload, ensure_ascii=False), flush=True)

    def _install_signal_handlers(loop: VoiceCommandLoop) -> None:
        def _sig_handler(signum, frame):  # noqa: ANN001
            loop.stop_requested = True
            loop.log(f"signal {signum} received, stopping ...")

        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)

    return arouter_run_voice_command_entrypoint_host_runtime(
        args=args,
        build_loop=VoiceCommandLoop,
        emit_json=_emit_json,
        request_biometric_lock_cli_flow=lambda: arouter_run_request_biometric_lock_cli_flow(
            args=args,
            default_path=DEFAULT_BIOMETRIC_LOCK_SIGNAL_FILE,
            write_signal=write_biometric_signal_file,
        ),
        encrypt_biometric_password_stdin_cli_flow=lambda: arouter_run_encrypt_biometric_password_stdin_cli_flow(
            args=args,
            default_public_key_path=DEFAULT_BIOMETRIC_PASSWORD_PUBLIC_KEY,
            default_output_path=DEFAULT_BIOMETRIC_PASSWORD_FILE,
            read_passwords=_read_password_secret_lines_from_stdin,
            encrypt_password=encrypt_biometric_password_file,
        ),
        install_signal_handlers=_install_signal_handlers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
