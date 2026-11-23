#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

namespace Sitekick
{
	/// <summary>
			/// Play-mode check for one chip: opens the gallery, clicks its cell and samples
		/// the running ChipMoviePlayer, then reports the frames it showed, where it
		/// wrapped, which sound cues fired, the frame it rested on, and whether a
		/// stop() held it.  Edit-mode probes call SetFrame, so they never exercise
		/// the clock, the loop range or the pause list.
	///
	/// Batch entry point: -executeMethod Sitekick.ChipPlayCheck.RunFromCommandLine
	/// </summary>
	public static class ChipPlayCheck
	{
		public const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		public static int Chip = 16;   // the chip under test
		public const float Seconds = 7f;

		const string PhaseKey = "Sitekick.ChipPlayCheck.phase";

		static readonly HashSet<int> distinct = new HashSet<int>();
		static readonly List<int> stops = new List<int>();
		static readonly List<int> cuePlays = new List<int>();
		static readonly StringBuilder trace = new StringBuilder();

		static ChipMoviePlayer player;
		static bool isStatic;              // no movie player: one drawing, most chips
		static SpriteRenderer[] art;
		static int samples;
		static int last = -1;
		static int wraps;
		static string tintHex;
		static GameObject spawned;

		static float start;
		static float window = Seconds;
		static bool restarted;
		static bool wasPaused;

		static string OutDir
		{
			get
			{
				return "Logs/chip_" + Chip.ToString( "0000" ) + "_play" +
					( tintHex != null ? "_" + tintHex.ToLowerInvariant() : "" );
			}
		}

		[InitializeOnLoadMethod]
		static void Hook()
		{
			EditorApplication.update -= Tick;
			if ( SessionState.GetInt( PhaseKey, 0 ) > 0 )
				EditorApplication.update += Tick;
		}

		/// <summary>Batch entry point; `--chip 36` picks the chip, as in ChipMovieBuilder.</summary>
		public static void RunFromCommandLine()
		{
			var args = System.Environment.GetCommandLineArgs();
			for ( var i = 0; i < args.Length - 1; i++ )
			{
				if ( args[ i ] == "--color" )
				{
					tintHex = args[ i + 1 ];
					continue;
				}

				if ( args[ i ] != "--chip" )
					continue;

				int chip;
				if ( int.TryParse( args[ i + 1 ], out chip ) )
					Chip = chip;
			}

			Application.runInBackground = true;
			SessionState.SetInt( PhaseKey, 1 );
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			EditorApplication.update -= Tick;
			EditorApplication.update += Tick;
		}

		/// <summary>
		/// Entering play mode reloads the domain, so the run is two phases carried in
		/// SessionState: wait for play mode (1), then sample it (2).
		/// </summary>
		static void Tick()
		{
			var phase = SessionState.GetInt( PhaseKey, 0 );

			if ( phase == 1 )
			{
				if ( EditorUtility.scriptCompilationFailed )
					Finish( "scripts have compile errors, play mode never started" );
				else if ( EditorApplication.isPlaying )
					Begin();
				else if ( !EditorApplication.isPlayingOrWillChangePlaymode )
					EditorApplication.isPlaying = true;
				return;
			}

			if ( phase != 2 )
				return;

			if ( isStatic )
			{
				// a static effect has no clock: give the sprites a moment to load, then look
				if ( Time.time - start > 0.5f )
					Finish( null );
				return;
			}

			if ( player == null )
				Finish( "lost the movie player during play" );
			else
				Sample();
		}

