using System.Collections.Generic;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.U2D;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
	/// A UI cell that draws a chip's vector sprite as a mesh.
	///
	/// An imported vector sprite keeps its fills as a small gradient atlas: each
	/// vertex carries a ramp index (TexCoord2) and a position inside its gradient
	/// (uv), and a shader looks the colour up. That lookup does not survive the UI
	/// mesh — the index and the atlas texel size were both verified on the mesh
	/// that reached the canvas, and the sampled ramp still came out wrong — so the
	/// ramp is evaluated here instead, once per vertex, and written into the vertex
	/// colours. The mesh is still the chip's own paths: nothing is rasterised, and
	/// the icon stays sharp at any size.
	/// </summary>
	[RequireComponent( typeof( CanvasRenderer ) )]
	public sealed class ChipIconGraphic : MaskableGraphic
	{
		[SerializeField]
		Sprite m_sprite;

		public Sprite sprite
		{
			get { return m_sprite; }
			set
			{
				if ( m_sprite == value )
					return;

				m_sprite = value;
				SetAllDirty();
			}
		}

		[SerializeField]
		bool m_preserveAspect = true;

		public bool preserveAspect
		{
			get { return m_preserveAspect; }
			set
			{
				if ( m_preserveAspect == value )
					return;

				m_preserveAspect = value;
				SetVerticesDirty();
			}
		}

		/// <summary>Samples a gradient atlas; the vector shader does exactly this.</summary>
		sealed class Atlas
		{
			readonly Color32[] pixels;
			readonly int width, height;

			public Atlas( Texture2D texture )
			{
				width = texture.width;
				height = texture.height;

				// The imported atlas is not readable, so it is copied through a render
				// target, which needs no read/write permission on the asset. It holds
				// packed gradient data, not colour, so the copy must not run through
				// an sRGB encode.
				var rt = RenderTexture.GetTemporary( width, height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear );
				Graphics.Blit( texture, rt );
				var active = RenderTexture.active;
				RenderTexture.active = rt;
				var copy = new Texture2D( width, height, TextureFormat.RGBA32, false, true );
				copy.ReadPixels( new Rect( 0, 0, width, height ), 0, 0 );
				copy.Apply();
				RenderTexture.active = active;
				RenderTexture.ReleaseTemporary( rt );

				pixels = copy.GetPixels32();
				Object.DestroyImmediate( copy );
			}

			Color32 At( float u, float v )
			{
				int x = Mathf.Clamp( Mathf.FloorToInt( u * width ), 0, width - 1 );
				int y = Mathf.Clamp( Mathf.FloorToInt( v * height ), 0, height - 1 );
				return pixels[ y * width + x ];
			}

			static Vector2 Unpack( Color32 c )
			{
				// two 8-bit channels hold one 16-bit number: high byte, then low byte
				return new Vector2( c.r * 255f + c.g, c.b * 255f + c.a );
			}

			static Vector2 RadialAddress( Vector2 uv, Vector2 focus )
			{
				uv = ( uv - new Vector2( 0.5f, 0.5f ) ) * 2f;
				var direction = ( uv - focus ).normalized;

				// first hit of the ray from focus along direction on the unit circle
				float tca = Vector2.Dot( -focus, direction );
				float d2 = Vector2.Dot( focus, focus ) - tca * tca;
				float thc = Mathf.Sqrt( Mathf.Max( 0f, 1f - d2 ) );
				float t0 = tca - thc, t1 = tca + thc;
				float t = t0 < 0f ? Mathf.Max( t0, t1 ) : Mathf.Min( t0, t1 );
				var hit = focus + direction * t;
				var diff = hit - focus;

				if ( Mathf.Abs( diff.x ) > 0.0001f )
					return new Vector2( ( uv.x - focus.x ) / diff.x, 0f );
				if ( Mathf.Abs( diff.y ) > 0.0001f )
					return new Vector2( ( uv.y - focus.y ) / diff.y, 0f );
				return Vector2.zero;
			}

			public string Describe( float index, Vector2 uv )
			{
				var texel = new Vector2( 1f / width, 1f / height );
				var setting = new Vector2( 0.5f, index + 0.5f ) * texel;
				var settings = At( setting.x, setting.y );
				var pos = ( Unpack( At( setting.x + texel.x, setting.y ) ) + new Vector2( 0.5f, 0.5f ) ) * texel;
				var size = Unpack( At( setting.x + texel.x * 2f, setting.y ) ) * texel;
				return string.Format( "atlas {0}x{1} index {2} uv {3} settings {4} pos {5} size {6} -> {7}",
					width, height, index, uv, settings, pos, size, Eval( index, uv ) );
			}

			public Color32 Eval( float index, Vector2 uv )
			{
				var texel = new Vector2( 1f / width, 1f / height );
				var setting = new Vector2( 0.5f, index + 0.5f ) * texel;
				var settings = At( setting.x, setting.y );

				if ( settings.r > 0 )
				{
					var focus = new Vector2( settings.b / 255f - 0.5f, settings.a / 255f - 0.5f ) * 2f;
					uv = RadialAddress( uv, focus );
				}

				int addressing = Mathf.RoundToInt( settings.g );
				if ( addressing == 1 )
					uv.x = Mathf.Clamp01( uv.x );
				else if ( addressing == 2 )
				{
					float w = Mathf.Repeat( uv.x, 2f );
					uv.x = w > 1f ? 1f - Mathf.Repeat( w, 1f ) : w;
				}
				else
					uv.x = Mathf.Repeat( uv.x, 1f );

				var pos = ( Unpack( At( setting.x + texel.x, setting.y ) ) + new Vector2( 0.5f, 0.5f ) ) * texel;
				var size = Unpack( At( setting.x + texel.x * 2f, setting.y ) ) * texel;
				var sample = new Vector2( uv.x * size.x + pos.x, uv.y * size.y + pos.y );
				return At( sample.x, sample.y );
			}
		}

		static readonly Dictionary<Texture, Atlas> s_atlases = new Dictionary<Texture, Atlas>();

		static Atlas AtlasOf( Texture2D texture )
		{
			Atlas atlas;
			if ( s_atlases.TryGetValue( texture, out atlas ) && atlas != null )
				return atlas;

			atlas = new Atlas( texture );
			s_atlases[ texture ] = atlas;
			return atlas;
		}

		protected override void OnPopulateMesh( VertexHelper vh )
		{
			vh.Clear();
			if ( m_sprite == null )
				return;

			var vertices = m_sprite.vertices;
			var uvs = m_sprite.uv;
			var triangles = m_sprite.triangles;
			if ( vertices == null || vertices.Length == 0 || triangles == null )
				return;

			// a flat sprite has no vertex colours and only one gradient (index 0)
			var colors = new NativeSlice<Color32>();
			var index = new NativeSlice<Vector2>();
			if ( m_sprite.HasVertexAttribute( VertexAttribute.Color ) )
				colors = m_sprite.GetVertexAttribute<Color32>( VertexAttribute.Color );
			if ( m_sprite.HasVertexAttribute( VertexAttribute.TexCoord2 ) )
				index = m_sprite.GetVertexAttribute<Vector2>( VertexAttribute.TexCoord2 );

			bool hasColor = colors.Length > 0;
			bool hasIndex = index.Length > 0;
			var atlas = m_sprite.texture is Texture2D && hasIndex ? AtlasOf( (Texture2D) m_sprite.texture ) : null;

			// fit the sprite's own bounds into the cell, keeping its aspect
			var bounds = m_sprite.bounds.size;
			var rect = GetPixelAdjustedRect();
			var scale = new Vector2( rect.width / bounds.x, rect.height / bounds.y );
			if ( m_preserveAspect )
			{
				float fit = Mathf.Min( scale.x, scale.y );
				scale = new Vector2( fit, fit );
			}

			var tint = (Color) color;
			var center = rect.center;
			for ( int i = 0; i < vertices.Length; i++ )
			{
				var position = new Vector3( center.x + vertices[ i ].x * scale.x, center.y + vertices[ i ].y * scale.y, 0f );
				var fill = atlas != null ? (Color) atlas.Eval( index[ i ].x, uvs[ i ] ) : Color.white;
				if ( hasColor )
					fill *= colors[ i ];
				fill *= tint;

				// the icon shader paints these colours, so the sprite's uv is not
				// needed on the mesh; uv1 is left free for the UI
				vh.AddVert( position, fill, Vector2.zero );
			}

			for ( int i = 0; i + 2 < triangles.Length; i += 3 )
				vh.AddTriangle( triangles[ i ], triangles[ i + 1 ], triangles[ i + 2 ] );
		}
	}
}
