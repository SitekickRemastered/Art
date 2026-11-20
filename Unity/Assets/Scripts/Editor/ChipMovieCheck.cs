#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Toggles each rebuilt chip and captures it at the start, middle and end of
	/// its movie, so the frames can be compared with the SWF exports.
	/// </summary>
	public static class ChipMovieCheck
	{
		public const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		public const string ReportPath = "Logs/chip-movie-check.txt";

		static readonly float[] At = { 0f, 0.5f, 1f };

		public static void Run()
		{
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			var gallery = UnityEngine.Object.FindFirstObjectByType<ChipGallery>();
			var camera = Camera.main;
			if ( gallery == null || camera == null )
			{
				Debug.LogError( "gallery scene is missing the gallery or camera" );
				return;
			}

			var lines = new StringBuilder();
			foreach ( var chip in ChipMovieBuilder.Chips )
			{
				gallery.Toggle( chip );
				var instance = Find( chip );
				lines.AppendLine( "=== chip " + chip + " ===" );
				if ( instance == null )
				{
					lines.AppendLine( "  no instance" );
					continue;
				}

				var player = instance.GetComponentInChildren<ChipMoviePlayer>( true );
				var renderer = instance.GetComponentInChildren<SpriteRenderer>( true );
				if ( player == null || renderer == null )
				{
					lines.AppendLine( "  missing player or renderer" );
					continue;
				}

				var b = renderer.bounds;
				lines.AppendLine( "  frames " + player.frames.Length + "  fps " + player.fps
					+ "  sounds " + player.sounds.Count + "  pauses " + string.Join( ",", player.pauses.ConvertAll( p => p.ToString() ).ToArray() ) );
				lines.AppendLine( "  world " + b.size.ToString( "0.00" ) + " @ " + b.center.ToString( "0.00" ) );

				foreach ( var t in At )
				{
					int frame = Mathf.Clamp( Mathf.RoundToInt( t * ( player.frames.Length - 1 ) ), 0, player.frames.Length - 1 );
					player.SetFrame( frame );
					Capture( camera, "Logs/movie-" + chip.ToString( "0000" ) + "-" + ( frame + 1 ).ToString( "000" ) + ".png" );
					var fb = renderer.bounds;
					lines.AppendLine( "  frame " + ( frame + 1 ) + "  " + fb.size.ToString( "0.00" ) + " @ " + fb.center.ToString( "0.00" )
						+ " -> Logs/movie-" + chip.ToString( "0000" ) + "-" + ( frame + 1 ).ToString( "000" ) + ".png" );
				}

				gallery.Toggle( chip );
			}

			Directory.CreateDirectory( Path.GetDirectoryName( ReportPath ) );
			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );
		}

		/// <summary>
		/// Capture every frame of one chip, for the frame-by-frame comparison against a
		/// real Flash player (Ruffle). Writes Logs/pilot/unity/XXXX/frame_NNN.png.
		/// </summary>
		public static void DumpPilot()
		{
			foreach ( var c in ChipMovieBuilder.Chips )
				DumpOne( c );
		}

		public static void DumpOne( int chip )
		{
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			var gallery = UnityEngine.Object.FindFirstObjectByType<ChipGallery>();
			var camera = Camera.main;
			if ( gallery == null || camera == null )
			{
				Debug.LogError( "gallery scene is missing the gallery or camera" );
				return;
			}

			gallery.Toggle( chip );
			var instance = Find( chip );
			var player = instance != null ? instance.GetComponentInChildren<ChipMoviePlayer>( true ) : null;
			if ( player == null )
			{
				Debug.LogError( "chip " + chip + " has no movie player" );
				return;
			}

			// Hide the Sitekick so the dump is the chip's own drawing, like the SWF frame.
			var keep = new HashSet<SpriteRenderer>( instance.GetComponentsInChildren<SpriteRenderer>( true ) );
			foreach ( var r in UnityEngine.Object.FindObjectsByType<SpriteRenderer>( FindObjectsSortMode.None ) )
				if ( !keep.Contains( r ) )
					r.enabled = false;

			// Frame the whole stage: at the pipeline's scale a movie is wider than the
			// gallery view, and a dump has to be the chip's drawing and nothing else.
			var viewSize = camera.orthographicSize;
			var viewAt = camera.transform.position;
			camera.orthographicSize = 6.7f;
			camera.transform.position = new Vector3( ChipMovieBuilder.Anchor.x + 5.2f, ChipMovieBuilder.Anchor.y, -10f );

			var dir = "Logs/pilot/unity/" + chip.ToString( "0000" );
			Directory.CreateDirectory( dir );
			var lines = new StringBuilder();
			lines.AppendLine( "chip " + chip + " frames " + player.frames.Length + " fps " + player.fps
				+ " ortho " + camera.orthographicSize + " at " + camera.transform.position );
			for ( int i = 0; i < player.frames.Length; i++ )
			{
				player.SetFrame( i );
				var path = dir + "/frame_" + ( i + 1 ).ToString( "000" ) + ".png";
				Capture( camera, path );
				lines.AppendLine( ( i + 1 ) + " " + path );
			}

			gallery.Toggle( chip );
			camera.orthographicSize = viewSize;
			camera.transform.position = viewAt;
			File.WriteAllText( "Logs/pilot/unity/" + chip.ToString( "0000" ) + "/index.txt", lines.ToString() );
			Debug.Log( "dumped " + player.frames.Length + " frames of chip " + chip + " to " + dir );
		}

		/// <summary>Which chip the Ruffle comparison is using.</summary>
		public const int PilotChip = 12;

		static GameObject Find( int chip )
		{
			var name = "Chip_" + chip.ToString( "0000" ) + "_Effect";
			foreach ( var t in UnityEngine.Object.FindObjectsByType<Transform>( FindObjectsSortMode.None ) )
				if ( t != null && t.name == name )
					return t.gameObject;
			return null;
		}

		static void Capture( Camera camera, string path )
		{
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
