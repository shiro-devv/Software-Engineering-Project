"""The app's original line-art camera mascot, drawn as reusable inline SVG."""

from __future__ import annotations

from typing import Literal

Pose = Literal["walking", "standing", "wave"]


def mascot(size: int = 260, pose: Pose = "walking") -> str:
    """Return the camera mascot as inline SVG.

    Args:
        size: Rendered width in pixels.  The SVG keeps its aspect ratio.
        pose: ``walking`` spreads the legs, ``standing`` brings them together,
            and ``wave`` adds a taller wave arm.
    """
    if pose not in {"walking", "standing", "wave"}:
        pose = "walking"

    if pose == "walking":
        legs = """
            <path d="M143 224 C136 241 123 254 108 264" />
            <path d="M231 224 C240 240 249 252 261 261" />
            <ellipse cx="101" cy="272" rx="26" ry="13" transform="rotate(14 101 272)" />
            <ellipse cx="270" cy="269" rx="25" ry="13" transform="rotate(-15 270 269)" />
        """
        arm = """
            <path d="M103 151 C82 155 62 145 52 122" />
            <path d="M51 122 C42 119 31 111 27 98 C23 85 34 78 43 85 C48 75 62 76 64 88 C75 83 84 94 77 105 C87 110 81 125 69 124 C64 133 52 132 51 122 Z" />
            <path d="M34 91 C39 95 43 99 45 104" />
            <path d="M51 85 C53 92 56 98 60 102" />
            <path d="M70 92 C68 98 65 103 61 107" />
        """
    elif pose == "standing":
        legs = """
            <path d="M149 225 C146 241 141 253 137 263" />
            <path d="M225 225 C230 241 235 253 240 263" />
            <ellipse cx="133" cy="271" rx="24" ry="12" transform="rotate(6 133 271)" />
            <ellipse cx="245" cy="271" rx="24" ry="12" transform="rotate(-6 245 271)" />
        """
        arm = """
            <path d="M103 151 C83 154 65 142 55 120" />
            <path d="M54 120 C44 117 32 107 28 94 C24 81 35 74 44 81 C48 70 63 71 65 83 C77 78 86 89 79 101 C89 106 83 121 71 120 C66 130 54 129 54 120 Z" />
            <path d="M35 87 C40 91 44 96 46 101" />
            <path d="M52 81 C54 89 57 95 61 99" />
            <path d="M72 87 C70 94 67 100 63 104" />
        """
    else:  # wave - arm is higher and the hand is more open
        legs = """
            <path d="M148 225 C144 243 139 254 134 264" />
            <path d="M226 225 C231 242 236 253 241 264" />
            <ellipse cx="130" cy="272" rx="24" ry="12" transform="rotate(5 130 272)" />
            <ellipse cx="246" cy="272" rx="24" ry="12" transform="rotate(-5 246 272)" />
        """
        arm = """
            <path d="M104 147 C81 137 62 116 59 91" />
            <path d="M58 91 C49 87 39 75 37 61 C35 47 47 42 55 51 C61 39 75 42 76 55 C89 52 96 65 87 75 C97 82 89 96 77 94 C72 103 60 101 58 91 Z" />
            <path d="M44 54 C48 60 50 66 51 72" />
            <path d="M61 48 C62 56 64 63 67 69" />
            <path d="M80 58 C77 65 73 71 68 76" />
        """

    return f"""
    <svg class="camera-mascot" width="{int(size)}" height="{int(size)}"
         viewBox="0 0 330 315" fill="none" xmlns="http://www.w3.org/2000/svg"
         role="img" aria-labelledby="mascot-title">
        <title id="mascot-title">Friendly waving camera mascot</title>
        <g stroke="currentColor" stroke-width="5" stroke-linecap="round"
           stroke-linejoin="round">
            <g>
                {legs}
            </g>
            <g>
                {arm}
            </g>
            <rect x="78" y="125" width="28" height="46" rx="8" />
            <path d="M86 141 L98 141" />
            <path d="M160 91 L166 67 C168 60 172 57 180 57 L205 57 C213 57 217 60 219 67 L226 91" />
            <rect x="238" y="78" width="27" height="17" rx="8" />
            <rect x="98" y="89" width="178" height="139" rx="19" />
            <circle cx="187" cy="161" r="52" />
            <circle cx="187" cy="161" r="41" fill="var(--mascot-lens, #E4EDF1)" />
            <path d="M168 151 C172 157 178 157 182 151" />
            <path d="M195 151 C199 157 205 157 209 151" />
            <path d="M169 168 C178 181 197 181 206 168" />
        </g>
    </svg>
    """
