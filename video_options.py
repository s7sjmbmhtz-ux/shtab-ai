"""Подтверждённые пользовательские параметры и цены видеомоделей.

Все цены GenAPI переводятся во внутренние 💎 по правилу:
рубли себестоимости × 6, затем округление вверх до 10 💎.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class VideoOptions:
    qualities: tuple[Choice, ...] = ()
    resolutions: tuple[Choice, ...] = ()
    durations: tuple[int, ...] = ()
    audio_choices: tuple[Choice, ...] = ()
    aspects: tuple[Choice, ...] = ()
    default_quality: str | None = None
    default_resolution: str | None = None
    default_duration: int | None = None
    default_audio: str | None = None
    default_aspect: str | None = None
    fixed_quality_label: str | None = None
    fixed_resolution_label: str | None = None
    fixed_duration_label: str | None = None
    fixed_audio_label: str | None = None
    fixed_aspect_label: str | None = None


VIDEO_OPTIONS: Mapping[str, VideoOptions] = {
    "cogvideox-5b": VideoOptions(
        fixed_quality_label="Фиксированное",
        fixed_resolution_label="720×480",
        fixed_duration_label="Задаёт модель",
        fixed_audio_label="Без звука",
        fixed_aspect_label="Горизонтальный",
    ),
    "ltx-2-3": VideoOptions(
        qualities=(Choice("fast", "Fast"), Choice("pro", "Pro")),
        resolutions=(
            Choice("1080p", "1080p"),
            Choice("1440p", "1440p"),
            Choice("2160p", "2160p"),
        ),
        durations=(6, 8, 10),
        audio_choices=(Choice("off", "Без звука"), Choice("on", "Со звуком")),
        aspects=(Choice("horizontal", "Горизонтальный"), Choice("vertical", "Вертикальный")),
        default_quality="fast",
        default_resolution="1080p",
        default_duration=6,
        default_audio="on",
        default_aspect="horizontal",
    ),
    "kling-o3": VideoOptions(
        qualities=(Choice("standard", "Standard"), Choice("pro", "Pro")),
        durations=(5,),
        audio_choices=(Choice("off", "Без звука"), Choice("on", "Со звуком")),
        aspects=(Choice("horizontal", "Горизонтальный"), Choice("vertical", "Вертикальный")),
        default_quality="standard",
        default_duration=5,
        default_audio="off",
        default_aspect="horizontal",
        fixed_resolution_label="Задаёт модель",
    ),
    "kling-v3": VideoOptions(
        qualities=(Choice("standard", "Standard"), Choice("pro", "Pro")),
        durations=(5,),
        audio_choices=(Choice("off", "Без звука"), Choice("on", "Со звуком")),
        aspects=(Choice("horizontal", "Горизонтальный"), Choice("vertical", "Вертикальный")),
        default_quality="standard",
        default_duration=5,
        default_audio="on",
        default_aspect="horizontal",
        fixed_resolution_label="Задаёт модель",
    ),
    "veo-3-1-lite": VideoOptions(
        resolutions=(Choice("720p", "720p"), Choice("1080p", "1080p")),
        durations=(8,),
        audio_choices=(Choice("off", "Без звука"), Choice("on", "Со звуком")),
        aspects=(Choice("horizontal", "Горизонтальный"), Choice("vertical", "Вертикальный")),
        default_resolution="720p",
        default_duration=8,
        default_audio="on",
        default_aspect="horizontal",
        fixed_quality_label="Lite",
    ),
    "veo-3-1": VideoOptions(
        qualities=(Choice("fast", "Fast"), Choice("normal", "Обычный")),
        resolutions=(Choice("720p", "720p"), Choice("1080p", "1080p"), Choice("4k", "4K")),
        durations=(8,),
        audio_choices=(Choice("off", "Без звука"), Choice("on", "Со звуком")),
        aspects=(Choice("horizontal", "Горизонтальный"), Choice("vertical", "Вертикальный")),
        default_quality="fast",
        default_resolution="720p",
        default_duration=8,
        default_audio="on",
        default_aspect="horizontal",
    ),
    "luma-ray2": VideoOptions(
        qualities=(Choice("ray-2-flash", "Flash"), Choice("ray-2", "Ray-2")),
        resolutions=(Choice("540p", "540p"), Choice("720p", "720p"), Choice("1080p", "1080p")),
        durations=(5, 9),
        aspects=(Choice("horizontal", "Горизонтальный"), Choice("vertical", "Вертикальный")),
        default_quality="ray-2-flash",
        default_resolution="540p",
        default_duration=5,
        default_aspect="horizontal",
        fixed_audio_label="Без звука",
    ),
    "runway-gen4": VideoOptions(
        durations=(5, 10),
        default_duration=5,
        default_aspect="horizontal",
        fixed_quality_label="Gen-4 Turbo",
        fixed_resolution_label="720p",
        fixed_audio_label="Без звука",
        fixed_aspect_label="Горизонтальный",
    ),
}


def get_video_options(model_key: str) -> VideoOptions:
    try:
        return VIDEO_OPTIONS[model_key]
    except KeyError as exc:
        raise ValueError(f"Нет настроек для видеомодели: {model_key}") from exc


def default_video_selection(model_key: str) -> dict[str, Any]:
    options = get_video_options(model_key)
    return {
        "quality": options.default_quality,
        "resolution": options.default_resolution,
        "duration": options.default_duration,
        "audio": options.default_audio,
        "aspect": options.default_aspect,
    }


def _choice_label(choices: tuple[Choice, ...], value: str | None, fixed: str | None) -> str:
    if fixed:
        return fixed
    for choice in choices:
        if choice.value == value:
            return choice.label
    return "Не выбрано"


def selection_labels(model_key: str, selection: Mapping[str, Any]) -> dict[str, str]:
    options = get_video_options(model_key)
    duration = selection.get("duration")
    if options.fixed_duration_label:
        duration_label = options.fixed_duration_label
    elif duration:
        duration_label = f"{int(duration)} секунд"
    else:
        duration_label = "Задаёт модель"
    return {
        "quality": _choice_label(options.qualities, selection.get("quality"), options.fixed_quality_label),
        "resolution": _choice_label(options.resolutions, selection.get("resolution"), options.fixed_resolution_label),
        "duration": duration_label,
        "audio": _choice_label(options.audio_choices, selection.get("audio"), options.fixed_audio_label),
        "aspect": _choice_label(options.aspects, selection.get("aspect"), options.fixed_aspect_label),
    }


def validate_option(model_key: str, field: str, value: str) -> Any:
    options = get_video_options(model_key)
    if field == "quality":
        valid = {item.value for item in options.qualities}
        if value not in valid:
            raise ValueError("Недоступный режим качества")
        return value
    if field == "resolution":
        valid = {item.value for item in options.resolutions}
        if value not in valid:
            raise ValueError("Недоступное разрешение")
        return value
    if field == "duration":
        parsed = int(value)
        if parsed not in options.durations:
            raise ValueError("Недоступная длительность")
        return parsed
    if field == "audio":
        valid = {item.value for item in options.audio_choices}
        if value not in valid:
            raise ValueError("Недоступный режим звука")
        return value
    if field == "aspect":
        valid = {item.value for item in options.aspects}
        if value not in valid:
            raise ValueError("Недоступный формат")
        return value
    raise ValueError("Неизвестный параметр")


def build_video_overrides(model_key: str, selection: Mapping[str, Any]) -> dict[str, Any]:
    quality = selection.get("quality")
    resolution = selection.get("resolution")
    audio = selection.get("audio")
    aspect = selection.get("aspect")
    overrides: dict[str, Any] = {}

    if model_key == "ltx-2-3":
        overrides["mode"] = quality
        overrides["resolution"] = resolution
        overrides["generate_audio"] = audio == "on"
        overrides["aspect_ratio"] = "9:16" if aspect == "vertical" else "16:9"
    elif model_key == "kling-o3":
        overrides["pro"] = quality == "pro"
        overrides["generate_audio"] = audio == "on"
        overrides["aspect_ratio"] = "9:16" if aspect == "vertical" else "16:9"
    elif model_key == "kling-v3":
        overrides["model"] = quality
        overrides["generate_audio"] = audio == "on"
        overrides["aspect_ratio"] = "9:16" if aspect == "vertical" else "16:9"
    elif model_key == "veo-3-1-lite":
        overrides["resolution"] = resolution
        overrides["generate_audio"] = audio == "on"
        overrides["aspect_ratio"] = "9:16" if aspect == "vertical" else "16:9"
    elif model_key == "veo-3-1":
        overrides["fast"] = quality == "fast"
        overrides["resolution"] = resolution
        overrides["generate_audio"] = audio == "on"
        overrides["aspect_ratio"] = "9:16" if aspect == "vertical" else "16:9"
    elif model_key == "luma-ray2":
        overrides["model"] = quality
        overrides["resolution"] = resolution
        overrides["aspect_ratio"] = "9:16" if aspect == "vertical" else "16:9"
    elif model_key == "runway-gen4":
        # В доступной схеме GenAPI подтверждён только горизонтальный формат.
        # Вертикальное значение 720:1280 ранее было добавлено по предположению
        # и приводило к ошибке провайдера, поэтому всегда отправляем 1280:720.
        overrides["ratio"] = "1280:720"
    elif model_key == "cogvideox-5b":
        overrides["width"] = 720
        overrides["height"] = 480
    else:
        raise ValueError(f"Нет API-сопоставления для видеомодели: {model_key}")

    return {key: value for key, value in overrides.items() if value is not None}


def _tokens_from_rubles(rubles: float) -> int:
    return max(10, int(ceil((rubles * 6) / 10.0) * 10))


def video_cost_rubles(model_key: str, selection: Mapping[str, Any]) -> float:
    quality = selection.get("quality")
    resolution = selection.get("resolution")
    duration = int(selection.get("duration") or 0)
    audio = selection.get("audio")

    if model_key == "cogvideox-5b":
        return 30.0
    if model_key == "runway-gen4":
        return {5: 60.0, 10: 120.0}[duration]
    if model_key == "luma-ray2":
        table = {
            ("ray-2-flash", 5, "540p"): 40.0,
            ("ray-2-flash", 5, "720p"): 80.0,
            ("ray-2-flash", 5, "1080p"): 160.0,
            ("ray-2-flash", 9, "540p"): 80.0,
            ("ray-2-flash", 9, "720p"): 160.0,
            ("ray-2-flash", 9, "1080p"): 320.0,
            ("ray-2", 5, "540p"): 100.0,
            ("ray-2", 5, "720p"): 200.0,
            ("ray-2", 5, "1080p"): 400.0,
            ("ray-2", 9, "540p"): 200.0,
            ("ray-2", 9, "720p"): 400.0,
            ("ray-2", 9, "1080p"): 800.0,
        }
        return table[(quality, duration, resolution)]
    if model_key == "ltx-2-3":
        per_second = {
            ("fast", "1080p"): 10.0,
            ("fast", "1440p"): 20.0,
            ("fast", "2160p"): 40.0,
            ("pro", "1080p"): 15.0,
            ("pro", "1440p"): 30.0,
            ("pro", "2160p"): 60.0,
        }[(quality, resolution)]
        return per_second * duration
    if model_key == "veo-3-1-lite":
        per_second = {
            ("720p", "off"): 7.5,
            ("720p", "on"): 12.5,
            ("1080p", "off"): 12.5,
            ("1080p", "on"): 20.0,
        }[(resolution, audio)]
        return per_second * duration
    if model_key == "veo-3-1":
        is_fast = quality == "fast"
        if resolution in {"720p", "1080p"}:
            per_second = 25.0 if is_fast and audio == "off" else 37.5 if is_fast else 50.0 if audio == "off" else 100.0
        else:
            per_second = 75.0 if is_fast and audio == "off" else 87.5 if is_fast else 100.0 if audio == "off" else 150.0
        return per_second * duration
    if model_key == "kling-v3":
        per_second = {
            ("standard", "off"): 42.0,
            ("standard", "on"): 63.0,
            ("pro", "off"): 56.0,
            ("pro", "on"): 84.0,
        }[(quality, audio)]
        return per_second * duration
    if model_key == "kling-o3":
        per_second = {
            ("standard", "off"): 42.0,
            ("standard", "on"): 56.0,
            ("pro", "off"): 56.0,
            ("pro", "on"): 70.0,
        }[(quality, audio)]
        return per_second * duration
    raise ValueError(f"Нет цены для видеомодели: {model_key}")


def video_cost_tokens(model_key: str, selection: Mapping[str, Any]) -> int:
    return _tokens_from_rubles(video_cost_rubles(model_key, selection))


def video_min_cost_tokens(model_key: str) -> int:
    options = get_video_options(model_key)
    selection = default_video_selection(model_key)
    candidates: list[int] = []

    qualities = options.qualities or (Choice(str(selection.get("quality") or ""), ""),)
    resolutions = options.resolutions or (Choice(str(selection.get("resolution") or ""), ""),)
    durations = options.durations or (int(selection.get("duration") or 0),)
    audios = options.audio_choices or (Choice(str(selection.get("audio") or ""), ""),)

    for quality in qualities:
        for resolution in resolutions:
            for duration in durations:
                for audio in audios:
                    candidate = dict(selection)
                    candidate.update(
                        quality=quality.value or None,
                        resolution=resolution.value or None,
                        duration=duration or None,
                        audio=audio.value or None,
                    )
                    try:
                        candidates.append(video_cost_tokens(model_key, candidate))
                    except (KeyError, ValueError):
                        continue
    if not candidates:
        return video_cost_tokens(model_key, selection)
    return min(candidates)
