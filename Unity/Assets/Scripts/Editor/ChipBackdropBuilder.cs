#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Sitekick
{
	/// <summary>
	/// Rebuilds the nine background chips (ids 1-6, 161, 177, 286) so their art
	/// actually covers the frame.
	///
	/// In Flash a background chip's class only instantiates a separate backdrop
	/// clip and adds it to the effect container at (0,0), so the backdrop's own
	/// drawing coordinates are the container's frame -- the 550x400 effect stage.
	/// The old build treated that art like a chip effect part and dropped it in
	/// the Sitekick's local frame, which put it below and right of the camera.
	/// Here the backdrop is placed in stage space, scaled to cover the camera,
	/// and kept behind everything (the Background layer already sits under the
	/// Sitekick, so the Sitekick stays in front of it).
	///
	/// Chips 1-6 are the weekday mini-game chips: their library symbol is an
	/// empty stub, and the effect is the standalone 375x300 movie exported to
	/// Assets/Chips/Backdrops/Boot (51 frames at 12 fps), played by
	/// ChipBackdropPlayer. Chips 177/286 have their backdrop and overlay; 161's
	/// class assigns Back_161 through a local, which the actionscript scan missed,
	/// so its art was exported directly (Tools/SwfToSvg/export_backdrops.sh).
	/// </summary>
	public static class ChipBackdropBuilder
	{
		public const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		public const string ReportPath = "Logs/chip-backdrops.txt";
		public const string BootDir = "Assets/Chips/Backdrops/Boot";

		/// <summary>Effect stage in SWF pixels; the effect container's origin is its top-left.</summary>
		const float StageW = 550f;
		const float StageH = 400f;

		sealed class Spec
		{
			public int id;
			public string back;          // single backdrop svg, or null
			public string front;         // overlay svg, or null
			public bool boot;            // 51-frame movie instead of a still backdrop
			public Vector2 stageCenter = new Vector2( StageW * 0.5f, StageH * 0.5f );
			public Vector2? centerOverride;
		}

		public static void Run()
		{
			var lines = new StringBuilder();
			var report = new List<string>();

			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			var camera = Camera.main;
			if ( camera == null )
			{
				Debug.LogError( "no main camera in the gallery scene" );
				return;
			}

			float camH = camera.orthographicSize * 2f;
			float camW = camH * camera.aspect;
			float layerScale = LayerScale();
			lines.AppendLine( "camera " + camW.ToString( "0.000" ) + " x " + camH.ToString( "0.000" )
				+ "  background layer scale " + layerScale );
			if ( layerScale <= 0f )
			{
				Debug.LogError( "no Background EffectLayer in the scene" );
				return;
			}

			var specs = new[]
			{
				Boot( 1 ), Boot( 2 ), Boot( 3 ), Boot( 4 ), Boot( 5 ), Boot( 6 ),
				Still( 161, Back( 161 ), Front( 161 ), null ),
				Still( 177, Back( 177 ), Front( 177 ), new Vector2( StageW * 0.5f, StageH * 0.5f ) ),
				Still( 286, Back( 286 ), Front( 286 ), new Vector2( StageW * 0.5f, StageH * 0.5f ) ),
			};

			foreach ( var spec in specs )
			{
				var spritePaths = new List<string>();
				if ( spec.boot )
					spritePaths.AddRange( BootFrames() );
				if ( spec.back != null )
					spritePaths.Add( spec.back );

				var backSprite = LoadSprite( spec.boot ? spritePaths[ 0 ] : spec.back );
				if ( backSprite == null )
				{
					report.Add( spec.id + ": MISSING backdrop art" );
					continue;
				}

				var backCanvas = Canvas( spec.boot ? spritePaths[ 0 ] : spec.back );
				// cover the camera with the backdrop's own bounding box
				float fit = Mathf.Max( camW / backCanvas.z, camH / backCanvas.w );
				float scale = fit * backCanvas.z / backSprite.bounds.size.x / layerScale;
				var backCenter = new Vector2( backCanvas.x + backCanvas.z * 0.5f, backCanvas.y + backCanvas.w * 0.5f );

				report.Add( spec.id + ": back " + Path.GetFileName( spec.boot ? spritePaths[ 0 ] : spec.back )
					+ "  art " + backCanvas.z.ToString( "0.0" ) + "x" + backCanvas.w.ToString( "0.0" ) + " px"
					+ "  fit " + fit.ToString( "0.0000" ) + " world/px"
					+ "  world size " + ( backCanvas.z * fit ).ToString( "0.00" ) + " x " + ( backCanvas.w * fit ).ToString( "0.00" )
					+ "  scale " + scale.ToString( "0.0000" ) + ( spec.boot ? "  frames " + spritePaths.Count : "" ) );

				var prefab = Build( spec, spritePaths, backSprite, scale, fit, backCenter, layerScale, report );
				if ( prefab != null )
					report.Add( "    -> " + prefab );
			}

			AssetDatabase.SaveAssets();
			AssetDatabase.Refresh();
			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllText( ReportPath, string.Join( "\n", report.ToArray() ) + "\n" );
			Debug.Log( lines + "\n" + string.Join( "\n", report.ToArray() ) );
		}

		static Spec Boot( int id )
		{
			return new Spec { id = id, boot = true, stageCenter = new Vector2( 187.5f, 150f ) };
		}

		static Vector2 ReferenceView()
		{
			var camera = Camera.main;
			if ( camera == null )
				return new Vector2( 14.667f, 11f );
			var height = camera.orthographicSize * 2f;
			return new Vector2( height * camera.aspect, height );
		}

		static Spec Still( int id, string back, string front, Vector2? stageCenter )
		{
			var spec = new Spec { id = id, back = back, front = front };
			if ( stageCenter.HasValue )
				spec.stageCenter = stageCenter.Value;
			else if ( back != null )
			{
				// art without a shared stage frame: centre the backdrop
				var c = Canvas( back );
				spec.stageCenter = new Vector2( c.x + c.z * 0.5f, c.y + c.w * 0.5f );
			}
			return spec;
		}

		static string Back( int id )
		{
			return PreferPng( ChipPath( id, "chip_" + id.ToString( "0000" ) + "_back" ) );
		}

		static string Front( int id )
		{
			return PreferPng( ChipPath( id, "chip_" + id.ToString( "0000" ) + "_front" ) );
		}

		/// <summary>
		/// A rasterised copy wins over the vector original: the SVG importer cannot
		/// draw &lt;pattern&gt; fills (chip 286's overlay is one), so that piece ships as
		/// a PNG rendered by rsvg-convert. Its canvas is read from the SVG twin.
		/// </summary>
		static string PreferPng( string stem )
		{
			if ( string.IsNullOrEmpty( stem ) )
				return null;
			if ( File.Exists( stem + ".png" ) )
				return stem + ".png";
			return File.Exists( stem + ".svg" ) ? stem + ".svg" : null;
		}

		static string ChipDir( int id )
		{
			var dirs = Directory.GetDirectories( "Assets/Chips", "Chip_" + id.ToString( "0000" ), SearchOption.AllDirectories );
			return dirs.Length == 0 ? null : dirs[ 0 ].Replace( '\\', '/' );
		}

		static string ChipPath( int id, string file )
		{
			var dir = ChipDir( id );
			return dir == null ? null : dir + "/Sprites/" + file;
		}

		static string[] BootFrames()
		{
			return Directory.GetFiles( BootDir, "chip_boot_f*.svg" )
				.OrderBy( p => p, StringComparer.Ordinal )
				.Select( p => p.Replace( '\\', '/' ) )
				.ToArray();
		}

		static Sprite LoadSprite( string path )
		{
			if ( string.IsNullOrEmpty( path ) )
				return null;
			var sprite = AssetDatabase.LoadAssetAtPath<Sprite>( path );
			if ( sprite == null )
				Debug.LogWarning( "no sprite at " + path );
			return sprite;
		}

		/// <summary>Canvas of an exported SVG as (minX, minY, width, height) in SWF pixels.</summary>
		static Vector4 Canvas( string path )
		{
			// a rasterised piece keeps its vector twin for the canvas numbers
			if ( path.EndsWith( ".png", StringComparison.Ordinal ) )
			{
				var twin = Path.ChangeExtension( path, ".svg" );
				if ( File.Exists( twin ) )
					return Canvas( twin );
				var sprite = AssetDatabase.LoadAssetAtPath<Sprite>( path );
				return sprite != null
					? new Vector4( 0f, 0f, sprite.rect.width, sprite.rect.height )
					: new Vector4( 0f, 0f, 1f, 1f );
			}

			var head = File.ReadAllText( path ).Substring( 0, Math.Min( 1200, (int)new FileInfo( path ).Length ) );
			var vb = Regex.Match( head, "viewBox=\"([-0-9.eE ]+)\"" );
			if ( vb.Success )
			{
				var n = vb.Groups[ 1 ].Value.Split( new[] { ' ', ',' }, StringSplitOptions.RemoveEmptyEntries )
					.Select( v => float.Parse( v, CultureInfo.InvariantCulture ) ).ToArray();
				if ( n.Length == 4 )
					return new Vector4( n[ 0 ], n[ 1 ], n[ 2 ], n[ 3 ] );
			}

			float Num( string attr )
			{
				var m = Regex.Match( head, attr + "=\"([-0-9.eE]+)px\"" );
				return m.Success ? float.Parse( m.Groups[ 1 ].Value, CultureInfo.InvariantCulture ) : 0f;
			}

			return new Vector4( 0f, 0f, Num( "width" ), Num( "height" ) );
		}

		static float LayerScale()
		{
			foreach ( var layer in UnityEngine.Object.FindObjectsByType<EffectLayer>( FindObjectsSortMode.None ) )
				if ( layer.layer == ChipData.EffectLayer.Background )
					return layer.transform.lossyScale.x;
			return 0f;
		}

		static string Build( Spec spec, List<string> spritePaths, Sprite backSprite,
			float scale, float fit, Vector2 backCenter, float layerScale, List<string> report )
		{
			var dir = ChipDir( spec.id );
			if ( string.IsNullOrEmpty( dir ) )
				dir = Path.GetDirectoryName( spec.back ?? spritePaths[ 0 ] ).Replace( "/Sprites", "" );
			var path = dir + "/Chip_" + spec.id.ToString( "0000" ) + "_Effect.prefab";

			var root = new GameObject( "Chip_" + spec.id.ToString( "0000" ) + "_Effect" );
			try
			{
				var group = root.AddComponent<SortingGroup>();
				group.sortingOrder = 0;
				root.AddComponent<ChipEffect>();
				root.AddComponent<ChipBackdropFit>().referenceView = ReferenceView();

				var sprite = backSprite;
				var canvas = Canvas( spec.boot ? spritePaths[ 0 ] : spec.back );
				var back = Node( root, "back", sprite, -1000 );
				back.transform.localScale = Vector3.one * scale;
				back.transform.localPosition = Place( canvas, backCenter, fit, layerScale, sprite, scale );

				if ( spec.boot )
				{
					var player = root.AddComponent<ChipBackdropPlayer>();
					player.target = back.GetComponent<SpriteRenderer>();
					player.fps = 12f;
					player.frames = spritePaths
						.Select( p => AssetDatabase.LoadAssetAtPath<Sprite>( p ) )
						.Where( s => s != null ).ToArray();
					report.Add( "    frames loaded: " + player.frames.Length );
				}

				if ( spec.front != null )
				{
					var frontSprite = LoadSprite( spec.front );
					if ( frontSprite != null )
					{
						var frontCanvas = Canvas( spec.front );
						var frontCenter = new Vector2( frontCanvas.x + frontCanvas.z * 0.5f, frontCanvas.y + frontCanvas.w * 0.5f );
						// a piece's own px-per-unit ratio differs between an SVG sprite and
						// its rasterised twin, so scale each piece from its own bounds
						var frontScale = fit * frontCanvas.z / frontSprite.bounds.size.x / layerScale;
						var front = Node( root, "front", frontSprite, 1000 );
						front.transform.localScale = Vector3.one * frontScale;
						front.transform.localPosition = Place( frontCanvas, backCenter, fit, layerScale, frontSprite, frontScale, frontCenter );
					}
				}

				AssetDatabase.DeleteAsset( path );
				var saved = PrefabUtility.SaveAsPrefabAsset( root, path );
				return saved != null ? path : null;
			}
			finally
			{
				UnityEngine.Object.DestroyImmediate( root );
			}
		}

		static GameObject Node( GameObject parent, string name, Sprite sprite, int order )
		{
			var go = new GameObject( name );
			go.transform.SetParent( parent.transform, false );
			var renderer = go.AddComponent<SpriteRenderer>();
			renderer.sprite = sprite;
			renderer.sortingOrder = order;
			return go;
		}

		/// <summary>
		/// Where a piece goes in the effect container's frame: its stage coordinate
		/// relative to the backdrop centre, converted to the layer's local units.
		/// Swapping the y axis turns Flash's downwards y into Unity's upwards y.
		/// </summary>
		static Vector3 Place( Vector4 canvas, Vector2 backCenter, float fit, float layerScale,
			Sprite sprite, float scale, Vector2? center = null )
		{
			var c = center ?? new Vector2( canvas.x + canvas.z * 0.5f, canvas.y + canvas.w * 0.5f );
			var offset = new Vector2(
				( c.x - backCenter.x ) * fit / layerScale,
				( backCenter.y - c.y ) * fit / layerScale );
			// the sprite's pivot need not sit on its geometry centre
			return new Vector3( offset.x, offset.y, 0f ) - scale * sprite.bounds.center;
		}
	}
}
#endif
