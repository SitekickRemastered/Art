using Sitekick;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class EditorSitekick : MonoBehaviour
{
	[SerializeField]
	protected GameObject bodyObj, eyesObj, antennaObj;

	/// <summary>
	/// The pieces painted with the chosen colour.
	///
	/// The art is a template: white and the two baked shade greys, so one
	/// multiply turns it into the Sitekick at that colour.  Tuesday.swf's
	/// sitekick at #FFCC00 is the reference -- white becomes #FFCC00, the
	/// 0.835 shade becomes #D59A00 and the 0.698 shade #B27600 -- and every
	/// other colour moves the same ratios, which is how the site's own chips
	/// shade.  The gloss is listed separately because it is not a ratio of the
	/// colour but a lift of it (see <see cref="shineRenderers"/>).
	/// </summary>
	[Header( "Colour" )]
	[Tooltip( "Renderers painted with the chosen colour. The art carries the shading." )]
	[SerializeField]
	protected List<Renderer> coloredRenderers = new List<Renderer>();

	/// <summary>
	/// The upper-left shine, painted with the colour lifted toward white.
	///
	/// Tuesday's gloss is #FFEB99 over #FFCC00, which is white at 60 % over the
	/// body colour, so its tint is <c>C + 0.6 (1 - C)</c> --
	/// <see cref="SitekickColor.Lift"/>.  Baking that into the art is
	/// impossible: the blue channel would need a 1.67 ratio where the body's is
	/// zero.  As a lift the gloss still follows the picker like everything else,
	/// and at #FFCC00 it lands on exactly the pixels the white overlay made.
	/// At white it is white on white, which is why it only shows once the body
	/// takes a colour.
	/// </summary>
	[Tooltip( "The gloss: painted with the chosen colour lifted 60 % toward white (SitekickColor.Lift)." )]
	[SerializeField]
	protected List<Renderer> shineRenderers = new List<Renderer>();

	/// <summary>How far the gloss lifts the body colour toward white.</summary>
	public const float GlossLift = 0.6f;

	protected List<SpriteRenderer> sprites = null;

	protected ChipData.EffectFlags currentEffectFlags;

	void OnEnable()
	{
		SitekickColor.Changed += SetColor;
	}

	void OnDisable()
	{
		SitekickColor.Changed -= SetColor;
	}

	public void SetEffectFlags( ChipData.EffectFlags effectFlags )
	{
		if ( currentEffectFlags == effectFlags )
			return;

		currentEffectFlags = effectFlags;

		if ( bodyObj != null )
			bodyObj.SetActive( ( effectFlags & ChipData.EffectFlags.HideBody ) != ChipData.EffectFlags.HideBody );

		if ( eyesObj != null )
			eyesObj.SetActive( ( effectFlags & ChipData.EffectFlags.HideEyes ) != ChipData.EffectFlags.HideEyes );

		if ( antennaObj != null )
			antennaObj.SetActive( ( effectFlags & ChipData.EffectFlags.HideAntenna ) != ChipData.EffectFlags.HideAntenna );
	}

	/// <summary>
	/// Paints the body and publishes the colour, so every chip effect on show --
	/// and every one switched on later -- follows it.
	/// </summary>
	public void SetColor( Color color )
	{
		foreach ( var renderer in coloredRenderers )
			SitekickColor.Apply( renderer, color );

		if ( shineRenderers != null )
		{
			var shine = SitekickColor.Lift( color, GlossLift );
			foreach ( var renderer in shineRenderers )
				SitekickColor.Apply( renderer, shine );
		}

		// the chip effects paint themselves from the same value; publishing only
		// when it moves is what keeps this from re-entering through Changed
		if ( SitekickColor.Current != color )
			SitekickColor.Set( color );
	}

	public void SetAlpha( float alpha )
	{
		if ( sprites == null )
			sprites = GetComponentsInChildren<SpriteRenderer>().ToList();

		foreach ( var sprite in sprites )
		{
			var color = sprite.color;
			color.a = alpha;
			sprite.color = color;
		}
	}
}
