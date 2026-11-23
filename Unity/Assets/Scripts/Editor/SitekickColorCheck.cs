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
	/// Renders the gallery Sitekick at a few colours and saves each one, so the
	/// tinting can be compared with the Flash reference (a probe copy of
	/// sitekick.swf whose paint() calls are inlined, played in Ruffle).
	///
	/// Batch entry point: -executeMethod Sitekick.SitekickColorCheck.RunFromCommandLine
	/// </summary>
	public static class SitekickColorCheck
	{
		const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		const string PhaseKey = "Sitekick.SitekickColorCheck.phase";
		const int Size = 640;

		static readonly string[] Colours = { "FFCC00", "FFFFFF", "3366FF" };

		static int retries;

		[InitializeOnLoadMethod]
		static void Hook()
		{
			EditorApplication.update -= Tick;
			if ( SessionState.GetInt( PhaseKey, 0 ) > 0 )
				EditorApplication.update += Tick;
		}

		public static void RunFromCommandLine()
		{
			Application.runInBackground = true;
			SessionState.SetInt( PhaseKey, 1 );
			// the prefab and its new sprites were written by a script, so the
			// scene's reference to it is only resolvable after an import
			AssetDatabase.Refresh();
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			EditorApplication.update -= Tick;
			EditorApplication.update += Tick;
		}

		static void Tick()
		{
			var phase = SessionState.GetInt( PhaseKey, 0 );
			if ( phase != 1 )
				return;

			if ( EditorUtility.scriptCompilationFailed )
			{
				Debug.Log( "SitekickColorCheck: scripts have compile errors" );
				Finish();
			}
			else if ( EditorApplication.isPlaying )
				Run();
			else if ( !EditorApplication.isPlayingOrWillChangePlaymode )
				EditorApplication.isPlaying = true;
		}

		static void Run()
		{
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			var root = gallery != null ? gallery.Sitekick : null;
			var sitekick = root != null ? root.GetComponentInChildren<EditorSitekick>( true ) : null;
			if ( sitekick == null )
			{
				if ( retries++ < 20 )
					return;
				Debug.Log( "SitekickColorCheck: the gallery has no Sitekick" );
				Finish();
				return;
			}

			var body = FindBody( root );
			foreach ( var hex in Colours )
			{
				Color colour;
				if ( !ColorUtility.TryParseHtmlString( "#" + hex, out colour ) )
					continue;

				sitekick.SetColor( colour );
				var dir = "Logs/sitekick-colour-" + hex.ToLowerInvariant();
				Directory.CreateDirectory( dir );
				Capture( dir + "/art.png", body != null ? body.bounds : new Bounds() );
				Debug.Log( "SitekickColorCheck: wrote " + dir );
			}

			Finish();
		}

		static Renderer FindBody( Transform sitekick )
		{
			foreach ( var t in sitekick.GetComponentsInChildren<Transform>( true ) )
			{
				if ( t.name == "Body" )
					return t.GetComponent<Renderer>();
			}
			return null;
		}

		/// <summary>Renders the camera at `bounds` and logs the colours it found.</summary>
		internal static void Capture( string path, Bounds bounds )
		{
			var camera = Camera.main;
			if ( camera == null )
				return;

			var viewSize = camera.orthographicSize;
			var aspect = camera.aspect;
			var radius = Mathf.Max( bounds.extents.x, bounds.extents.y );
			camera.orthographicSize = Mathf.Max( 0.5f, radius * 1.25f );
			camera.transform.position = new Vector3( bounds.center.x, bounds.center.y,
				camera.transform.position.z );

			var rt = new RenderTexture( Size, Size, 24, RenderTextureFormat.ARGB32 );
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
			var tex = new Texture2D( Size, Size, TextureFormat.RGBA32, false );
			tex.ReadPixels( new Rect( 0, 0, Size, Size ), 0, 0 );
			tex.Apply();
			RenderTexture.active = active;

			var counts = new Dictionary<string, int>();
			var pixels = tex.GetPixels32();
			foreach ( var p in pixels )
			{
				if ( p.a < 250 )
					continue;
				var key = string.Format( "{0:X2}{1:X2}{2:X2}", p.r, p.g, p.b );
				int n;
				counts.TryGetValue( key, out n );
				counts[ key ] = n + 1;
			}

			var order = new List<KeyValuePair<string, int>>( counts );
			order.Sort( ( a, b ) => b.Value.CompareTo( a.Value ) );
			var lines = new StringBuilder();
			for ( var i = 0; i < Mathf.Min( 6, order.Count ); i++ )
				lines.AppendLine( "  #" + order[ i ].Key + " " + order[ i ].Value );
			Debug.Log( Path.GetFileName( Path.GetDirectoryName( path ) ) + ":\n" + lines );

			File.WriteAllBytes( path, tex.EncodeToPNG() );
			Object.DestroyImmediate( tex );
			rt.Release();
			Object.DestroyImmediate( rt );
			camera.orthographicSize = viewSize;
			camera.aspect = aspect;
		}

		static void Finish()
		{
			SessionState.SetInt( PhaseKey, 0 );
			EditorApplication.update -= Tick;
			EditorApplication.isPlaying = false;
			EditorApplication.delayCall += () => EditorApplication.Exit( 0 );
		}
	}
}
#endif
