"""Tour processing service: stitching, video generation, and viewer creation.

Every operation that can fail wraps the underlying error in a domain-specific
exception so the caller always gets a structured, safe error message.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from typing import Optional

from app.errors.exceptions import (
    StitchingError,
    TourProcessingError,
    VideoProcessingError,
)

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", "outputs")
TOURS_FOLDER = os.environ.get("TOURS_FOLDER", "tours")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

for folder in (UPLOAD_FOLDER, OUTPUT_FOLDER, TOURS_FOLDER):
    os.makedirs(folder, exist_ok=True)


def slugify(text: str) -> str:
    text = text[:200].lower()
    text = re.sub(r"[^\w\s\-]", "", text)
    text = text.replace("_", "-")
    parts = text.split()
    text = "-".join(parts)
    text = text.strip("-")
    return text


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_exposures(images_folder: str) -> None:
    """Normalize exposure across all images in a folder.

    Raises:
        TourProcessingError: If any image fails to process (not silently skipped).
    """
    try:
        from PIL import Image, ImageEnhance
    except ImportError as exc:
        raise TourProcessingError(
            message="Image processing library is not available.",
            context={"original_error": str(exc)},
        ) from exc

    for filename in os.listdir(images_folder):
        if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
            continue

        img_path = os.path.join(images_folder, filename)
        try:
            img = Image.open(img_path)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.05)
            img.save(img_path)
        except Exception as exc:
            logger.error("Failed to normalize exposure for '%s': %s", img_path, exc)
            raise TourProcessingError(
                message=f"Failed to process image '{filename}'.",
                context={"file": img_path, "original_error": str(exc)},
            ) from exc


def stitch_panorama(images_folder: str, output_path: str) -> str:
    """Stitch images into a 360 panorama using OpenCV.

    Raises:
        StitchingError: If there aren't enough images or stitching fails.
    """
    try:
        import cv2
    except ImportError as exc:
        raise StitchingError(
            message="OpenCV is not available for image stitching.",
            context={"original_error": str(exc)},
        ) from exc

    images = []
    for f in sorted(os.listdir(images_folder)):
        if f.lower() == "realtor_photo.jpg":
            continue
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            img_path = os.path.join(images_folder, f)
            img = cv2.imread(img_path)
            if img is not None:
                images.append(img)
            else:
                logger.warning("Could not read image '%s', skipping.", img_path)

    if len(images) < 2:
        raise StitchingError(
            message="Not enough valid photos to stitch. Need at least 2 overlapping images.",
            context={"image_count": len(images), "folder": images_folder},
        )

    try:
        stitcher = cv2.Stitcher_create()
    except AttributeError:
        stitcher = cv2.Stitcher.create()

    status, panorama = stitcher.stitch(images)

    STITCH_ERRORS = {
        1: "Photos do not have enough overlapping visual features to connect.",
        2: "Failed to align photos. The angles may be too disjointed.",
        3: "Failed to calculate camera parameters from the photos.",
    }

    if status != 0:
        error_msg = STITCH_ERRORS.get(
            status, f"OpenCV stitcher returned error code {status}."
        )
        raise StitchingError(
            message=error_msg,
            context={"opencv_status": status, "image_count": len(images)},
        )

    cv2.imwrite(output_path, panorama)
    logger.info("Panorama stitched successfully: %s (%d images)", output_path, len(images))
    return output_path


def create_360_video(panorama_path: str, output_path: str, duration: int = 30) -> str:
    """Create a rotating 360 video from a panorama using FFmpeg.

    Raises:
        VideoProcessingError: If FFmpeg is missing or the conversion fails.
    """
    if not os.path.exists(panorama_path):
        raise VideoProcessingError(
            message="Source panorama file does not exist.",
            context={"panorama_path": panorama_path},
        )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", panorama_path,
        "-vf",
        f"rotate=2*PI*t/{duration}:ow=hypot(iw\\,ih):oh=ow,scale=1920:1080",
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        logger.info("360 video created: %s", output_path)
    except FileNotFoundError as exc:
        raise VideoProcessingError(
            message="FFmpeg is not installed on this system.",
            context={"original_error": str(exc)},
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        logger.error("FFmpeg failed: %s", stderr)
        raise VideoProcessingError(
            message="Video encoding failed. The panorama image may be corrupted.",
            context={"ffmpeg_stderr": stderr, "exit_code": exc.returncode},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("FFmpeg timed out after 300s for %s", panorama_path)
        raise VideoProcessingError(
            message="Video encoding timed out.",
            context={"panorama_path": panorama_path},
        ) from exc

    return output_path


def generate_vr_viewer(
    tour_folder: str,
    realtor_data: dict,
    address: str,
    scenes_data: Optional[dict] = None,
) -> str:
    """Generate the Pannellum HTML viewer with realtor overlay.

    Raises:
        TourProcessingError: If the viewer HTML cannot be written.
    """
    scenes_html = ""
    if scenes_data and len(scenes_data) > 1:
        scenes_html = """
        <div class="scene-selector" style="position: absolute; top: 24px; right: 24px; z-index: 100;">
            <select id="sceneSelect" class="bg-black/70 backdrop-blur-lg border border-white/20 rounded-lg px-4 py-2 text-white">
                <option value="interior">Interior</option>
                <option value="exterior">Exterior</option>
            </select>
        </div>
        """

    scenes_json = json.dumps(scenes_data) if scenes_data else "{}"

    # Escape user data for safe HTML embedding
    safe_name = _escape_html(realtor_data.get("name", ""))
    safe_brokerage = _escape_html(realtor_data.get("brokerage", ""))
    safe_phone = _escape_html(realtor_data.get("phone", ""))
    safe_email = _escape_html(realtor_data.get("email", ""))
    safe_address = _escape_html(address)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>{safe_name} - {safe_address} | 360 Virtual Tour</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.css"/>
    <script src="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; overflow: hidden; }}
        #container {{ width: 100%; height: 100vh; position: relative; }}
        .realtor-card {{
            position: absolute; bottom: 24px; left: 24px; z-index: 100;
            background: rgba(0,0,0,0.85); backdrop-filter: blur(20px);
            border-radius: 20px; padding: 16px 20px; display: flex; gap: 16px;
            align-items: center; border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s ease; max-width: 320px;
        }}
        .realtor-card:hover {{ transform: translateY(-4px); background: rgba(0,0,0,0.95); border-color: rgba(201,168,76,0.3); }}
        .realtor-avatar {{ width: 56px; height: 56px; border-radius: 50%; object-fit: cover; border: 2px solid #c9a84c; }}
        .realtor-info h3 {{ color: #c9a84c; font-size: 1rem; font-weight: 700; margin-bottom: 4px; }}
        .realtor-info p {{ color: rgba(255,255,255,0.7); font-size: 0.75rem; margin-bottom: 2px; }}
        .realtor-info .phone {{ color: white; font-size: 0.8rem; font-weight: 600; margin-top: 4px; }}
        .address-badge {{
            position: absolute; top: 24px; left: 50%; transform: translateX(-50%); z-index: 100;
            background: rgba(0,0,0,0.7); backdrop-filter: blur(12px); padding: 10px 24px;
            border-radius: 40px; border: 1px solid rgba(255,255,255,0.15);
            font-size: 0.9rem; font-weight: 500; color: white; white-space: nowrap;
        }}
        .action-buttons {{ position: absolute; bottom: 24px; right: 24px; z-index: 100; display: flex; gap: 12px; }}
        .action-btn {{
            background: rgba(0,0,0,0.7); backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.15); border-radius: 50px;
            padding: 12px 20px; color: white; font-size: 0.8rem; font-weight: 500;
            cursor: pointer; transition: all 0.2s ease; text-decoration: none;
            display: inline-flex; align-items: center; gap: 8px;
        }}
        .action-btn:hover {{ background: #c9a84c; color: black; border-color: #c9a84c; }}
        .action-btn.contact {{ background: #c9a84c; color: black; }}
        .modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 200; align-items: center; justify-content: center; }}
        .modal.active {{ display: flex; }}
        .modal-content {{ background: #1a1a1a; border-radius: 24px; padding: 32px; max-width: 400px; width: 90%; text-align: center; border: 1px solid #c9a84c; }}
        .modal-content h3 {{ color: #c9a84c; font-size: 1.5rem; margin-bottom: 16px; }}
        .modal-content p {{ color: white; margin-bottom: 24px; }}
        .modal-close {{ background: #c9a84c; color: black; border: none; padding: 10px 24px; border-radius: 30px; font-weight: bold; cursor: pointer; }}
        .error-banner {{
            position: absolute; top: 80px; left: 50%; transform: translateX(-50%); z-index: 150;
            background: rgba(220,38,38,0.9); color: white; padding: 12px 24px;
            border-radius: 12px; font-size: 0.85rem; display: none;
        }}
        @media (max-width: 768px) {{
            .realtor-card {{ padding: 12px 16px; max-width: 280px; }}
            .realtor-avatar {{ width: 44px; height: 44px; }}
            .address-badge {{ font-size: 0.7rem; padding: 6px 16px; }}
            .action-btn {{ padding: 8px 16px; font-size: 0.7rem; }}
        }}
    </style>
</head>
<body>
    <div id="container"></div>
    <div id="error-banner" class="error-banner"></div>

    {scenes_html}

    <div class="realtor-card">
        <img class="realtor-avatar" src="realtor.jpg" alt="{safe_name}"
             onerror="this.src='https://placehold.co/56x56/c9a84c/1a1a1a?text=R'">
        <div class="realtor-info">
            <h3>{safe_name}</h3>
            <p>{safe_brokerage}</p>
            <div class="phone">{safe_phone}</div>
        </div>
    </div>

    <div class="address-badge">{safe_address}</div>

    <div class="action-buttons">
        <a href="mailto:{safe_email}" class="action-btn">Email</a>
        <button class="action-btn contact" onclick="showModal()">Contact</button>
    </div>

    <div id="modal" class="modal" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <h3>{safe_name}</h3>
            <p>Call or text for a private showing</p>
            <p style="font-size: 1.5rem; font-weight: bold;">{safe_phone}</p>
            <p style="font-size: 0.9rem;">{safe_email}</p>
            <button class="modal-close" onclick="closeModal()">Close</button>
        </div>
    </div>

    <script>
        var currentViewer = null;
        var errorBanner = document.getElementById('error-banner');

        function showError(msg) {{
            errorBanner.textContent = msg;
            errorBanner.style.display = 'block';
            setTimeout(function() {{ errorBanner.style.display = 'none'; }}, 8000);
        }}

        function loadScene(sceneType) {{
            try {{
                var scenes = {scenes_json};
                var scene = scenes[sceneType];

                if (!scene) {{
                    showError('Scene "' + sceneType + '" is not available.');
                    return;
                }}

                if (currentViewer) {{
                    try {{ currentViewer.destroy(); }} catch(e) {{ /* viewer already destroyed */ }}
                    currentViewer = null;
                }}

                if (scene.type === '360') {{
                    currentViewer = pannellum.viewer('container', {{
                        "type": "equirectangular",
                        "panorama": scene.src,
                        "autoLoad": true,
                        "showZoomCtrl": true,
                        "showFullscreenCtrl": true,
                        "compass": true
                    }});
                    currentViewer.on('error', function(err) {{
                        showError('Failed to load panorama: ' + (err || 'unknown error'));
                    }});
                }} else if (scene.type === 'video') {{
                    var container = document.getElementById('container');
                    container.innerHTML = '<video controls autoplay style="width:100%;height:100%;object-fit:contain;">' +
                        '<source src="' + scene.src + '" type="video/mp4">' +
                        'Your browser does not support video playback.</video>';
                    var video = container.querySelector('video');
                    if (video) {{
                        video.onerror = function() {{ showError('Failed to load video. The file may be corrupted or unsupported.'); }};
                    }}
                }} else {{
                    showError('Unknown scene type: ' + scene.type);
                }}
            }} catch(e) {{
                showError('Error loading scene: ' + e.message);
            }}
        }}

        // Initialize
        (function() {{
            var sceneSelect = document.getElementById('sceneSelect');
            if (sceneSelect) {{
                sceneSelect.addEventListener('change', function(e) {{ loadScene(e.target.value); }});
            }}
            var scenes = {scenes_json};
            var firstScene = scenes.interior ? 'interior' : Object.keys(scenes)[0];
            if (firstScene) {{
                loadScene(firstScene);
            }} else {{
                showError('No scenes available for this tour.');
            }}
        }})();

        function showModal() {{
            document.getElementById('modal').classList.add('active');
        }}

        function closeModal(e) {{
            if (!e || e.target === document.getElementById('modal')) {{
                document.getElementById('modal').classList.remove('active');
            }}
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>"""

    viewer_path = os.path.join(tour_folder, "index.html")
    try:
        with open(viewer_path, "w") as f:
            f.write(html_content)
    except OSError as exc:
        logger.error("Failed to write viewer HTML to '%s': %s", viewer_path, exc)
        raise TourProcessingError(
            message="Failed to create the tour viewer file.",
            context={"path": viewer_path, "original_error": str(exc)},
        ) from exc

    logger.info("VR viewer generated: %s", viewer_path)
    return viewer_path