		static void Begin()
		{
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			var button = gallery != null ? FindCell( Chip ) : null;
			if ( button == null )
			{
				Finish( "the gallery has no cell for chip " + Chip );
				return;
			}

			// the colour goes on first so the chip is spawned into it, the way the
			// real gallery paints whatever is already wearing the Sitekick colour
			if ( tintHex != null )
			{
				var panel = Object.FindFirstObjectByType<ChipColorPanel>();
				if ( panel != null )
					panel.ApplyHex( tintHex );
				else
					gallery.ApplyColor( ChipColorPanel.Parse( tintHex ) );
			}

			button.onClick.Invoke();
			var instance = GameObject.Find( "Chip_" + Chip.ToString( "0000" ) + "_Effect" );
			spawned = instance;
			player = instance != null ? instance.GetComponentInChildren<ChipMoviePlayer>( true ) : null;
			isStatic = player == null;
			if ( isStatic )
			{
				// most chips have no timeline: the prefab is a single drawing to look at
				art = instance != null ? instance.GetComponentsInChildren<SpriteRenderer>( true ) : new SpriteRenderer[ 0 ];
				if ( art.Length == 0 )
				{
					Finish( "the click spawned neither a movie player nor a sprite" );
					return;
				}

				start = Time.time;
				SessionState.SetInt( PhaseKey, 2 );
				return;
			}

			distinct.Clear();
			stops.Clear();
			cuePlays.Clear();
			player.CueFired += frame => cuePlays.Add( frame );
			trace.Length = 0;
			samples = 0;
			last = -1;
			wraps = 0;
			restarted = false;
			wasPaused = false;
			start = Time.time;
			// two passes of the loop plus the restart, so a movie whose cycle is
			// longer than the fixed window (chip 36 runs 51 frames) still wraps twice
			var cycle = player.fps > 0f ? player.frames.Length / player.fps : 0f;
			window = Mathf.Max( Seconds, cycle * 2f + 2.5f );
			SessionState.SetInt( PhaseKey, 2 );
		}

		static void Sample()
		{
			var now = Time.time - start;
			var frame = player.Frame + 1;

			if ( frame != last )
			{
				var wrapped = last >= 0 && frame == player.loopFrom && last >= player.loopTo;
				if ( wrapped )
					wraps++;

				if ( samples > 0 )
					trace.Append( wrapped ? " | " : " " );
				trace.Append( frame );

				last = frame;
				distinct.Add( frame );
				samples++;
			}

			if ( player.IsPaused != wasPaused )
			{
				wasPaused = player.IsPaused;
				if ( wasPaused )
					stops.Add( frame );
			}

			// Play mode's first frames are a load hitch longer than the intro lasts, so
			// the editor loop can miss it.  Restart once warm -- the player's own
			// Restart, the same path the click reaches -- to sample frames below the loop.
			if ( !restarted && now > 1.2f )
			{
				restarted = true;
				last = -1;
				player.Restart();
				trace.Append( " restart" );
			}

			if ( now > window )
				Finish( null );
		}

