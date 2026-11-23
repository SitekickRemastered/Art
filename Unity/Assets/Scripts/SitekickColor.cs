using System;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// One colour for the Sitekick and everything it wears, and the arithmetic
	/// Flash paints it with.
	///
	/// sitekick.swf has no colour data of its own: every painted clip calls
	/// `paint(this[, tone])`, and the site defines that as
	///
	///     ra/ga/ba = rvalue/gvalue/bvalue      (0..100, a plain multiply)
	///     "shadow" -20, "shadow2" -30, "shadow3" -40
	///
	/// so a painted clip's drawing is multiplied by the colour, and a shaded
	/// piece by the colour less its tone.  A clip painted inside another painted
	/// clip carries both multipliers, because Flash multiplies the colour
	/// transform down the display list: art x C x (C - tone).
	///
	/// The colour lives here rather than in each prefab so that everything that
	/// follows it -- the body, the effects on show, an effect switched on later --
	/// reads the same value.  A prefab only lists which renderers are painted
	/// (ChipEffect.coloredRenderers, EditorSitekick.coloredRenderers); this is
	/// the colour they get and the math they get it by.  `_Color` on a sprite
	/// multiplies the sprite's own art, which is exactly the channel Flash
	/// transforms, so a white piece becomes the colour and a grey shading run
	/// becomes a darker shade of it -- which is why the body's art carries the
	/// shades Tuesday.swf baked (white and two grey ratios) and needs nothing but
	/// the multiply -- with the gloss on top as a lift of the colour, see
	/// <see cref="Lift"/>.
	///
	/// <see cref="Tint"/> is the other half of the site's colouring: the tone
	/// arithmetic `paint(clip, tone)` uses, which sitekick.swf's own clips and
	/// the movie chips need.  The static body and chips do not call it.
	/// </summary>
	public static class SitekickColor
	{
		public static Color Current { get; private set; } = Color.white;

		/// <summary>Raised whenever the chosen colour changes, with the new colour.</summary>
		public static event Action<Color> Changed;

		[RuntimeInitializeOnLoadMethod( RuntimeInitializeLoadType.SubsystemRegistration )]
		static void ResetStatics()
		{
			Current = Color.white;
			Changed = null;
		}

		public static void Set( Color color )
		{
			Current = color;
			Changed?.Invoke( color );
		}

		/// <summary>
		/// The multiplier one painted clip draws with.
		/// </summary>
		/// <param name="color">The colour the user picked, as 0..1 channels.</param>
		/// <param name="tone">The shade this clip was painted with, in points: 20, 30 or 40.</param>
		/// <param name="paintedParent">
		/// True when the clip also sits inside a painted clip, whose multiplier
		/// is still in effect: Flash nests them, so the piece is multiplied by
		/// the colour twice (the body shell's shadow runs are the ones that need
		/// it).
		/// </param>
		public static Color Tint( Color color, float tone, bool paintedParent = false )
		{
			var drop = tone / 100f;
			return new Color(
				Channel( color.r, drop, paintedParent ),
				Channel( color.g, drop, paintedParent ),
				Channel( color.b, drop, paintedParent ),
				color.a );
		}

		static float Channel( float value, float drop, bool paintedParent )
		{
			var own = Mathf.Max( 0f, value - drop );
			return paintedParent ? own * value : own;
		}

		/// <summary>
		/// A gloss layer's tint: the colour pulled `amount` of the way to white.
		///
		/// The body's shine is white at 60 % in Tuesday.swf, and white over a
		/// colour composites to `C + amount (1 - C)` -- at #FFCC00 that is
		/// #FFEB99, the pale yellow the gloss shows.  Baking that as an art ratio
		/// is impossible (it would need 1.15 on green and far more than 1 on blue,
		/// where the body has none), so the gloss ships as opaque white art and
		/// gets this tint instead: identical pixels, but the layer follows the
		/// colour like every other run instead of washing it white.
		/// </summary>
		public static Color Lift( Color color, float amount )
		{
			return new Color(
				color.r + ( 1f - color.r ) * amount,
				color.g + ( 1f - color.g ) * amount,
				color.b + ( 1f - color.b ) * amount,
				color.a );
		}

		/// <summary>Sets a sprite's tint; `_Color` is the multiply Flash's paint applies.</summary>
		public static void Apply( Renderer renderer, Color tint )
		{
			if ( renderer is SpriteRenderer sprite )
			{
				var block = new MaterialPropertyBlock();
				sprite.GetPropertyBlock( block );

				block.SetColor( "_Color", tint );
				sprite.SetPropertyBlock( block );
			}
		}
	}
}
