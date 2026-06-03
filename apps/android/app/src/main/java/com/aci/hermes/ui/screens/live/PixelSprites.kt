package com.aci.hermes.ui.screens.live

/**
 * Hand-authored pixel-art avatars — a wide, readable starter set (people, a
 * robot, and pets) so JARVIS opens as an actual character, not a stick figure.
 *
 * Each sprite is a small grid of palette keys (one char per pixel), chosen for
 * **silhouette readability** first (the #1 pixel-art rule) with a compact
 * 6–12 colour palette. They render at any size via [PixelSpriteAvatar] and
 * breathe/animate through the shared [AvatarInputs] contract. Finished
 * sprite-sheet / Rive art can later replace these behind the same wiring.
 */
data class PixelSprite(
    val id: String,
    val label: String,
    val rows: List<String>,
    val palette: Map<Char, Long>,
)

object PixelSprites {

    // Shared palette keys: ' ' transparent. Per-sprite maps pick the hues.
    private const val T = 0xFF1A1A22 // outline / ink
    private const val STEEL = 0xFFB8C2D0
    private const val STEEL_D = 0xFF6B7686
    private const val CYAN = 0xFF36D6E7
    private const val GOLD = 0xFFCB8B26
    private const val SKIN = 0xFFE8B98C
    private const val SKIN_D = 0xFFB98760
    private const val NAVY = 0xFF1F3A5F
    private const val NAVY_L = 0xFF35597F
    private const val ORANGE = 0xFFE0792E
    private const val ORANGE_D = 0xFFB45A1E
    private const val WHITE = 0xFFF3F0EA
    private const val GREY = 0xFF8A8A92
    private const val GREY_D = 0xFF55555C
    private const val BROWN = 0xFF8A5A34
    private const val BROWN_D = 0xFF5E3C22
    private const val PINK = 0xFFE69BB0

    /** Robot — the default. Antenna + visor eyes read instantly at any size. */
    private val ROBOT = PixelSprite(
        id = "robot", label = "Robot",
        rows = listOf(
            "      o o       ",
            "      | |       ",
            "    ssssssss    ",
            "   sSSSSSSSSs   ",
            "   sSccccccSs   ",
            "   sScVVVVcSs   ",
            "   sSccccccSs   ",
            "   sSSSSSSSSs   ",
            "  a sSSSSSSs a  ",
            "  a snnnnnns a  ",
            "  a snGGGGns a  ",
            "  a snnnnnns a  ",
            "    snnnnnns    ",
            "    sSS  SSs    ",
            "    ll    ll    ",
            "   lll    lll   ",
        ),
        palette = mapOf(
            'o' to CYAN, '|' to STEEL_D, 's' to STEEL_D, 'S' to STEEL,
            'c' to T, 'V' to CYAN, 'a' to STEEL_D, 'n' to NAVY, 'G' to GOLD,
            'l' to GREY_D,
        ),
    )

    /** Explorer — a friendly humanoid (hair, face, jacket). */
    private val EXPLORER = PixelSprite(
        id = "explorer", label = "Explorer",
        rows = listOf(
            "     hhhhhh     ",
            "    hhhhhhhh    ",
            "   hhKKKKKKhh   ",
            "   hKkkkkkkKh   ",
            "   kkffffffkk   ",
            "   kfeffffefk   ",
            "   kffffffffk   ",
            "   kfffmmfffk   ",
            "    kffffffk    ",
            "    nnnnnnnn    ",
            "   nnGnnnnGnn   ",
            "  s nnnnnnnn s  ",
            "  s nnnnnnnn s  ",
            "    nnn  nnn    ",
            "    bbb  bbb    ",
            "   bbbb  bbbb   ",
        ),
        palette = mapOf(
            'h' to BROWN_D, 'K' to BROWN, 'k' to SKIN_D, 'f' to SKIN,
            'e' to T, 'm' to BROWN_D, 'n' to NAVY, 'G' to GOLD, 's' to SKIN,
            'b' to GREY_D,
        ),
    )