		/// <summary>Reports what was seen and exits 1 on a failed check; `why` marks an aborted run.</summary>
		static void Finish( string why )
		{
			SessionState.SetInt( PhaseKey, 0 );
			EditorApplication.update -= Tick;

			var frames = new List<int>( distinct );
			frames.Sort();

			var lines = new List<string>();
			lines.Add( "chip " + Chip + " play-mode check" );

			if ( player != null )
			{
				lines.Add( "frames " + player.frames.Length + "  fps " + player.fps
					+ "  loop " + player.loopFrom + ".." + player.loopTo
					+ "  pauses [" + string.Join( ",", player.pauses.ConvertAll( p => p.ToString() ).ToArray() ) + "]"
					+ "  pauseSeconds " + player.pauseSeconds + "  sounds " + player.sounds.Count );
			}

			if ( isStatic )
			{
				var sprites = new List<string>();
				var bounds = new Bounds();
				var first = true;
				foreach ( var r in art )
				{
					if ( r == null )
						continue;
					if ( r.sprite != null )
						sprites.Add( r.sprite.name );
					if ( first )
						{ bounds = r.bounds; first = false; }
					else
						bounds.Encapsulate( r.bounds );
				}

				lines.Add( "static effect  no ChipMoviePlayer  renderers " + art.Length
					+ "  sprites " + sprites.Count
					+ "  bounds " + bounds.size.ToString( "0.00" ) + " @ " + bounds.center.ToString( "0.00" ) );
				lines.Add( "drawn " + string.Join( ",", sprites.ToArray() ) );
				// where each renderer actually sits, so a missing or covered piece of
				// art is visible in the report instead of only in the capture
				foreach ( var r in art )
				{
					if ( r == null ) continue;
					var w = r.transform.TransformVector( r.sprite != null ? (Vector3) r.sprite.bounds.size : Vector3.zero );
					lines.Add( $"  renderer {r.name}  sprite {( r.sprite != null ? r.sprite.name : "-" )}  order {r.sortingOrder}"
						+ $"  z {r.transform.position.z:0.00}  centre {r.bounds.center.ToString( "0.000" )}"
						+ $"  size {Mathf.Abs( w.x ):0.000}x{Mathf.Abs( w.y ):0.000}"
						+ ( r.enabled ? "" : "  DISABLED" ) );
				}
			}

			// 0,0 is not a loop: the movie plays once and rests on its last frame
			var once = player != null && player.loopFrom < 1;
			var ended = player != null ? player.Frame + 1 : 0;
			var seen = player != null && player.target != null && player.target.sprite != null
				? player.target.sprite.name : "-";
			var fired = new List<int>( new HashSet<int>( cuePlays ) );
			fired.Sort();
			var wanted = new List<int>();
			if ( player != null )
				foreach ( var cue in player.sounds )
					if ( cue != null )
						wanted.Add( cue.frame );
			wanted = new List<int>( new HashSet<int>( wanted ) );
			wanted.Sort();

			if ( !isStatic )
			{
				lines.Add( "trace " + trace );
				lines.Add( "samples " + samples + "  distinct " + frames.Count + "  wraps " + wraps
					+ "  stopped at " + ( stops.Count > 0 ? string.Join( ",", stops.ConvertAll( p => p.ToString() ).ToArray() ) : "-" )
					+ ( player != null && player.IsPaused ? " (still held)" : "" ) );
				lines.Add( "rest " + ( player.IsDone ? "done" : "running" )
					+ " on frame " + ended + " (" + seen + ")" );
				lines.Add( "cues " + Join( fired ) + "  fired " + cuePlays.Count + "x  prefab " + Join( wanted ) );
			}

			var ok = why == null;
			if ( why != null )
				lines.Add( "FAIL " + why );
			else if ( isStatic )
			{
				var drawn = false;
				foreach ( var r in art )
					if ( r != null && r.sprite != null )
						drawn = true;

				if ( !drawn )
					{ lines.Add( "FAIL the static effect draws nothing" ); ok = false; }
			}
			else if ( frames.Count == 0 )
				{ lines.Add( "FAIL no frames played" ); ok = false; }
			else if ( frames[ 0 ] < 1 || frames[ frames.Count - 1 ] > player.frames.Length )
				{ lines.Add( "FAIL frames outside 1.." + player.frames.Length ); ok = false; }
			else if ( !once && frames[ frames.Count - 1 ] > player.loopTo )
				{ lines.Add( "FAIL played past the loop into the retract: " + frames[ frames.Count - 1 ] ); ok = false; }
			else if ( once && ( frames.Count != player.frames.Length || !player.IsDone || ended != player.frames.Length ) )
				{ lines.Add( "FAIL a one-pass movie must show all " + player.frames.Length + " frames once and rest on the last" ); ok = false; }
			else if ( !once && player.loopFrom != player.loopTo && wraps < 2 )
				{ lines.Add( "FAIL did not loop " + player.loopFrom + ".." + player.loopTo + " twice" ); ok = false; }
			else if ( !once && player.loopFrom == player.loopTo
				&& ( frames.Count != 1 || frames[ 0 ] != player.loopFrom ) )
				{ lines.Add( "FAIL a one-frame loop must show only frame " + player.loopFrom ); ok = false; }
			else if ( wanted.Count > 0 && !Same( fired, wanted ) )
				{ lines.Add( "FAIL cues fired on frames other than the prefab's " + Join( wanted ) ); ok = false; }
			else if ( player.IsPaused )
				{ lines.Add( "FAIL held at a stop() when the run ended" ); ok = false; }

			if ( tintHex != null )
			{
				lines.Add( "colour: " + tintHex.ToUpperInvariant() );
				foreach ( var renderer in spawned != null
					? spawned.GetComponentsInChildren<SpriteRenderer>( true )
					: new SpriteRenderer[ 0 ] )
				{
					var block = new MaterialPropertyBlock();
					renderer.GetPropertyBlock( block );
					var tint = block.GetColor( "_Color" );
					// an unset block reads back as (0,0,0,0), not white
					lines.Add( "  " + renderer.name + ": " + ( tint.a > 0f
						? ColorUtility.ToHtmlStringRGB( tint ) + " (set)"
						: "untouched" ) );
				}

				var gallery = Object.FindFirstObjectByType<ChipGallery>();
				foreach ( var renderer in gallery != null && gallery.Sitekick != null
					? gallery.Sitekick.GetComponentsInChildren<SpriteRenderer>( true )
					: new SpriteRenderer[ 0 ] )
				{
					var block = new MaterialPropertyBlock();
					renderer.GetPropertyBlock( block );
					var tint = block.GetColor( "_Color" );
					if ( tint.a > 0f && tint != Color.white )
						lines.Add( "  sitekick " + renderer.name + ": " +
							ColorUtility.ToHtmlStringRGB( tint ) + " (set)" );
				}
			}

			lines.Add( "" );
			lines.Add( ok ? "RESULT: OK" : "RESULT: FAIL" );

			Directory.CreateDirectory( OutDir );
			Capture( "resting.png", null );
			if ( player != null && player.target != null )
				Capture( "resting-close.png", player.target.bounds );
			else if ( art != null && art.Length > 0 && art[ 0 ] != null )
			{
				Capture( "resting-close.png", art[ 0 ].bounds );
				// a static chip can have several renderers (chip 99's four wings):
				// frame the whole effect, or a piece at the edge is invisible in the check
				var whole = art[ 0 ].bounds;
				foreach ( var r in art )
					if ( r != null ) whole.Encapsulate( r.bounds );
				Capture( "resting-art.png", whole );
			}
			File.WriteAllText( OutDir + "/report.txt", string.Join( "\n", lines.ToArray() ) + "\n" );
			Debug.Log( string.Join( "\n", lines.ToArray() ) );

			EditorApplication.isPlaying = false;
			EditorApplication.delayCall += () => EditorApplication.Exit( ok ? 0 : 1 );
		}