def process_tour_job(job_id: str, upload_base: str, realtor_data: dict, address: str) -> None:
    """Background job: stitch panoramas, generate videos, build viewer.

    Errors are caught, logged, and written to status.json — never silently
    swallowed. Each processing step logs its own failures with full context.
    """
    realtor_slug = slugify(realtor_data["name"])
    tour_folder = os.path.join(TOURS_FOLDER, realtor_slug, job_id)
    os.makedirs(tour_folder, exist_ok=True)

    scenes = {}

    try:
        # --- Interior: photos -> panorama, or video copy ---
        int_p = os.path.join(upload_base, "int_photos")
        int_v = os.path.join(upload_base, "int_video")

        if os.path.exists(int_p) and len(os.listdir(int_p)) > 1:
            logger.info("[job=%s] Processing interior photos...", job_id)
            normalize_exposures(int_p)
            panorama_path = os.path.join(tour_folder, "int_pan.jpg")
            stitch_panorama(int_p, panorama_path)
            scenes["interior"] = {"type": "360", "src": "int_pan.jpg"}

            # Generate a rotating video from the panorama
            video_path = os.path.join(tour_folder, "int_video.mp4")
            try:
                create_360_video(panorama_path, video_path)
                logger.info("[job=%s] Interior 360 video created.", job_id)
            except VideoProcessingError as exc:
                logger.warning(
                    "[job=%s] Could not create interior video (panorama still available): %s",
                    job_id, exc.message,
                )

        elif os.path.exists(int_v) and os.listdir(int_v):
            vid_name = os.listdir(int_v)[0]
            shutil.copy(
                os.path.join(int_v, vid_name),
                os.path.join(tour_folder, "int_tour.mp4"),
            )
            scenes["interior"] = {"type": "video", "src": "int_tour.mp4"}
            logger.info("[job=%s] Interior video copied.", job_id)

        # --- Exterior: photos -> panorama, or video copy ---
        ext_p = os.path.join(upload_base, "ext_photos")
        ext_v = os.path.join(upload_base, "ext_video")

        if os.path.exists(ext_p) and len(os.listdir(ext_p)) > 1:
            logger.info("[job=%s] Processing exterior photos...", job_id)
            normalize_exposures(ext_p)
            panorama_path = os.path.join(tour_folder, "ext_pan.jpg")
            stitch_panorama(ext_p, panorama_path)
            scenes["exterior"] = {"type": "360", "src": "ext_pan.jpg"}

            video_path = os.path.join(tour_folder, "ext_video.mp4")
            try:
                create_360_video(panorama_path, video_path)
                logger.info("[job=%s] Exterior 360 video created.", job_id)
            except VideoProcessingError as exc:
                logger.warning(
                    "[job=%s] Could not create exterior video (panorama still available): %s",
                    job_id, exc.message,
                )

        elif os.path.exists(ext_v) and os.listdir(ext_v):
            vid_name = os.listdir(ext_v)[0]
            shutil.copy(
                os.path.join(ext_v, vid_name),
                os.path.join(tour_folder, "ext_tour.mp4"),
            )
            scenes["exterior"] = {"type": "video", "src": "ext_tour.mp4"}
            logger.info("[job=%s] Exterior video copied.", job_id)

        # --- Realtor branding photo ---
        realtor_photo_path = os.path.join(upload_base, "realtor_photo.jpg")
        if os.path.exists(realtor_photo_path):
            shutil.copy(realtor_photo_path, os.path.join(tour_folder, "realtor.jpg"))
            realtor_data["photo"] = "realtor.jpg"

        if not scenes:
            raise TourProcessingError(
                message="No valid interior or exterior media was provided.",
                context={"job_id": job_id},
            )

        # --- Save data + generate viewer ---
        player_data = {
            "realtor": realtor_data,
            "address": address,
            "scenes": scenes,
        }

        with open(os.path.join(tour_folder, "data.json"), "w") as f:
            json.dump(player_data, f)

        generate_vr_viewer(tour_folder, realtor_data, address, scenes)

        with open(os.path.join(tour_folder, "status.json"), "w") as f:
            json.dump(
                {"status": "completed", "tour_url": f"/tour/{realtor_slug}/{job_id}"},
                f,
            )

        logger.info("[job=%s] Tour completed: /tour/%s/%s", job_id, realtor_slug, job_id)

    except TourProcessingError as exc:
        logger.error("[job=%s] Tour processing failed: %s", job_id, exc.message)
        _write_failure_status(tour_folder, exc.message)
    except StitchingError as exc:
        logger.error("[job=%s] Stitching failed: %s", job_id, exc.message)
        _write_failure_status(tour_folder, exc.message)
    except Exception as exc:
        logger.error(
            "[job=%s] Unexpected error during tour processing: %s",
            job_id, exc, exc_info=True,
        )
        _write_failure_status(tour_folder, "An unexpected error occurred during processing.")


def _write_failure_status(tour_folder: str, error_message: str) -> None:
    """Write a failure status file. Never raises — this is a last-resort logger."""
    try:
        with open(os.path.join(tour_folder, "status.json"), "w") as f:
            json.dump({"status": "failed", "error": error_message}, f)
    except OSError as exc:
        logger.critical(
            "Could not write failure status to '%s': %s", tour_folder, exc
        )


def _escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS in generated viewer pages."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
