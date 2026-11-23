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

namespace Sitekick
{
	/// <summary>
	/// Rebuilds chips 7-16 from the standalone chip SFWs: one sprite per Flash
	/// frame, the clips the movie starts, and the frames where it calls stop().
	///
	/// The prefab asset is rewritten in place, so its .meta guid survives and the
	/// gallery scene keeps pointing at it without a rebuild.
	///
	/// Registration: the same units the rest of the chip pipeline uses. build_prefabs
	/// draws a chip symbol at 6.94 exported pixels per SWF unit over a 400 px
	/// sprite unit, i.e. 0.01735 prefab units per SWF pixel, and the gallery hangs
	/// every chip on the Sitekick's own transform — so a movie drawn at that scale
	/// sits on the Sitekick at the size the original artwork was made for. The
	/// stage's centre goes on the face centre; a movie's backdrop is stripped, so
	/// only the drawing is left and nothing has to line up edge to edge.
	/// </summary>
	public static class ChipMovieBuilder
	{
		public const string ReportPath = "Logs/chip-movies.txt";

		/// <summary>
		/// Shared material for the movie frame sprites. The built-in sprite material
		/// samples the wrong place in a vector sprite's gradient atlas, which is what
		/// turned gradient-heavy chips into dark washes; Unlit/VectorGradient is the
		/// shader the icon baker uses and draws them correctly.
		/// </summary>
		public const string MaterialPath = "Assets/Materials/ChipMovie-Vector.mat";
		public static readonly int[] Chips = { 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 };

		[Serializable]
		sealed class SoundCueJson
		{
			public int frame;
			public string clip;
		}

		[Serializable]
		sealed class MovieJson
		{
			public int chip;
			public float fps;
			public string[] frames;
			public float[] stage_px;
			public float[] canvas_units;
			public float units_per_px;
			public SoundCueJson[] sounds;
			public int[] pauses;
			public int[] loop;
		}

		/// <summary>
		/// Prefab units per SWF pixel, from build_prefabs: 6.94 px per SWF unit over
		/// a 400 px sprite unit, which is the scale every chip in the gallery uses.
		/// </summary>
		public const float UnitsPerPx = 0.01735f;

		/// <summary>Screen centre in prefab-local units: the body disc's centre.</summary>
		public static readonly Vector2 Anchor = new Vector2( 0.0017f, -0.0390f );

		[MenuItem( "Sitekick/Rebuild Chip Movies" )]
		public static void RunFromMenu()
		{
			Run();
		}

		/// <summary>
		/// Batch entry point: rebuilds every chip, or only the ones named by
		/// `--chip 8` / `--chip 8,9` after -executeMethod.
		/// </summary>
		public static void RunFromCommandLine()
		{
			var wanted = new List<int>();
			var args = Environment.GetCommandLineArgs();
			for ( var i = 0; i < args.Length - 1; i++ )
			{
				if ( args[ i ] != "--chip" )
					continue;
				foreach ( var part in args[ i + 1 ].Split( ',' ) )
				{
					int chip;
					if ( int.TryParse( part.Trim(), out chip ) )
						wanted.Add( chip );
				}
			}
			Run( wanted.Count > 0 ? ( IEnumerable<int> )wanted : Chips );
		}

		public static void Run()
		{
			Run( Chips );
		}

