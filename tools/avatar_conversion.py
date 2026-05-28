"""Image → Jarvis avatar conversion (prompt + routing builder).

The Android app lets the user upload a photo and turn it into their
Jarvis avatar in one of several styles, in two renderer flavours:

* **2D pixel / animated-pixel** — handled fully on-device by
  ``AvatarPixelator`` (no cloud, no key). This module is *not* involved
  in that path.
* **Stylized character portrait / texture** and **image-to-3D** — these
  reuse the existing cloud image-gen path
  (``tools.image_generation_tool``) and an image-to-3D model. This module
  owns the *request shaping* for those: it maps a chosen
  :class:`AvatarConversionStyle` + target renderer to the prompt and
  parameters the image-gen tool expects.

Keeping request-shaping here (pure, unit-tested) means the actual
submission stays the single canonical code path in
``image_generation_tool`` — this module never makes a network call, so
it's safe to import and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AvatarConversionStyle(str, Enum):
    """Mirrors the Kotlin ``AvatarStyle`` the picker offers."""

    NAVY_GOLD = "NAVY_GOLD"
    CYAN_GLOW = "CYAN_GLOW"
    MONOCHROME_TERMINAL = "MONOCHROME_TERMINAL"
    REALISTIC = "REALISTIC"


class AvatarRenderKind(str, Enum):
    """Mirrors the Kotlin ``AvatarRenderKind``."""

    ANIMATED_PIXEL = "ANIMATED_PIXEL"
    RIVE = "RIVE"
    CHARACTER_3D = "CHARACTER_3D"


_STYLE_PROMPTS: dict[AvatarConversionStyle, str] = {
    AvatarConversionStyle.NAVY_GOLD: (
        "navy-and-gold JARVIS holographic interface aesthetic, deep blue "
        "with luminous gold edge lighting, clean and premium"
    ),
    AvatarConversionStyle.CYAN_GLOW: (
        "cyan neon glow, holographic Iron-Man HUD energy, soft rim light, "
        "translucent and futuristic"
    ),
    AvatarConversionStyle.MONOCHROME_TERMINAL: (
        "monochrome terminal phosphor look, single-hue green-on-black, "
        "retro command-line aesthetic"
    ),
    AvatarConversionStyle.REALISTIC: (
        "photorealistic stylized character, cinematic key lighting, "
        "subtle sci-fi grading"
    ),
}

# A character avatar wants a clean, centered, full-body or bust subject
# on a transparent/neutral background so the renderer can composite it.
_RENDER_DIRECTIVES: dict[AvatarRenderKind, str] = {
    AvatarRenderKind.ANIMATED_PIXEL: (
        "single centered character, full body, neutral pose, clean silhouette, "
        "plain background for spritesheet extraction"
    ),
    AvatarRenderKind.RIVE: (
        "single centered character, front-facing, simple flat-vector friendly "
        "shapes, plain background, clear limb separation for rigging"
    ),
    AvatarRenderKind.CHARACTER_3D: (
        "single centered character, T-pose, even diffuse lighting, plain "
        "background, consistent proportions suitable for 3D reconstruction"
    ),
}


@dataclass(frozen=True)
class AvatarConversionRequest:
    """The shaped request handed to the image-gen tool."""

    prompt: str
    aspect_ratio: str
    transparent_background: bool
    needs_image_to_3d: bool
    source_note: str

    def as_image_tool_kwargs(self) -> dict:
        """kwargs for ``tools.image_generation_tool.image_generate_tool``."""
        return {
            "prompt": self.prompt,
            "aspect_ratio": self.aspect_ratio,
            "transparent_background": self.transparent_background,
        }


def build_conversion_request(
    style: AvatarConversionStyle,
    render_kind: AvatarRenderKind,
    *,
    subject_hint: str = "the uploaded portrait",
) -> AvatarConversionRequest:
    """Map (style, renderer) → a concrete image-gen request.

    ``CHARACTER_3D`` additionally flags the image-to-3D follow-up step;
    the runtime submits the stylized image to an image-to-3D model and
    caches the resulting ``.glb`` in the app's avatar directory.
    """
    style_clause = _STYLE_PROMPTS[style]
    render_clause = _RENDER_DIRECTIVES[render_kind]
    prompt = (
        f"Stylized avatar of {subject_hint}. Style: {style_clause}. "
        f"Composition: {render_clause}."
    )
    return AvatarConversionRequest(
        prompt=prompt,
        # square works for portraits/sprites; 3D recon prefers square too
        aspect_ratio="1:1",
        transparent_background=render_kind != AvatarRenderKind.CHARACTER_3D,
        needs_image_to_3d=render_kind == AvatarRenderKind.CHARACTER_3D,
        source_note=f"{style.value}/{render_kind.value}",
    )
