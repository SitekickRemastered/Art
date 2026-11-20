#if UNITY_EDITOR
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Shows a reference chip over the Sitekick the way the gallery does — through
	/// ChipGallery.Toggle, so the same layer, scale and offset — and records the
	/// world rectangle every renderer of it occupies. Writes
	/// Logs/pilot/ref-chipXXXX.txt and .png.
	/// </summary>
	public static class ChipEffectProbe
	{
		static readonly int[] Ids = { 20, 12, 7 };

		[MenuItem( "Sitekick/Probe Reference Chips" )]
		public static void Run()
		{
			EditorSceneManager.OpenScene( ChipMovieCheck.ScenePath, OpenSceneMode.Single );
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			var camera = Camera.main;
			if ( gallery == null || camera == null )
				return;

			camera.clearFlags = CameraClearFlags.SolidColor;
			camera.backgroundColor = Color.black;

			foreach ( var id in Ids )
			{
				gallery.Toggle( id );
				var lines = new StringBuilder();
				var effects = new System.Collections.Generic.List<GameObject>();
				foreach ( var active in gallery.ActiveEffects )
					effects.Add( active );
				foreach ( var effect in effects )
				{
					lines.AppendLine( "chip " + id + " effect " + effect.name
						+ " world scale " + effect.transform.lossyScale.ToString( "0.0000" ) );
					foreach ( var sr in effect.GetComponentsInChildren<SpriteRenderer>( true ) )
						lines.AppendLine( "  " + sr.name + " sort " + sr.sortingOrder
							+ " world " + sr.bounds.size.ToString( "0.0000" )
							+ " centre " + sr.bounds.center.ToString( "0.0000" ) );
				}

				var texture = new Texture2D( 720, 720, TextureFormat.RGB24, false );
				var cam = new GameObject( "probe_camera" ).AddComponent<Camera>();
				cam.CopyFrom( camera );
				cam.orthographic = true;
				cam.orthographicSize = 2.6f;
				cam.transform.position = new Vector3( 5.2f, 0.6f, -10f );
				cam.targetTexture = RenderTexture.GetTemporary( 720, 720, 24 );
				cam.Render();
				RenderTexture.active = cam.targetTexture;
				texture.ReadPixels( new Rect( 0, 0, 720, 720 ), 0, 0 );
				texture.Apply();
				File.WriteAllBytes( "Logs/pilot/ref-chip" + id.ToString( "0000" ) + ".png", texture.EncodeToPNG() );
				RenderTexture.active = null;
				cam.targetTexture.Release();

				File.WriteAllText( "Logs/pilot/ref-chip" + id.ToString( "0000" ) + ".txt", lines.ToString() );
				Debug.Log( lines.ToString() );

				Object.DestroyImmediate( texture );
				Object.DestroyImmediate( cam.gameObject );
				gallery.Toggle( id );
			}
		}
	}
}
#endif