		static void Run( IEnumerable<int> chips )
		{
			var report = new StringBuilder();
			foreach ( var chip in chips )
			{
				var dir = ChipDir( chip );
				if ( dir == null )
				{
					report.AppendLine( chip + ": no chip folder" );
					continue;
				}

				var manifestPath = dir + "/Movie/movie.json";
				if ( !File.Exists( manifestPath ) )
				{
					report.AppendLine( chip + ": no movie.json (run Tools/SwfToSvg/export_chip_movies.py)" );
					continue;
				}

				var manifest = JsonUtility.FromJson<MovieJson>( File.ReadAllText( manifestPath ) );
				var frameNames = manifest.frames;
				var sprites = frameNames
					.Select( f => AssetDatabase.LoadAssetAtPath<Sprite>( dir + "/Movie/" + f ) )
					.ToArray();
				var missing = sprites.Count( s => s == null );
				if ( missing > 0 )
				{
					report.AppendLine( chip + ": " + missing + "/" + sprites.Length + " frame sprites missing" );
					continue;
				}

				var first = sprites[ 0 ];
				float stageW = manifest.stage_px != null && manifest.stage_px.Length > 0 ? manifest.stage_px[ 0 ] : 375f;
				// The sprite is the drawing, not the stage: chips whose frames reach outside
				// the canvas would otherwise be sized (and jittered) by that overflow.
				float canvasW = manifest.canvas_units != null && manifest.canvas_units.Length > 0
					? manifest.canvas_units[ 0 ] : first.bounds.size.x;

				// stage px -> prefab units, expressed as a scale on the frame sprites
				float spriteUnitsPerPx = canvasW / stageW;
				float scale = UnitsPerPx / spriteUnitsPerPx;

				var vectorMaterial = EnsureMaterial();

			var cues = new List<ChipMoviePlayer.Cue>();
				foreach ( var cue in manifest.sounds ?? Array.Empty<SoundCueJson>() )
				{
					var clip = AssetDatabase.LoadAssetAtPath<AudioClip>( dir + "/" + cue.clip );
					if ( clip == null )
					{
						report.AppendLine( "    missing clip " + cue.clip );
						continue;
					}
					cues.Add( new ChipMoviePlayer.Cue { frame = cue.frame, clip = clip } );
				}

				var pauses = ( manifest.pauses ?? Array.Empty<int>() ).ToList();
				var loop = manifest.loop ?? Array.Empty<int>();
				var path = Build( chip, dir, sprites, scale, cues, pauses, loop, manifest.fps, vectorMaterial );
				report.AppendLine( chip + ": " + sprites.Length + " frames, " + cues.Count + " sounds, pauses ["
					+ string.Join( ",", pauses ) + "], loop ["
					+ ( loop.Length > 1 ? loop[ 0 ] + ".." + loop[ 1 ] : "once" )
					+ "], scale " + scale.ToString( "0.0000" ) + " -> " + path );
			}

			AssetDatabase.SaveAssets();
			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllText( ReportPath, report.ToString() );
			Debug.Log( report.ToString() );
		}

		static Material EnsureMaterial()
		{
			var existing = AssetDatabase.LoadAssetAtPath<Material>( MaterialPath );
			if ( existing != null )
				return existing;

			var shader = Shader.Find( "Unlit/VectorGradient" );
			if ( shader == null )
			{
				Debug.LogError( "Unlit/VectorGradient is missing" );
				return null;
			}

			Directory.CreateDirectory( "Assets/Materials" );
			var material = new Material( shader ) { name = "ChipMovie-Vector" };
			AssetDatabase.CreateAsset( material, MaterialPath );
			return AssetDatabase.LoadAssetAtPath<Material>( MaterialPath );
		}

		static string Build( int chip, string dir, Sprite[] sprites, float scale,
			List<ChipMoviePlayer.Cue> cues, List<int> pauses, int[] loop, float fps, Material material )
		{
			var name = "Chip_" + chip.ToString( "0000" ) + "_Effect";
			var path = dir + "/" + name + ".prefab";
			var root = new GameObject( name );
			try
			{
				var group = root.AddComponent<SortingGroup>();
				group.sortingOrder = 0;
				root.AddComponent<ChipEffect>();

				var go = new GameObject( "movie" );
				go.transform.SetParent( root.transform, false );
				go.transform.localScale = Vector3.one * scale;
				go.transform.localPosition = new Vector3( Anchor.x, Anchor.y, 0f );

				var renderer = go.AddComponent<SpriteRenderer>();
				renderer.sprite = sprites[ 0 ];
				renderer.sortingOrder = 0;
				if ( material != null )
					renderer.sharedMaterial = material;

				var audio = root.AddComponent<AudioSource>();
				audio.playOnAwake = false;
				audio.spatialBlend = 0f;

				var player = root.AddComponent<ChipMoviePlayer>();
				player.target = renderer;
				player.frames = sprites;
				player.fps = fps > 0f ? fps : 12f;
				player.sounds = cues;
				player.pauses = pauses;
				player.loopFrom = loop.Length > 1 ? loop[ 0 ] : 0;
				player.loopTo = loop.Length > 1 ? loop[ 1 ] : 0;
				player.pauseSeconds = 0.75f; // holds long enough to read, then carries on
				player.audioSource = audio;

				// Overwrite in place: deleting the asset would take its .meta with it and
				// the gallery scene's references are by guid.
				var saved = PrefabUtility.SaveAsPrefabAsset( root, path );
				return saved != null ? path : null;
			}
			finally
			{
				UnityEngine.Object.DestroyImmediate( root );
			}
		}

		static string ChipDir( int chip )
		{
			var dirs = Directory.GetDirectories( "Assets/Chips", "Chip_" + chip.ToString( "0000" ), SearchOption.AllDirectories );
			return dirs.Length == 0 ? null : dirs[ 0 ].Replace( '\\', '/' );
		}
	}
}
#endif
