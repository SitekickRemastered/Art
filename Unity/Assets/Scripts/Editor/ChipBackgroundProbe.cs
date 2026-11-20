#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace Sitekick
{
	/// <summary>
	/// Toggles each background chip in the gallery scene and captures what the
	/// camera actually draws, next to the numbers that decide it: sprite bounds,
	/// world size after the transform, sorting order and the sprite's geometry.
	/// </summary>
	public static class ChipBackgroundProbe
	{
		public const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		public const string ReportPath = "Logs/chip-background-probe.txt";

		static readonly int[] Backgrounds = { 1, 2, 3, 4, 5, 6, 161, 177, 286 };

		public static void Run()
		{
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			var gallery = UnityEngine.Object.FindFirstObjectByType<ChipGallery>();
			if ( gallery == null )
			{
				Debug.LogError( "no ChipGallery in scene" );
				return;
			}

			var lines = new StringBuilder();
			var camera = Camera.main;
			lines.AppendLine( "camera: " + ( camera != null ? camera.orthographicSize + " ortho, clear " + camera.backgroundColor : "none" ) );
			foreach ( var layer in UnityEngine.Object.FindObjectsByType<EffectLayer>( FindObjectsSortMode.None ) )
				lines.AppendLine( "layer " + layer.layer + "  node " + layer.name + "  at " + layer.transform.position
					+ "  scale " + layer.transform.lossyScale + "  active " + layer.gameObject.activeInHierarchy );
			lines.AppendLine( "camera rect: " + ( camera != null ? camera.orthographicSize * 2f * camera.aspect + " x " + camera.orthographicSize * 2f : "none" ) );

			foreach ( var id in Backgrounds )
			{
				gallery.Toggle( id );
				var instance = FindInstance( id );
				lines.AppendLine();
				lines.AppendLine( "=== chip " + id + " ===" );
				if ( instance == null )
				{
					lines.AppendLine( "  no instance" );
				}
				else
				{
					// Unity does not run MonoBehaviour updates in edit mode, so the
					// backdrop fit has to be applied explicitly before capturing.
					foreach ( var fit in instance.GetComponentsInChildren<ChipBackdropFit>( true ) )
						fit.Apply();
					Dump( instance, lines );
				}

				Capture( camera, "Logs/bg-" + id.ToString( "0000" ) + ".png" );
				gallery.Toggle( id );
				lines.AppendLine( "  toggled off: " + ( FindInstance( id ) == null ? "removed" : "STILL PRESENT" ) );
			}

			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );
		}

		static GameObject FindInstance( int id )
		{
			var all = UnityEngine.Object.FindObjectsByType<Transform>( FindObjectsSortMode.None );
			var name = "Chip_" + id.ToString( "0000" ) + "_Effect";
			foreach ( var t in all )
				if ( t != null && t.name == name )
					return t.gameObject;
			return null;
		}

		static void Dump( GameObject root, StringBuilder lines )
		{
			lines.AppendLine( "  active: " + root.activeInHierarchy + "  scale " + root.transform.lossyScale );
			var group = root.GetComponentInChildren<SortingGroup>();
			if ( group != null )
				lines.AppendLine( "  sorting group: order " + group.sortingOrder + " layer " + group.sortingLayerName );

			foreach ( var r in root.GetComponentsInChildren<SpriteRenderer>( true ) )
			{
				var t = r.transform;
				var b = r.bounds;
				var sprite = r.sprite;
				var text = new StringBuilder();
				text.Append( "  " ).Append( NodePath( t, root.transform ) ).Append( "  enabled " ).Append( r.enabled )
					.Append( "  order " ).Append( r.sortingOrder )
					.Append( "  color " ).Append( r.color )
					.Append( "  world " ).Append( b.size.ToString( "0.00" ) )
					.Append( " @ " ).Append( b.center.ToString( "0.00" ) )
					.Append( "  scale " ).Append( t.lossyScale.ToString( "0.000" ) );
				if ( sprite == null )
					text.Append( "  NO SPRITE" );
				else
					text.Append( "  sprite " ).Append( sprite.name )
						.Append( " " ).Append( sprite.rect.size.ToString( "0" ) )
						.Append( " tris " ).Append( sprite.triangles.Length / 3 )
						.Append( " tex " ).Append( sprite.texture != null ? sprite.texture.width + "x" + sprite.texture.height : "none" );
				lines.AppendLine( text.ToString() );
			}

			if ( root.GetComponentsInChildren<SpriteRenderer>( true ).Length == 0 )
				lines.AppendLine( "  no SpriteRenderers at all" );
		}

		static string NodePath( Transform t, Transform root )
		{
			var parts = new List<string>();
			while ( t != null && t != root )
			{
				parts.Insert( 0, t.name );
				t = t.parent;
			}
			return string.Join( "/", parts.ToArray() );
		}

		static void Capture( Camera camera, string path )
		{
			if ( camera == null )
				return;
			// 4:3, the aspect the gallery scene is authored for
			const int w = 1440, h = 1080;
			var rt = new RenderTexture( w, h, 24, RenderTextureFormat.ARGB32 );
			var previous = camera.targetTexture;
			camera.targetTexture = rt;
			camera.Render();
			camera.targetTexture = previous;
			var active = RenderTexture.active;
			RenderTexture.active = rt;
			var tex = new Texture2D( w, h, TextureFormat.RGB24, false );
			tex.ReadPixels( new Rect( 0, 0, w, h ), 0, 0 );
			tex.Apply();
			RenderTexture.active = active;
			Directory.CreateDirectory( Path.GetDirectoryName( path ) );
			File.WriteAllBytes( path, tex.EncodeToPNG() );
			UnityEngine.Object.DestroyImmediate( tex );
			rt.Release();
			UnityEngine.Object.DestroyImmediate( rt );
		}
	}
}
#endif
