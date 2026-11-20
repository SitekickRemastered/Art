#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Renders two test SVGs side by side — the pilot frame as exported, and the
	/// same frame with its gradient-filled shapes removed — and writes what Unity
	/// actually drew, plus the world rectangle each sprite covered.
	///
	/// The point is to separate "the importer mangles gradients" from "the
	/// importer mangles the nested group transforms", which look the same in a
	/// single picture.
	/// </summary>
	public static class PilotSvgProbe
	{
		public const string ReportPath = "Logs/pilot/probe.txt";

		public static void Run()
		{
			EditorSceneManager.OpenScene( ChipMovieCheck.ScenePath, OpenSceneMode.Single );
			foreach ( var r in Object.FindObjectsByType<SpriteRenderer>( FindObjectsSortMode.None ) )
				r.enabled = false;

			var camera = Camera.main;
			camera.clearFlags = CameraClearFlags.SolidColor;
			camera.backgroundColor = Color.black;

			var flat = AssetDatabase.LoadAssetAtPath<Sprite>( "Assets/Pilot/bone_flat.svg" );
			var full = AssetDatabase.LoadAssetAtPath<Sprite>( "Assets/Pilot/bone_full.svg" );
			var lines = new System.Text.StringBuilder();
			if ( flat == null || full == null )
			{
				Debug.LogError( "test SVGs did not import: flat=" + flat + " full=" + full );
				return;
			}

			// The same two SVGs, once with the built-in sprite material and once with
			// the vector shader the icon baker uses, to see which one draws them.
			var vectorShader = Shader.Find( "Unlit/VectorGradient" );
			lines.AppendLine( "Unlit/VectorGradient: " + ( vectorShader != null ) );
			var mats = new System.Collections.Generic.List<Material>();
			Material sprite = null;
			Material vector = null;
			if ( vectorShader != null )
			{
				vector = new Material( vectorShader );
				mats.Add( vector );
			}

			var objs = new System.Collections.Generic.List<GameObject>();
			for ( int i = 0; i < 4; i++ )
			{
				var withVector = i >= 2;
				var which = i % 2 == 0 ? flat : full;
				var name = ( which == flat ? "flat" : "full" ) + ( withVector ? "_vector" : "_sprite" );
				objs.Add( Spawn( name, which, new Vector3( -5.4f + i * 3.6f, 0f, 0f ), lines,
					withVector ? vector : sprite ) );
			}
			lines.AppendLine( "camera ortho " + camera.orthographicSize + " at " + camera.transform.position );

			Capture( camera, "Logs/pilot/probe.png" );
			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );
			foreach ( var o in objs )
				UnityEngine.Object.DestroyImmediate( o );
			foreach ( var m in mats )
				UnityEngine.Object.DestroyImmediate( m );
		}

		static GameObject Spawn( string name, Sprite sprite, Vector3 at, System.Text.StringBuilder lines, Material material )
		{
			var go = new GameObject( "probe_" + name );
			go.transform.position = at;
			go.transform.localScale = Vector3.one * 0.12f;   // 26-unit sprite into a 14.7-unit view
			var sr = go.AddComponent<SpriteRenderer>();
			sr.sprite = sprite;
			if ( material != null )
				sr.sharedMaterial = material;
			var b = sr.bounds;
			lines.AppendLine( name + " bounds " + b.size.ToString( "0.000" ) + " center " + b.center.ToString( "0.000" )
				+ " material " + ( sr.sharedMaterial != null ? sr.sharedMaterial.shader.name : "none" ) );
			return go;
		}

		static void Capture( Camera camera, string path )
		{
			const int w = 1440, h = 1080;
			var rt = new RenderTexture( w, h, 24, RenderTextureFormat.ARGB32 );
			camera.targetTexture = rt;
			camera.Render();
			camera.targetTexture = null;
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
