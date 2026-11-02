"""Local H3 task preparation. Sampling, decoding and output remain in the graph.

These nodes call ComfyUI's open-weights MiniMax H3 implementation, not the
hosted partner API. Extend/insert additionally use the MCR context node.
"""


def _h3():
    try:
        from comfy_extras import nodes_minimax_h3
    except ImportError as exc:
        raise RuntimeError("Fluxdon Local H3 needs a ComfyUI version with MiniMax H3 support") from exc
    return nodes_minimax_h3


def _i2v(clip, vae, prompt, width, height, length, first_frame=None):
    return _h3().MiniMaxH3ImageToVideo.execute(
        clip=clip, vae=vae, prompt=prompt, width=width, height=height,
        length=length, first_frame=first_frame)


def _context(**kwargs):
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get("MiniMaxH3ExistingVideoMaskedContext")
    if cls is None:
        raise RuntimeError("Install ComfyUI-H3-Motion-Context-MultiRef for Fluxdon H3 extend/insert")
    return cls().prepare(**kwargs)


def _common():
    return {
        "clip": ("CLIP",), "vae": ("VAE",),
        "prompt": ("STRING", {"default": "", "multiline": True}),
        "width": ("INT", {"default": 1024, "min": 32, "max": 16384, "step": 32}),
        "height": ("INT", {"default": 576, "min": 32, "max": 16384, "step": 32}),
        "length": ("INT", {"default": 124, "min": 5, "max": 3600, "step": 17}),
    }


class _Base:
    CATEGORY = "Fluxdon/Local H3"
    FUNCTION = "prepare"
    RETURN_TYPES = ("CONDITIONING", "LATENT")
    RETURN_NAMES = ("positive", "latent")


class FluxdonH3Recast(_Base):
    """Condition on an identity image and source motion; not a pixel-exact swap."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {**_common(), "audio_vae": ("VAE",),
                "identity": ("IMAGE",), "source_frames": ("IMAGE",),
                "ref_image_size": (["match", "max"], {"default": "match"})},
                "optional": {"identity_2": ("IMAGE",), "source_audio": ("AUDIO",)}}

    def prepare(self, clip, vae, prompt, width, height, length, audio_vae,
                identity, source_frames, ref_image_size="match", identity_2=None, source_audio=None):
        images = {"ref_image_0": identity}
        if identity_2 is not None:
            images["ref_image_1"] = identity_2
        return tuple(_h3().MiniMaxH3ReferenceToVideo.execute(
            clip=clip, vae=vae, audio_vae=audio_vae, prompt=prompt, width=width,
            height=height, length=length, ref_image_size=ref_image_size,
            ref_images=images, ref_videos={"ref_video_0": source_frames},
            ref_video_audios={"ref_video_audio_0": source_audio} if source_audio is not None else {}))


class _Context(_Base):
    RETURN_TYPES = ("CONDITIONING", "LATENT", "INT", "INT", "INT")
    RETURN_NAMES = ("positive", "latent", "trim_frames", "insert_frame", "preserved_frames")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {**_common(), "audio_vae": ("VAE",),
                "source_frames": ("IMAGE",), "source_audio": ("AUDIO",),
                "source_fps": ("FLOAT", {"default": 24.0, "min": 24.0, "max": 24.0}),
                "context_length": ("INT", {"default": 39, "min": 5, "max": 9999}),
                "crop": (["disabled", "center"], {"default": "center"}),
                "audio_feather_ticks": ("INT", {"default": 8, "min": 0, "max": 256}),
                "insert_frame": ("INT", {"default": cls.default_insert, "min": 0})}}

    def prepare(self, clip, vae, prompt, width, height, length, audio_vae,
                source_frames, source_audio, source_fps, context_length,
                crop, audio_feather_ticks, insert_frame):
        positive, latent = _i2v(clip, vae, prompt, width, height, length)
        latent, trim, actual_insert, preserved = _context(
            latent=latent, vae=vae, audio_vae=audio_vae, source_frames=source_frames,
            source_audio=source_audio, source_fps=source_fps, context_length=context_length,
            crop=crop, audio_feather_ticks=audio_feather_ticks, insert_frame=insert_frame)
        return positive, latent, trim, actual_insert, preserved


class FluxdonH3Extend(_Context):
    """Prepare a masked source prefix. Use MCR trim and extension assembly after decoding."""
    default_insert = 0


class FluxdonH3Insert(_Context):
    """Prepare an interior masked context. Use MCR interior assembly after decoding."""
    default_insert = 51


class FluxdonH3Reframe(_Base):
    """Anchor a padded source clip as a guide, not a pixel-exact outpaint mask."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {**_common(), "audio_vae": ("VAE",), "guide_frames": ("IMAGE",)},
                "optional": {"source_audio": ("AUDIO",)}}

    def prepare(self, clip, vae, prompt, width, height, length, audio_vae, guide_frames, source_audio=None):
        positive, latent = _i2v(clip, vae, prompt, width, height, length)
        positive = _h3().MiniMaxH3AddGuide.execute(
            positive=positive, latent=latent, frame_idx=0, vae=vae, audio_vae=audio_vae,
            image=guide_frames, audio=source_audio)[0]
        return positive, latent


class FluxdonH3LipSync(_Base):
    """Audio-guided portrait animation; not a dedicated phoneme lip-sync model."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {**_common(), "audio_vae": ("VAE",),
                "portrait": ("IMAGE",), "speech": ("AUDIO",)}}

    def prepare(self, clip, vae, prompt, width, height, length, audio_vae, portrait, speech):
        positive, latent = _i2v(clip, vae, prompt, width, height, length, first_frame=portrait)
        positive = _h3().MiniMaxH3AddGuide.execute(
            positive=positive, latent=latent, frame_idx=0, vae=vae,
            audio_vae=audio_vae, audio=speech)[0]
        return positive, latent


class FluxdonH3CameraControl(_Base):
    """Prompt-guided camera motion; angles are descriptive, not geometric guarantees."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {**_common(), "first_frame": ("IMAGE",),
                "azimuth": ("INT", {"default": 45, "min": -360, "max": 360}),
                "elevation": ("INT", {"default": 10, "min": -90, "max": 90}),
                "dolly": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 5.0, "step": 0.1})}}

    def prepare(self, clip, vae, prompt, width, height, length, first_frame, azimuth, elevation, dolly):
        move = (f"Camera move: orbit {azimuth} degrees in azimuth (positive = move right around "
                f"the subject), {elevation} degrees in elevation (positive = rise above), and dolly "
                f"to {dolly}x the starting distance. One smooth continuous move, no cuts.")
        return tuple(_i2v(clip, vae, f"{prompt}\n{move}", width, height, length, first_frame))


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (
    FluxdonH3Recast, FluxdonH3Extend, FluxdonH3Reframe,
    FluxdonH3Insert, FluxdonH3LipSync, FluxdonH3CameraControl,
)}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FluxdonH3Recast": "Fluxdon H3 Recast (Local)",
    "FluxdonH3Extend": "Fluxdon H3 Extend (Local)",
    "FluxdonH3Reframe": "Fluxdon H3 Reframe (Local)",
    "FluxdonH3Insert": "Fluxdon H3 Insert (Local)",
    "FluxdonH3LipSync": "Fluxdon H3 Lip Sync (Local)",
    "FluxdonH3CameraControl": "Fluxdon H3 Camera Control (Local)",
}