    /** Astronaut — helmet + visor, a calm classic. */
    private val ASTRONAUT = PixelSprite(
        id = "astronaut", label = "Astronaut",
        rows = listOf(
            "    wwwwww     ",
            "   wWWWWWWw    ",
            "  wWvvvvvvWw   ",
            "  wWvVVVVvWw   ",
            "  wWvvvvvvWw   ",
            "   wWWWWWWw    ",
            "  w wwwwww w   ",
            "  w wWWWWw w   ",
            "  w wWGGWw w   ",
            "    wWWWWw     ",
            "    wWWWWw     ",
            "    wW  Ww     ",
            "    ww  ww     ",
            "    WW  WW     ",
            "   WWW  WWW    ",
            "              ",
        ),
        palette = mapOf(
            'w' to STEEL_D, 'W' to WHITE, 'v' to NAVY, 'V' to CYAN, 'G' to GOLD,
        ),
    )

    /** Cat — ears + tail silhouette. */
    private val CAT = PixelSprite(
        id = "cat", label = "Cat",
        rows = listOf(
            "  e        e   ",
            "  eOe      eOe  ",
            "  eOOe    eOOe  ",
            "  eOOOOOOOOOe   ",
            "  eOyOOOOyOe    ",
            "  eOOOOOOOOe    ",
            "  eOOppppOOe    ",
            "   eOOOOOOe     ",
            "   OOOOOOOO  t  ",
            "  OOOOOOOOO tt  ",
            "  OOOOOOOOOOt   ",
            "  OOOOOOOOOO    ",
            "  OO OO OO OO   ",
            "  OO OO OO OO   ",
            "               ",
            "               ",
        ),
        palette = mapOf(
            'e' to T, 'O' to ORANGE, 'y' to GOLD, 'p' to PINK, 't' to ORANGE_D,
        ),
    )

    /** Dog — floppy ears + snout. */
    private val DOG = PixelSprite(
        id = "dog", label = "Dog",
        rows = listOf(
            "   dd    dd    ",
            "  dddd  dddd   ",
            "  ddBBBBBBdd   ",
            "  dBByyyyBBd   ",
            "  dBBBBBBBBd   ",
            "  dBBwwwwBBd   ",
            "   dBwnnwBd    ",
            "   dBBwwBBd    ",
            "    BBBBBB     ",
            "   BBBBBBBB    ",
            "  BBBBBBBBBB   ",
            "  BBBBBBBBBB   ",
            "  BB BB BB BB  ",
            "  BB BB BB BB  ",
            "              ",
            "              ",
        ),
        palette = mapOf(
            'd' to BROWN_D, 'B' to BROWN, 'y' to GOLD, 'w' to WHITE, 'n' to T,
        ),
    )

    /** Fox — sharp ears, white cheeks. */
    private val FOX = PixelSprite(
        id = "fox", label = "Fox",
        rows = listOf(
            "  x        x   ",
            "  xx      xx   ",
            "  xXx    xXx   ",
            "  xXXXXXXXXx   ",
            "  xXXeXXeXXx   ",
            "  xXwwwwwwXx   ",
            "   xwwnnwwx    ",
            "   xXwwwwXx    ",
            "    XXXXXX  f  ",
            "   XXXXXXX ff  ",
            "  XXXXXXXXXf   ",
            "  XXXXXXXXX    ",
            "  XX XX XX XX  ",
            "  ww ww ww ww  ",
            "              ",
            "              ",
        ),
        palette = mapOf(
            'x' to ORANGE_D, 'X' to ORANGE, 'e' to T, 'w' to WHITE, 'n' to T, 'f' to ORANGE_D,
        ),
    )

    /** The ordered catalog shown in the picker / cycled on tap. Robot first. */
    val catalog: List<PixelSprite> = listOf(ROBOT, EXPLORER, ASTRONAUT, CAT, DOG, FOX)

    val default: PixelSprite get() = ROBOT

    fun byId(id: String?): PixelSprite =
        catalog.firstOrNull { it.id == id } ?: default

    fun next(id: String?): PixelSprite {
        val i = catalog.indexOfFirst { it.id == id }
        return catalog[(if (i < 0) 0 else i + 1) % catalog.size]
    }
}
