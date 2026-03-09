from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


def run_speaker_auth_enabled(
    *,
    classifier: Any | None,
    voiceprint: Any | None,
    enabled_check: Callable[..., bool] | None,
) -> bool:
    if callable(enabled_check):
        return bool(enabled_check(classifier=classifier, voiceprint=voiceprint))
    return classifier is not None and voiceprint is not None


def run_speaker_identity_verification(
    *,
    wav_path: Path,
    classifier: Any | None,
    voiceprint: Any | None,
    torchaudio_module: Any,
    torch_module: Any,
    np_module: Any,
    device: str,
    threshold: float,
    topk: int,
    auth_error_text: str,
    logger: Callable[[str], None],
    log_label: str,
    intent: str,
    verify_identity: Callable[..., tuple[bool, str | None]] | None,
) -> tuple[bool, str | None]:
    if classifier is None or voiceprint is None:
        return True, None

    if callable(verify_identity):
        return verify_identity(
            wav_path=wav_path,
            classifier=classifier,
            voiceprint=voiceprint,
            torchaudio_module=torchaudio_module,
            torch_module=torch_module,
            np_module=np_module,
            device=device,
            threshold=threshold,
            topk=topk,
            auth_error_text=auth_error_text,
            logger=logger,
            log_label=log_label,
            intent=intent,
        )

    try:
        started_at = time.time()
        signal, sample_rate = torchaudio_module.load(str(wav_path))
        if sample_rate != 16_000:
            resampler = torchaudio_module.transforms.Resample(sample_rate, 16_000)
            signal = resampler(signal)

        with torch_module.no_grad():
            embeddings = classifier.encode_batch(signal.to(device))
            embedding = embeddings.squeeze().cpu().numpy()
            if len(embedding.shape) > 1:
                embedding = np_module.mean(embedding, axis=0)
            embedding = embedding / np_module.linalg.norm(embedding)
            if len(voiceprint.shape) == 2:
                similarities = np_module.dot(voiceprint, embedding)
                top_similarities = sorted(similarities.tolist(), reverse=True)[:topk]
                similarity = float(np_module.mean(top_similarities))
            else:
                similarity = float(np_module.dot(voiceprint, embedding))

        elapsed = time.time() - started_at
        if similarity < threshold:
            logger(
                f"{log_label} AUTH FAILED: intent={intent} "
                f"similarity={similarity:.4f} (threshold={threshold}) SV_elapsed={elapsed:.2f}s"
            )
            return False, auth_error_text
        logger(
            f"{log_label} AUTH PASSED: intent={intent} "
            f"similarity={similarity:.4f} SV_elapsed={elapsed:.2f}s"
        )
        return True, None
    except Exception as exc:
        logger(f"Speaker ID verification error: {exc}")
        return False, auth_error_text
