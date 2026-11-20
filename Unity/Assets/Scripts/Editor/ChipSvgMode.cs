#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.U2D;
using Unity.VectorGraphics;
using Unity.VectorGraphics.Editor;

namespace Sitekick
{
	/// <summary>
	/// Switches the chip SVGs from rasterised sprites (a texture per sprite at
	/// up to 2048x2048) to vector sprites, which keep the geometry and are
	/// tessellated at runtime instead of being baked into the player.
	/// </summary>
	public static class ChipSvgMode
	{
		public const string ReportPath = "Logs/chip-svg-mode.txt";
		public const string RenderPath = "Logs/chip-gallery-render.png";
		public const string Root = "Assets/Chips";

		[MenuItem( "Sitekick/Chip SVG/Switch All To Vector" )]
		public static void AllFromMenu()
		{
			Switch( 0 );
		}

		[MenuItem( "Sitekick/Chip SVG/Switch 8 To Vector" )]
		public static void SampleFromMenu()
		{
			Switch( 8 );
		}

		[MenuItem( "Sitekick/Chip SVG/Report" )]
		public static void ReportFromMenu()
		{
			Report();
		}

		/// <summary>Batch entry point. limit 0 switches every chip SVG.</summary>
		public static void Run()
		{
			Switch( 0 );
		}

		/// <summary>Batch entry point: the first few sprites, to prove the import.</summary>
		public static void RunSample()
		{
			Switch( 8 );
		}

		/// <summary>Batch entry point for the report only.</summary>
		public static void Check()
		{
			Report();
		}

		public static string[] Paths()
		{
			return Directory.GetFiles( Root, "*.svg", SearchOption.AllDirectories )
				.Select( p => p.Replace( '\\', '/' ) )
				.OrderBy( p => p, StringComparer.Ordinal )
				.ToArray();
		}

		public static void Switch( int limit )
		{
			var lines = new List<string>();
			var svgType = typeof( SVGImporter );
			lines.Add( "SVGType: " + string.Join( ", ", Enum.GetNames( typeof( SVGType ) )
				.Select( n => n + "=" + (int)(object)Enum.Parse( typeof( SVGType ), n ) ).ToArray() ) );

			var paths = Paths();
			if ( limit > 0 )
				paths = paths.Take( limit ).ToArray();

			lines.Add( "switching " + paths.Length + " svg to vector" );

			int switched = 0, missing = 0;
			var before = new List<string>();

			foreach ( var path in paths )
			{
				var importer = AssetImporter.GetAtPath( path ) as SVGImporter;
				if ( importer == null )
				{
					missing++;
					continue;
				}

				if ( switched < 8 )
					before.Add( Describe( path ) );

				importer.SvgType = SVGType.VectorSprite;
				importer.SvgPixelsPerUnit = 400f;
				importer.TessellationMode = TessellationMode.Triangulation;
				importer.SaveAndReimport();
				switched++;
			}

			AssetDatabase.Refresh();

			lines.Add( "switched: " + switched + ", no importer: " + missing );

			foreach ( var line in before )
				lines.Add( "before | " + line );

			foreach ( var path in paths.Take( 8 ) )
				lines.Add( "after  | " + Describe( path ) );

			lines.Add( "RESULT: " + ( switched > 0 ? "OK" : "FAIL" ) );
			Write( lines );
		}

		/// <summary>Loads every chip sprite and reports what the build would carry.</summary>
		public static void Report()
		{
			var lines = new List<string>();
			var paths = Paths();

			long texture = 0, vertices = 0;
			int sprites = 0, largest = 0, raster = 0, empty = 0, scaled = 0;
			string largestPath = "";

			foreach ( var path in paths )
			{
				var sprite = AssetDatabase.LoadAssetAtPath<Sprite>( path );
				if ( sprite == null )
				{
					lines.Add( "no sprite: " + path );
					continue;
				}

				sprites++;
				var tex = sprite.texture;
				int side = tex != null ? Mathf.Max( tex.width, tex.height ) : 0;
				texture += side * side * 4L;
				vertices += sprite.vertices.Length;

				if ( side > largest )
				{
					largest = side;
					largestPath = path;
				}

				if ( side > 512 )
					raster++;

				if ( sprite.vertices.Length == 0 && importerType( path ) == "VectorSprite" )
					empty++;

				if ( sprite.pixelsPerUnit < 399f )
					scaled++;
			}

			lines.Add( "sprites: " + sprites );
			lines.Add( "texture payload (RGBA32): " + ( texture / 1048576.0 ).ToString( "0.0" ) + " MiB" );
			lines.Add( "largest texture: " + largest + " px (" + largestPath + ")" );
			lines.Add( "sprites with a texture over 512 px: " + raster );
			lines.Add( "sprite vertices total: " + vertices );
			lines.Add( "vector sprites with no geometry: " + empty );
			lines.Add( "sprites with a rescaled importer: " + scaled );

			foreach ( var path in paths.Take( 10 ) )
				lines.Add( "sample | " + Describe( path ) );

			lines.Add( "RESULT: " + ( sprites > 0 ? "OK" : "FAIL" ) );
			Write( lines );
		}

