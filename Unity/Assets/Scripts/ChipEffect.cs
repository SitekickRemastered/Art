using System.Collections.Generic;
using UnityEngine;

namespace Sitekick
{
	public class ChipEffect : MonoBehaviour
	{
		[SerializeField]
		protected List<Renderer> coloredRenderers = new List<Renderer>();

#if UNITY_EDITOR
		private List<Renderer> appliedRenderers = new List<Renderer>();
#endif

		public void ApplyColor( Color color )
		{
#if UNITY_EDITOR
			if ( appliedRenderers != null && appliedRenderers.Count > 0 )
			{
				foreach ( var renderer in appliedRenderers )
				{
					if ( renderer is SpriteRenderer sr )
					{
						var mpb = new MaterialPropertyBlock();
						sr.GetPropertyBlock( mpb );

						mpb.SetColor( "_Color", Color.white );
						sr.SetPropertyBlock( mpb );
					}
				}

				appliedRenderers.Clear();
			}

			if ( coloredRenderers != null && coloredRenderers.Count > 0 )
			{
				foreach ( var renderer in coloredRenderers )
				{
					if ( renderer is SpriteRenderer sr )
					{
						var mpb = new MaterialPropertyBlock();
						sr.GetPropertyBlock( mpb );

						mpb.SetColor( "_Color", color );
						sr.SetPropertyBlock( mpb );

						if ( !appliedRenderers.Contains( renderer ) )
							appliedRenderers.Add( renderer );
					}
				}
			}
#endif
		}
	}
}