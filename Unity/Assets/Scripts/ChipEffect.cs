using System.Collections.Generic;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// The pieces of an effect the Sitekick's colour reaches.
	///
	/// Flash paints every clip whose instance name matches /fill/ in the user's
	/// colour -- `corus.effects.base.BasePaint` walks the effect's children and
	/// applies `new ColorTransform(0,0,0,1,r,g,b,0)`, a flat silhouette that keeps
	/// the clip's alpha.  The importer splits those clips out of the rest of an
	/// effect's drawing and lists them here; every other renderer is left alone,
	/// which is what makes a chip without any fill clip stay uncoloured.
	///
	/// This list is the whole authoring surface for a chip's colouring: drag the
	/// renderers Flash would paint into "Colored Renderers" and they follow the
	/// Sitekick's colour by themselves.  Nothing per-renderer has to be set up,
	/// because the shading is already in the art -- a grey run becomes a darker
	/// shade of the colour under the multiply, exactly as `paint(clip,"shadow")`
	/// does.  The colour itself is <see cref="SitekickColor.Current"/>, which the
	/// gallery sets; a chip spawned later reads it as it switches on.
	/// </summary>
	public class ChipEffect : MonoBehaviour
	{
		[Tooltip( "Renderers Flash paints with the Sitekick's colour. Everything else keeps its own colours." )]
		[SerializeField]
		protected List<Renderer> coloredRenderers = new List<Renderer>();

		protected readonly List<Renderer> applied = new List<Renderer>();

		public int ColoredRendererCount => coloredRenderers != null ? coloredRenderers.Count : 0;

		public IList<Renderer> ColoredRenderers => coloredRenderers;

		protected void OnEnable()
		{
			SitekickColor.Changed += ApplyColor;
			ApplyColor( SitekickColor.Current );
		}

		protected void OnDisable()
		{
			SitekickColor.Changed -= ApplyColor;
		}

		/// <summary>Tints the colour-bearing pieces, or clears them back to white.</summary>
		public void ApplyColor( Color color )
		{
			foreach ( var renderer in applied )
			{
				if ( renderer != null )
					SitekickColor.Apply( renderer, Color.white );
			}

			applied.Clear();

			if ( coloredRenderers == null )
				return;

			foreach ( var renderer in coloredRenderers )
			{
				if ( renderer == null )
					continue;

				SitekickColor.Apply( renderer, color );
				applied.Add( renderer );
			}
		}
	}
}