		static string Describe( string path )
		{
			var importer = AssetImporter.GetAtPath( path ) as SVGImporter;
			var sprite = AssetDatabase.LoadAssetAtPath<Sprite>( path );
			var tex = sprite != null ? sprite.texture : null;

			return Path.GetFileName( path ) +
				" type=" + ( importer != null ? importer.SvgType.ToString() : "?" ) +
				" texture=" + ( tex != null ? tex.width + "x" + tex.height : "none" ) +
				" verts=" + ( sprite != null ? sprite.vertices.Length : -1 ) +
				" rect=" + ( sprite != null ? sprite.rect.width + "x" + sprite.rect.height : "?" ) +
				" ppu=" + ( sprite != null ? sprite.pixelsPerUnit.ToString( "0.##" ) : "?" ) +
				" world=" + ( sprite != null ? sprite.bounds.size.x.ToString( "0.###" ) + "x" + sprite.bounds.size.y.ToString( "0.###" ) : "?" ) +
				" aa=" + ( sprite != null ? HasArcEncoding( sprite ).ToString() : "?" );
		}

		/// <summary>
		/// Compares every sprite in one chip effect with the world size the old
		/// raster sprite had (texture size / 400), to catch scale drift.
		/// </summary>
		[MenuItem( "Sitekick/Chip SVG/Part Scales" )]
		public static void PartsFromMenu()
		{
			Parts();
		}

		public static void Parts()
		{
			var lines = new List<string>();
			const int chipId = 7;
			var prefabPath = "Assets/Chips/0001-0100/Chip_0007/Chip_0007_Effect.prefab";
			var prefab = AssetDatabase.LoadAssetAtPath<GameObject>( prefabPath );
			if ( prefab == null )
			{
				lines.Add( "missing " + prefabPath );
				Write( lines );
				return;
			}

			var instance = UnityEngine.Object.Instantiate( prefab );
			try
			{
				lines.Add( "chip " + chipId + " parts" );
				foreach ( var renderer in instance.GetComponentsInChildren<SpriteRenderer>( true ) )
				{
					var sprite = renderer.sprite;
					if ( sprite == null )
					{
						lines.Add( renderer.transform.name + ": no sprite" );
						continue;
					}

					var path = AssetDatabase.GetAssetPath( sprite );
					int tw = 0, th = 0;
					if ( File.Exists( path + ".meta" ) )
					{
						foreach ( var line in File.ReadAllLines( path + ".meta" ) )
						{
							var t = line.Trim();
							if ( t.StartsWith( "textureWidth:" ) )
								tw = int.Parse( t.Substring( 13 ).Trim() );
							else if ( t.StartsWith( "textureHeight:" ) )
								th = int.Parse( t.Substring( 14 ).Trim() );
						}
					}

					var now = sprite.bounds.size;
					var was = new Vector2( tw / 400f, th / 400f );
					lines.Add( string.Format( "{0,-22} {1,-34} now {2:0.###}x{3:0.###} was {4:0.###}x{5:0.###} dx {6:0.###} dy {7:0.###}",
						renderer.transform.name, Path.GetFileName( path ), now.x, now.y, was.x, was.y,
						now.x - was.x, now.y - was.y ) );
				}
			}
			finally
			{
				UnityEngine.Object.DestroyImmediate( instance );
			}

			Write( lines );
		}

		/// <summary>
		/// Builds a Linux player into Library/PlayerBuild and reports its size, so
		/// the vector import can be compared with the old rasterised build.
		/// </summary>
		[MenuItem( "Sitekick/Chip SVG/Measure Build" )]
		public static void BuildFromMenu()
		{
			BuildPlayer();
		}