		static string Join( List<int> frames )
		{
			return frames.Count > 0 ? string.Join( ",", frames.ConvertAll( f => f.ToString() ).ToArray() ) : "-";
		}

		static bool Same( List<int> a, List<int> b )
		{
			if ( a.Count != b.Count )
				return false;
			for ( var i = 0; i < a.Count; i++ )
				if ( a[ i ] != b[ i ] )
					return false;
			return true;
		}

		/// <summary>Saves the play view, or just `bounds` when given, as one PNG.</summary>
		static void Capture( string name, Bounds? bounds )
		{
			var camera = Camera.main;
			if ( camera == null )
				return;

			var viewSize = camera.orthographicSize;
			var viewAt = camera.transform.position;
			if ( bounds.HasValue )
			{
				var b = bounds.Value;
				var aspect = camera.aspect;
				camera.orthographicSize = Mathf.Max( b.extents.y, b.extents.x / Mathf.Max( aspect, 0.01f ) ) * 1.1f;
				camera.transform.position = new Vector3( b.center.x, b.center.y, viewAt.z );
			}

			const int w = 1440, h = 1080;
			var rt = new RenderTexture( w, h, 24, RenderTextureFormat.ARGB32 );
			// the gallery camera does not clear, so a fresh target can still hold
			// whatever the GPU last had in that memory
			var activeBefore = RenderTexture.active;
			RenderTexture.active = rt;
			GL.Clear( true, true, Color.clear );
			RenderTexture.active = activeBefore;
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
			File.WriteAllBytes( OutDir + "/" + name, tex.EncodeToPNG() );
			Object.DestroyImmediate( tex );
			rt.Release();
			Object.DestroyImmediate( rt );

			camera.orthographicSize = viewSize;
			camera.transform.position = viewAt;
		}

		static Button FindCell( int chip )
		{
			var name = "chip_" + chip.ToString( "0000" );
			foreach ( var b in Object.FindObjectsByType<Button>( FindObjectsSortMode.None ) )
				if ( b != null && b.gameObject.name == name )
					return b;
			return null;
		}
	}
}
#endif