		public static void BuildPlayer()
		{
			var lines = new List<string>();
			var output = "Builds/ChipGallery.x86_64";
			Directory.CreateDirectory( Path.GetDirectoryName( output ) );

			var options = new BuildPlayerOptions
			{
				scenes = new[] { ChipGalleryBuilder.ScenePath },
				locationPathName = output,
				target = BuildTarget.StandaloneLinux64,
				options = BuildOptions.None
			};

			var report = BuildPipeline.BuildPlayer( options );
			if ( report == null )
			{
				lines.Add( "RESULT: FAIL (no build report)" );
				Write( lines );
				return;
			}

			var summary = report.summary;
			lines.Add( "build result: " + summary.result );
			lines.Add( "build size: " + ( summary.totalSize / 1048576.0 ).ToString( "0.0" ) + " MiB" );
			lines.Add( "errors: " + summary.totalErrors + ", warnings: " + summary.totalWarnings );
			lines.Add( "output: " + output );
			lines.Add( "RESULT: " + ( summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded ? "OK" : "FAIL" ) );
			Write( lines );
		}

		/// <summary>
		/// Renders the gallery's world-space content (Sitekick + a chip effect) to
		/// Logs/chip-gallery-render.png and reports what the grid icons hold.
		/// Needs a graphics device, so it cannot run with -nographics.
		/// </summary>
		[MenuItem( "Sitekick/Chip SVG/Render Sample" )]
		public static void RenderFromMenu()
		{
			Render();
		}

		public static void Render()
		{
			var lines = new List<string>();
			UnityEditor.SceneManagement.EditorSceneManager.OpenScene( ChipGalleryBuilder.ScenePath,
				UnityEditor.SceneManagement.OpenSceneMode.Single );

			var gallery = UnityEngine.Object.FindFirstObjectByType<ChipGallery>();
			if ( gallery == null )
			{
				lines.Add( "no gallery" );
				Write( lines );
				return;
			}

			gallery.Build();
			Canvas.ForceUpdateCanvases();

			var icons = UnityEngine.Object.FindObjectsByType< SVGImage >( FindObjectsSortMode.None );
			long verts = 0;
			int withSprite = 0;
			foreach ( var icon in icons )
			{
				if ( icon.sprite == null )
					continue;
				withSprite++;
				verts += icon.sprite.vertices.Length;
			}
			lines.Add( "grid icons: " + icons.Length + ", with sprite: " + withSprite + ", sprite vertices: " + verts );

			int built = 0, sampled = 0;
			foreach ( var icon in icons )
			{
				sampled++;
				var renderer = icon.GetComponent<CanvasRenderer>();
				var mesh = renderer != null ? renderer.GetMesh() : null;
				if ( mesh != null && mesh.vertexCount > 3 )
					built++;

				if ( sampled >= 200 )
					break;
			}
			lines.Add( "icons with a built mesh (first " + sampled + "): " + built );

			gallery.Toggle( 7 );
			Canvas.ForceUpdateCanvases();
			lines.Add( "active effects: " + gallery.ActiveCount );

			var camera = UnityEngine.Object.FindFirstObjectByType<Camera>();
			if ( camera == null )
			{
				lines.Add( "no camera" );
				Write( lines );
				return;
			}

			const int width = 1600, height = 900;
			var target = new RenderTexture( width, height, 24, RenderTextureFormat.ARGB32 );
			var previous = camera.targetTexture;
			RenderTexture.active = target;
			camera.targetTexture = target;
			camera.Render();

			var image = new Texture2D( width, height, TextureFormat.RGB24, false );
			image.ReadPixels( new Rect( 0, 0, width, height ), 0, 0 );
			image.Apply();
			File.WriteAllBytes( RenderPath, image.EncodeToPNG() );

			camera.targetTexture = previous;
			RenderTexture.active = null;
			UnityEngine.Object.DestroyImmediate( target );
			UnityEngine.Object.DestroyImmediate( image );

			lines.Add( "render: " + RenderPath );
			lines.Add( "RESULT: OK" );
			Write( lines );
		}

		static string importerType( string path )
		{
			var importer = AssetImporter.GetAtPath( path ) as SVGImporter;
			return importer != null ? importer.SvgType.ToString() : "?";
		}

		/// <summary>Vector sprites carry anti-aliasing arcs in the second UV set.</summary>
		static bool HasArcEncoding( Sprite sprite )
		{
			try
			{
				return sprite.HasVertexAttribute( UnityEngine.Rendering.VertexAttribute.TexCoord2 );
			}
			catch ( Exception )
			{
				return false;
			}
		}

		static void Write( List<string> lines )
		{
			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllLines( ReportPath, lines );
			Debug.Log( string.Join( "\n", lines.ToArray() ) );
		}
	}
}
#endif
